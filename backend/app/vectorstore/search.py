"""
Semantic Search Service

High-level interface for vector similarity search.

Combines:
- FAISS index (vector search)
- Metadata store (prompt/response mapping)
- Embedding service (query embedding)
"""
import time
import logging
from typing import List, Optional, Tuple
import numpy as np

from app.vectorstore.faiss_index import get_faiss_index, FAISSIndex
from app.vectorstore.storage import get_metadata_store, MetadataStore
from app.embeddings.service import get_embedding_service
from app.embeddings.utils import list_to_vector
from app.models.search_schemas import (
    SearchQuery,
    SearchResult,
    SearchResults,
    VectorMetadata,
    CacheEntry,
)
from app.models.embedding_schemas import Embedding
from app.core.config import settings

logger = logging.getLogger(__name__)


class SemanticSearchService:
    """
    Semantic search service

    Provides high-level interface for:
    - Adding embeddings to index
    - Searching for similar prompts
    - Retrieving cache entries
    """

    def __init__(
        self,
        faiss_index: Optional[FAISSIndex] = None,
        metadata_store: Optional[MetadataStore] = None
    ):
        """
        Initialize semantic search service

        Args:
            faiss_index: FAISS index instance (defaults to global)
            metadata_store: Metadata store instance (defaults to global)
        """
        self.faiss_index = faiss_index or get_faiss_index()
        self.metadata_store = metadata_store or get_metadata_store()
        self.embedding_service = get_embedding_service()

        logger.info("SemanticSearchService initialized")

    def add_to_index(
        self,
        embedding: Embedding,
        response_text: str,
        model_name: str,
        tenant_id: str = "default",
        system_prompt: Optional[str] = None,
        conversation_history: Optional[str] = None,
        cache_key_hash: Optional[str] = None
    ) -> int:
        """
        Add an embedding to the search index

        Args:
            embedding: Embedding to add
            response_text: The LLM response to cache
            model_name: Model that generated the response
            tenant_id: Tenant namespace
            system_prompt: System prompt used (if any)
            conversation_history: Conversation context (for exact matching)
            cache_key_hash: Redis cache key hash (for retrieval)

        Returns:
            Vector ID assigned by FAISS
        """
        # Convert to numpy array
        vector = list_to_vector(embedding.vector).reshape(1, -1)

        # Add to FAISS index
        vector_ids = self.faiss_index.add_vectors(vector)
        vector_id = int(vector_ids[0])

        # Create metadata
        metadata = VectorMetadata(
            vector_id=vector_id,
            prompt_id=embedding.metadata.prompt_hash,
            prompt_text=embedding.text,
            response_text=response_text,
            model_name=model_name,
            embedding_model=self.embedding_service.model.model_name,
            tenant_id=tenant_id,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            cache_key_hash=cache_key_hash,
            timestamp=embedding.metadata.timestamp,
            request_params=embedding.metadata.request_params,
            cache_hits=0
        )

        # Add to metadata store
        self.metadata_store.add(metadata)

        logger.info(
            f"Added to index: vector_id={vector_id}, "
            f"prompt='{embedding.text[:50]}...'"
        )

        return vector_id

    def add_batch_to_index(
        self,
        embeddings: List[Embedding],
        responses: List[str],
        model_name: str,
        tenant_id: str = "default",
        system_prompt: Optional[str] = None
    ) -> List[int]:
        """
        Add multiple embeddings to index (more efficient)

        Args:
            embeddings: List of embeddings
            responses: List of corresponding responses
            model_name: Model name
            tenant_id: Tenant namespace
            system_prompt: System prompt used (if any)

        Returns:
            List of assigned vector IDs
        """
        if len(embeddings) != len(responses):
            raise ValueError("Number of embeddings must match number of responses")

        # Convert to numpy array
        vectors = np.array([emb.vector for emb in embeddings], dtype=np.float32)

        # Add to FAISS
        vector_ids = self.faiss_index.add_vectors(vectors)

        # Create metadata
        metadata_list = []
        for i, (embedding, response) in enumerate(zip(embeddings, responses)):
            metadata = VectorMetadata(
                vector_id=int(vector_ids[i]),
                prompt_id=embedding.metadata.prompt_hash,
                prompt_text=embedding.text,
                response_text=response,
                model_name=model_name,
                embedding_model=self.embedding_service.model.model_name,
                tenant_id=tenant_id,
                system_prompt=system_prompt,
                timestamp=embedding.metadata.timestamp,
                request_params=embedding.metadata.request_params,
                cache_hits=0
            )
            metadata_list.append(metadata)

        # Add to metadata store
        self.metadata_store.add_batch(metadata_list)

        logger.info(f"Added batch of {len(embeddings)} embeddings to index")

        return [int(vid) for vid in vector_ids]

    def search(
        self,
        query_embedding: Embedding,
        top_k: int = 5,
        threshold: Optional[float] = None
    ) -> SearchResults:
        """
        Search for similar embeddings

        Args:
            query_embedding: Query embedding
            top_k: Number of results to return
            threshold: Minimum similarity threshold

        Returns:
            SearchResults with matches
        """
        start_time = time.time()

        # Convert to numpy
        query_vector = list_to_vector(query_embedding.vector)

        # Search FAISS
        distances, indices = self.faiss_index.search_single(query_vector, k=top_k)

        # Convert to results
        results = []
        for i, (distance, idx) in enumerate(zip(distances, indices)):
            # Skip invalid indices
            if idx == -1:
                continue

            # Get metadata
            metadata = self.metadata_store.get(int(idx))
            if metadata is None:
                logger.warning(f"No metadata for vector_id={idx}")
                continue

            # Convert distance to similarity
            similarity = self.faiss_index.distance_to_similarity(float(distance))

            # Apply threshold if specified
            if threshold is not None and similarity < threshold:
                continue

            # Create result
            result = SearchResult(
                vector_id=int(idx),
                prompt_id=metadata.prompt_id,
                similarity=similarity,
                distance=float(distance),
                prompt_text=metadata.prompt_text,
                response_text=metadata.response_text,
                metadata=metadata.to_dict(),
                timestamp=metadata.timestamp
            )
            results.append(result)

        search_time = (time.time() - start_time) * 1000  # ms

        logger.info(
            f"Search completed: {len(results)} results in {search_time:.2f}ms "
            f"(threshold={threshold})"
        )

        return SearchResults(
            query_vector=query_embedding.vector,
            results=results,
            total_found=len(results),
            search_time_ms=search_time,
            threshold_applied=threshold
        )

    def get_cache_entry(
        self,
        query_embedding: Embedding,
        threshold: Optional[float] = None,
        model_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[str] = None,
        require_same_model: bool = False
    ) -> Optional[CacheEntry]:
        """
        Get best cache match for a query

        This is the main method used by the cache layer.
        Retrieves top-k candidates and filters for valid matches.

        Args:
            query_embedding: Query embedding
            threshold: Minimum similarity (defaults to settings)
            model_name: Filter by model name
            tenant_id: Filter by tenant
            system_prompt: Filter by system prompt
            require_same_model: Whether to require exact model match

        Returns:
            CacheEntry if match found, None otherwise
        """
        threshold = threshold or settings.SIMILARITY_THRESHOLD

        # Search for top candidates (not just top-1)
        # This allows filtering and picking the best valid match
        results = self.search(query_embedding, top_k=10, threshold=threshold)

        # Filter candidates for valid matches
        valid_candidates = []
        for result in results.results:
            metadata = self.metadata_store.get(result.vector_id)
            if metadata is None:
                continue

            # Filter by tenant
            if tenant_id and metadata.tenant_id != tenant_id:
                continue

            # Filter by model
            if model_name and require_same_model:
                if metadata.model_name != model_name:
                    continue

            # Filter by system prompt (must match exactly)
            if system_prompt != metadata.system_prompt:
                continue

            # Filter by conversation history (must match exactly for multi-turn)
            if conversation_history != metadata.conversation_history:
                continue

            # Check TTL expiration
            if metadata.timestamp:
                from datetime import datetime, timedelta
                ttl_seconds = settings.CACHE_TTL_SECONDS
                expiration = metadata.timestamp + timedelta(seconds=ttl_seconds)
                if datetime.utcnow() > expiration:
                    continue

            valid_candidates.append((result, metadata))

        if not valid_candidates:
            logger.info("No valid cache match found after filtering")
            return None

        # Get the best valid candidate (highest similarity)
        best_result, best_metadata = valid_candidates[0]

        # Increment cache hit counter
        self.metadata_store.increment_cache_hit(best_result.vector_id)

        # Create cache entry
        cache_entry = CacheEntry(
            vector_id=best_result.vector_id,
            prompt_id=best_result.prompt_id,
            prompt_text=best_result.prompt_text,
            response_text=best_result.response_text or "",
            similarity=best_result.similarity,
            metadata=best_metadata,
            is_cache_hit=True
        )

        logger.info(
            f"Cache HIT: similarity={best_result.similarity:.3f}, "
            f"vector_id={best_result.vector_id} "
            f"(filtered {len(results.results) - len(valid_candidates)} invalid candidates)"
        )

        return cache_entry

    def get_stats(self) -> dict:
        """
        Get search service statistics

        Returns:
            Dictionary with stats
        """
        faiss_stats = self.faiss_index.get_stats()
        metadata_stats = self.metadata_store.get_stats()

        return {
            "faiss": faiss_stats,
            "metadata": metadata_stats,
            "embedding_model": self.embedding_service.get_model_info()
        }

    def save_index(self, index_path: Optional[str] = None) -> None:
        """
        Save FAISS index and metadata to disk

        Args:
            index_path: Optional custom path for FAISS index
        """
        # Default paths
        if index_path is None:
            from pathlib import Path
            base_dir = Path(__file__).parent.parent.parent.parent
            storage_dir = base_dir / "data" / "cache"
            storage_dir.mkdir(parents=True, exist_ok=True)
            index_path = str(storage_dir / "faiss.index")

        # Save FAISS index
        self.faiss_index.save(index_path)

        # Save metadata
        self.metadata_store.save()

        logger.info(f"Saved index and metadata")

    def load_index(self, index_path: Optional[str] = None) -> None:
        """
        Load FAISS index and metadata from disk

        Args:
            index_path: Optional custom path for FAISS index
        """
        # Default path
        if index_path is None:
            from pathlib import Path
            base_dir = Path(__file__).parent.parent.parent.parent
            index_path = str(base_dir / "data" / "cache" / "faiss.index")

        # Load FAISS index
        try:
            self.faiss_index.load(index_path)
        except FileNotFoundError:
            logger.warning(f"FAISS index not found at {index_path}")

        # Load metadata
        self.metadata_store.load()

        logger.info("Loaded index and metadata")

    def clear_index(self) -> None:
        """Clear all data from index"""
        self.faiss_index.reset()
        self.metadata_store.clear()
        logger.info("Cleared index and metadata")


# Global instance
_search_service: Optional[SemanticSearchService] = None


def get_search_service() -> SemanticSearchService:
    """
    Get global search service instance

    Returns:
        SemanticSearchService singleton
    """
    global _search_service

    if _search_service is None:
        _search_service = SemanticSearchService()
        # Try to load existing index
        try:
            _search_service.load_index()
        except Exception as e:
            logger.warning(f"Could not load existing index: {e}")

    return _search_service
