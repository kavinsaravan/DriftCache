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
import os
import json
import threading
from datetime import datetime
from typing import List, Optional, Tuple
import numpy as np

from app.vectorstore.faiss_index import get_faiss_index, FAISSIndex
from app.vectorstore.storage import get_metadata_store, MetadataStore
from app.embeddings.model import EmbeddingModel, set_embedding_model
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
        self._lock = threading.RLock()
        self._dirty = False

        logger.info("SemanticSearchService initialized")

    @property
    def write_lock(self):
        """Expose the shared lock to maintenance and deployment operations."""
        return self._lock

    def _append_journal(
        self, entries: List[Tuple[np.ndarray, VectorMetadata]]
    ) -> None:
        """Durably append one vector mutation batch between checkpoints."""
        journal_path = f"{self.metadata_store.storage_path}.journal"
        journal_dir = os.path.dirname(journal_path)
        if journal_dir:
            os.makedirs(journal_dir, exist_ok=True)
        record = {
            "entries": [
                {
                    "vector_id": metadata.vector_id,
                    "vector": vector.reshape(-1).astype(float).tolist(),
                    "metadata": metadata.to_dict(),
                }
                for vector, metadata in entries
            ]
        }
        with open(journal_path, "a+", encoding="utf-8") as journal:
            journal.seek(0, os.SEEK_END)
            previous_size = journal.tell()
            try:
                journal.write(json.dumps(record, separators=(",", ":")) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
            except Exception:
                journal.seek(previous_size)
                journal.truncate()
                journal.flush()
                os.fsync(journal.fileno())
                raise

    def _truncate_journal(self) -> None:
        journal_path = f"{self.metadata_store.storage_path}.journal"
        temporary_path = f"{journal_path}.saving"
        journal_dir = os.path.dirname(journal_path)
        if journal_dir:
            os.makedirs(journal_dir, exist_ok=True)
        with open(temporary_path, "w", encoding="utf-8") as journal:
            journal.flush()
            os.fsync(journal.fileno())
        os.replace(temporary_path, journal_path)

    def mark_checkpointed(self) -> None:
        """Mark an externally written atomic index snapshot as durable."""
        with self._lock:
            self._truncate_journal()
            self._dirty = False

    def _replay_journal(self) -> int:
        journal_path = f"{self.metadata_store.storage_path}.journal"
        if not os.path.exists(journal_path):
            return 0

        existing_ids = self.faiss_index.get_ids()
        replayed = 0
        with open(journal_path, encoding="utf-8") as journal:
            for line_number, line in enumerate(journal, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    for entry in record["entries"]:
                        vector_id = int(entry["vector_id"])
                        metadata = VectorMetadata.from_dict(entry["metadata"])
                        if vector_id not in existing_ids:
                            self.faiss_index.add_vectors(
                                np.asarray([entry["vector"]], dtype=np.float32),
                                ids=np.asarray([vector_id], dtype=np.int64),
                            )
                            existing_ids.add(vector_id)
                        self.metadata_store.add(metadata)
                        replayed += 1
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    logger.warning(
                        "Ignoring malformed vector journal record at line %s",
                        line_number,
                    )
        if replayed:
            self._dirty = True
            logger.info("Replayed %s vector journal records", replayed)
        return replayed

    def add_to_index(
        self,
        embedding: Embedding,
        response_text: str,
        model_name: str,
        cache_id: Optional[str] = None,
        tenant_id: str = "default",
        system_prompt: Optional[str] = None,
        conversation_history: Optional[str] = None,
        cache_key_hash: Optional[str] = None,
        request_params: Optional[dict] = None,
        expires_at: Optional[datetime] = None,
    ) -> int:
        """
        Add an embedding to the search index

        Args:
            embedding: Embedding to add
            response_text: The LLM response to cache
            model_name: Model that generated the response
            cache_id: Persistent cache entry UUID
            tenant_id: Tenant namespace
            system_prompt: System prompt used (if any)
            conversation_history: Conversation context (for exact matching)
            cache_key_hash: Redis cache key hash (for retrieval)

        Returns:
            Vector ID assigned by FAISS
        """
        with self._lock:
            vector = list_to_vector(embedding.vector).reshape(1, -1)
            vector_ids = self.faiss_index.add_vectors(vector)
            vector_id = int(vector_ids[0])
            metadata = VectorMetadata(
                vector_id=vector_id,
                cache_id=cache_id,
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
                expires_at=expires_at,
                request_params=request_params or {},
                cache_hits=0,
            )
            metadata.expires_at = metadata.expiration_time()
            self.metadata_store.add(metadata)
            try:
                self._append_journal([(vector, metadata)])
            except Exception:
                self.faiss_index.remove_vectors(
                    np.asarray([vector_id], dtype=np.int64)
                )
                self.metadata_store.delete(vector_id)
                raise
            self._dirty = True

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

        with self._lock:
            vectors = np.array([emb.vector for emb in embeddings], dtype=np.float32)
            vector_ids = self.faiss_index.add_vectors(vectors)
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
                    cache_hits=0,
                )
                metadata.expires_at = metadata.expiration_time()
                metadata_list.append(metadata)
            self.metadata_store.add_batch(metadata_list)
            try:
                self._append_journal(list(zip(vectors, metadata_list)))
            except Exception:
                self.faiss_index.remove_vectors(vector_ids.astype(np.int64))
                for metadata in metadata_list:
                    self.metadata_store.delete(metadata.vector_id)
                raise
            self._dirty = True

        logger.info(f"Added batch of {len(embeddings)} embeddings to index")

        return [int(vid) for vid in vector_ids]

    def search(
        self,
        query_embedding: Embedding,
        top_k: int = 5,
        threshold: Optional[float] = None,
    ) -> SearchResults:
        with self._lock:
            return self._search_unlocked(query_embedding, top_k, threshold)

    def _search_unlocked(
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
        request_params: Optional[dict] = None,
        require_same_model: bool = True,
        include_below_threshold: bool = False,
    ) -> Optional[CacheEntry]:
        with self._lock:
            return self._get_cache_entry_unlocked(
                query_embedding=query_embedding,
                threshold=threshold,
                model_name=model_name,
                tenant_id=tenant_id,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                request_params=request_params,
                require_same_model=require_same_model,
                include_below_threshold=include_below_threshold,
            )

    def _get_cache_entry_unlocked(
        self,
        query_embedding: Embedding,
        threshold: Optional[float] = None,
        model_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[str] = None,
        request_params: Optional[dict] = None,
        require_same_model: bool = True,
        include_below_threshold: bool = False,
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
        threshold = settings.SIMILARITY_THRESHOLD if threshold is None else threshold

        # Search for top candidates (not just top-1)
        # This allows filtering and picking the best valid match
        # Start with top_k=10, retry with larger k if all candidates filtered out
        top_k = 10
        max_retries = 2
        retry_count = 0

        while retry_count <= max_retries:
            results = self.search(
                query_embedding, top_k=top_k,
                threshold=None if include_below_threshold else threshold,
            )

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

                # Sampling and stopping parameters affect the provider response
                # and must match exactly before a response can be reused.
                if (request_params or {}) != metadata.request_params:
                    continue

                # Check TTL expiration
                if metadata.is_expired():
                    continue

                valid_candidates.append((result, metadata))

            # If we found valid candidates, break out of retry loop
            if valid_candidates:
                break

            # All candidates filtered out - retry with larger k
            retry_count += 1
            if retry_count <= max_retries:
                top_k = top_k * 3  # Triple the search width
                logger.info(f"All {len(results.results)} candidates filtered out, retrying with top_k={top_k}")
            else:
                logger.info("No valid cache match found after filtering and retries")
                return None

        if not valid_candidates:
            logger.info("No valid cache match found after filtering")
            return None

        # Get the best valid candidate (highest similarity)
        best_result, best_metadata = valid_candidates[0]

        # Below-threshold candidates are observations, never cache hits.
        is_hit = best_result.similarity >= threshold
        if is_hit:
            self.metadata_store.increment_cache_hit(best_result.vector_id)
            self._dirty = True

        # Create cache entry
        cache_entry = CacheEntry(
            vector_id=best_result.vector_id,
            prompt_id=best_result.prompt_id,
            prompt_text=best_result.prompt_text,
            response_text=best_result.response_text or "",
            similarity=best_result.similarity,
            metadata=best_metadata,
            is_cache_hit=is_hit
        )

        logger.info(
            f"Cache candidate: similarity={best_result.similarity:.3f}, "
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
        with self._lock:
            if index_path is None:
                index_path = settings.get_index_path()

            metadata_path = self.metadata_store.storage_path
            temporary_index_path = f"{index_path}.saving"
            temporary_metadata_path = f"{metadata_path}.saving"
            try:
                self.faiss_index.save(temporary_index_path)
                self.metadata_store.save(temporary_metadata_path)
                os.replace(temporary_metadata_path, metadata_path)
                os.replace(temporary_index_path, index_path)
                self._truncate_journal()
                self._dirty = False
            finally:
                for temporary_path in (temporary_index_path, temporary_metadata_path):
                    if os.path.exists(temporary_path):
                        os.remove(temporary_path)

            logger.info("Saved index and metadata checkpoint")

    def save_if_dirty(self) -> bool:
        """Write an atomic checkpoint only when in-memory state changed."""
        with self._lock:
            if not self._dirty:
                return False
            self.save_index()
            return True

    def load_index(self, index_path: Optional[str] = None) -> None:
        """
        Load FAISS index and metadata from disk

        Args:
            index_path: Optional custom path for FAISS index
        """
        with self._lock:
            if index_path is None:
                index_path = settings.get_index_path()

            try:
                self.faiss_index.load(index_path)
            except FileNotFoundError:
                logger.warning(f"FAISS index not found at {index_path}")

            self.metadata_store.load()
            self._replay_journal()

            logger.info("Loaded index, metadata, and pending journal entries")

    def remove_expired_vectors(self, ttl_seconds: Optional[int] = None) -> int:
        """
        Remove expired vectors from FAISS index and metadata

        Args:
            ttl_seconds: Time-to-live in seconds. Defaults to settings.CACHE_TTL_SECONDS

        Returns:
            Number of vectors removed
        """
        from app.core.config import settings

        if ttl_seconds is None:
            ttl_seconds = settings.CACHE_TTL_SECONDS

        with self._lock:
            now = datetime.utcnow()
            expired_vector_ids = []
            for vector_id, metadata in self.metadata_store.metadata.items():
                if metadata.is_expired(now, ttl_seconds):
                    expired_vector_ids.append(vector_id)

            if not expired_vector_ids:
                logger.info("No expired vectors to remove")
                return 0

            expired_ids_array = np.array(expired_vector_ids, dtype=np.int64)
            self.faiss_index.remove_vectors(expired_ids_array)
            for vector_id in expired_vector_ids:
                self.metadata_store.delete(vector_id)
            self._dirty = True

        logger.info(f"Removed {len(expired_vector_ids)} expired vectors from index")

        return len(expired_vector_ids)

    def clear_index(self) -> None:
        """Clear all data from index"""
        with self._lock:
            self.faiss_index.reset()
            self.metadata_store.clear()
            self._dirty = True
            self.save_index()
        logger.info("Cleared index and metadata")

    def rebuild_with_embedding_model(self, embedding_model: EmbeddingModel) -> int:
        with self._lock:
            return self._rebuild_with_embedding_model_unlocked(embedding_model)

    def _rebuild_with_embedding_model_unlocked(
        self, embedding_model: EmbeddingModel
    ) -> int:
        """Re-embed every live entry, persist it, and switch models as one cutover."""
        current_metadata = [m for m in self.metadata_store.get_all() if not m.is_expired()]
        new_index = FAISSIndex(
            dimension=embedding_model.dimension,
            index_type=settings.VECTOR_INDEX_TYPE,
        )
        new_index.create_index()
        new_store = MetadataStore(storage_path=self.metadata_store.storage_path)

        if current_metadata:
            vectors = embedding_model.encode(
                [item.prompt_text for item in current_metadata],
                normalize=True,
                show_progress=False,
            )
            ids = np.asarray([item.vector_id for item in current_metadata], dtype=np.int64)
            new_index.add_vectors(vectors, ids=ids)

            rebuilt_metadata = []
            for item in current_metadata:
                rebuilt = item.model_copy(deep=True)
                rebuilt.embedding_model = embedding_model.model_name
                rebuilt_metadata.append(rebuilt)
            new_store.add_batch(rebuilt_metadata)

        index_path = settings.get_index_path()
        metadata_path = settings.get_metadata_path()
        temporary_index_path = f"{index_path}.deploying"
        temporary_metadata_path = f"{metadata_path}.deploying"
        try:
            new_index.save(temporary_index_path)
            new_store.save(temporary_metadata_path)
            os.replace(temporary_index_path, index_path)
            os.replace(temporary_metadata_path, metadata_path)
        finally:
            for temporary_path in (temporary_index_path, temporary_metadata_path):
                if os.path.exists(temporary_path):
                    os.remove(temporary_path)

        # Swap the objects only after the replacement index is fully built and saved.
        self.faiss_index.dimension = new_index.dimension
        self.faiss_index.index = new_index.index
        self.faiss_index._next_id = new_index._next_id
        self.metadata_store.metadata = new_store.metadata
        self.embedding_service.model = embedding_model
        set_embedding_model(embedding_model)
        settings.EMBEDDING_MODEL = embedding_model.model_name
        settings.EMBEDDING_DIMENSION = embedding_model.dimension
        self._truncate_journal()
        self._dirty = False

        logger.info(
            "Deployed embedding model %s and rebuilt %s vectors",
            embedding_model.model_name,
            len(current_metadata),
        )
        return len(current_metadata)


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
