"""
Embedding Service

Main service for generating and managing embeddings.

This is the entry point for the embedding pipeline:
1. Receive text
2. Normalize and clean
3. Generate embedding
4. Attach metadata
5. Return vector + metadata
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import numpy as np

from app.embeddings.model import get_embedding_model
from app.embeddings.utils import (
    extract_prompt_from_messages,
    normalize_text,
    create_prompt_hash,
    clean_text,
    truncate_for_embedding,
    vector_to_list,
)
from app.models.schemas import Message
from app.models.embedding_schemas import (
    Embedding,
    EmbeddingMetadata,
    EmbeddingBatch,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating embeddings

    This is the main interface for the embedding pipeline
    """

    def __init__(self):
        """Initialize the embedding service"""
        self.model = get_embedding_model()
        logger.info("EmbeddingService initialized")

    def embed_text(
        self,
        text: str,
        model_name: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None
    ) -> Embedding:
        """
        Generate an embedding for text

        This is the main method for single-text embedding

        Args:
            text: Text to embed
            model_name: Model name to include in metadata
            user_id: Optional user identifier
            session_id: Optional session identifier
            request_params: Optional request parameters

        Returns:
            Embedding object with vector and metadata
        """
        # Clean and normalize text
        cleaned_text = clean_text(text)
        normalized_text = normalize_text(cleaned_text)
        truncated_text = truncate_for_embedding(cleaned_text)

        # Generate embedding
        vector = self.model.encode_single(truncated_text, normalize=True)

        # Create metadata
        metadata = EmbeddingMetadata(
            prompt_hash=create_prompt_hash(normalized_text),
            model_name=model_name or self.model.model_name,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            session_id=session_id,
            request_params=request_params or {}
        )

        # Create embedding
        embedding = Embedding(
            vector=vector_to_list(vector),
            dimension=self.model.dimension,
            text=cleaned_text,
            metadata=metadata
        )

        logger.debug(
            f"Generated embedding: dim={embedding.dimension}, "
            f"hash={metadata.prompt_hash[:8]}..."
        )

        return embedding

    def embed_messages(
        self,
        messages: List[Message],
        model_name: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None
    ) -> Embedding:
        """
        Generate an embedding from chat messages

        Extracts user prompts and creates a single embedding

        Args:
            messages: Chat messages
            model_name: Model name for metadata
            user_id: Optional user identifier
            session_id: Optional session identifier
            request_params: Optional request parameters

        Returns:
            Embedding object
        """
        # Extract prompt from messages
        prompt = extract_prompt_from_messages(messages)

        # Generate embedding
        return self.embed_text(
            text=prompt,
            model_name=model_name,
            user_id=user_id,
            session_id=session_id,
            request_params=request_params
        )

    def embed_batch(
        self,
        texts: List[str],
        model_name: Optional[str] = None
    ) -> EmbeddingBatch:
        """
        Generate embeddings for a batch of texts

        More efficient than calling embed_text multiple times

        Args:
            texts: List of texts to embed
            model_name: Model name for metadata

        Returns:
            EmbeddingBatch with all embeddings
        """
        # Clean and prepare texts
        cleaned_texts = [clean_text(text) for text in texts]
        truncated_texts = [
            truncate_for_embedding(text) for text in cleaned_texts
        ]

        # Generate embeddings (batch operation is faster)
        vectors = self.model.encode(truncated_texts, normalize=True)

        # Create embedding objects
        embeddings = []
        for i, (text, vector) in enumerate(zip(cleaned_texts, vectors)):
            normalized = normalize_text(text)

            metadata = EmbeddingMetadata(
                prompt_hash=create_prompt_hash(normalized),
                model_name=model_name or self.model.model_name,
                timestamp=datetime.utcnow(),
                request_params={"batch_index": i}
            )

            embedding = Embedding(
                vector=vector_to_list(vector),
                dimension=self.model.dimension,
                text=text,
                metadata=metadata
            )
            embeddings.append(embedding)

        batch = EmbeddingBatch(
            embeddings=embeddings,
            total_count=len(embeddings),
            model_name=model_name or self.model.model_name
        )

        logger.info(f"Generated batch of {len(embeddings)} embeddings")

        return batch

    def compute_similarity(
        self,
        embedding1: Embedding,
        embedding2: Embedding
    ) -> float:
        """
        Compute cosine similarity between two embeddings

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Similarity score [0, 1]
        """
        # Convert to numpy arrays
        from app.embeddings.utils import list_to_vector

        vec1 = list_to_vector(embedding1.vector)
        vec2 = list_to_vector(embedding2.vector)

        # Compute similarity
        similarity = self.model.similarity(vec1, vec2)

        return similarity

    def find_most_similar(
        self,
        query_embedding: Embedding,
        candidate_embeddings: List[Embedding],
        top_k: int = 5,
        threshold: Optional[float] = None
    ) -> List[tuple[Embedding, float]]:
        """
        Find most similar embeddings to a query

        Args:
            query_embedding: Query embedding
            candidate_embeddings: List of candidate embeddings
            top_k: Number of top results to return
            threshold: Optional minimum similarity threshold

        Returns:
            List of (embedding, similarity) tuples, sorted by similarity
        """
        from app.embeddings.utils import list_to_vector

        query_vec = list_to_vector(query_embedding.vector)

        # Compute similarities
        results = []
        for candidate in candidate_embeddings:
            candidate_vec = list_to_vector(candidate.vector)
            similarity = self.model.similarity(query_vec, candidate_vec)

            # Apply threshold if specified
            if threshold is None or similarity >= threshold:
                results.append((candidate, similarity))

        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)

        # Return top K
        return results[:top_k]

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the embedding model

        Returns:
            Dictionary with model information
        """
        return {
            "model_name": self.model.model_name,
            "dimension": self.model.dimension,
            "loaded": self.model.is_loaded(),
        }


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Get the global embedding service instance

    Returns:
        EmbeddingService singleton
    """
    global _embedding_service

    if _embedding_service is None:
        _embedding_service = EmbeddingService()

    return _embedding_service
