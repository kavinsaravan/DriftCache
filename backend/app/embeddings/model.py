"""
Embedding Model

Loads and manages the sentence-transformers model for generating embeddings.

We use all-MiniLM-L6-v2 because it's:
- Lightweight (80MB)
- Fast (inference < 50ms)
- Free/local (no API costs)
- Strong enough for semantic similarity (384 dimensions)
"""
import logging
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    Wrapper for sentence-transformers model

    Handles model loading, caching, and inference
    """

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize embedding model

        Args:
            model_name: Name of the model to load (defaults to settings)
        """
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.model: Optional[SentenceTransformer] = None
        self._dimension: Optional[int] = None

        logger.info(f"Initializing embedding model: {self.model_name}")

    def load(self) -> None:
        """
        Load the model into memory

        This is called lazily on first use
        """
        if self.model is not None:
            logger.debug("Model already loaded")
            return

        try:
            logger.info(f"Loading model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            self._dimension = self.model.get_sentence_embedding_dimension()
            logger.info(
                f"Model loaded successfully. Dimension: {self._dimension}"
            )
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise RuntimeError(f"Could not load embedding model: {e}")

    def encode(
        self,
        texts: List[str],
        normalize: bool = True,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        Generate embeddings for a list of texts

        Args:
            texts: List of texts to embed
            normalize: Whether to L2-normalize vectors for cosine similarity
            show_progress: Show progress bar for batch encoding

        Returns:
            Numpy array of embeddings [batch_size, dimension]
        """
        # Lazy load model
        if self.model is None:
            self.load()

        try:
            embeddings = self.model.encode(
                texts,
                normalize_embeddings=normalize,
                show_progress_bar=show_progress,
                convert_to_numpy=True
            )
            return embeddings

        except Exception as e:
            logger.error(f"Error encoding texts: {e}")
            raise

    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed
            normalize: Whether to L2-normalize vector

        Returns:
            Numpy array embedding [dimension]
        """
        embeddings = self.encode([text], normalize=normalize)
        return embeddings[0]

    @property
    def dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this model

        Returns:
            Embedding dimension (e.g., 384 for all-MiniLM-L6-v2)
        """
        if self._dimension is None:
            if self.model is None:
                self.load()
            self._dimension = self.model.get_sentence_embedding_dimension()
        return self._dimension

    def similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings

        Assumes embeddings are already normalized.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score [0, 1]
        """
        # For normalized vectors, cosine similarity = dot product
        similarity = np.dot(embedding1, embedding2)
        return float(similarity)

    def batch_similarity(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute similarity between one query and multiple candidates

        Args:
            query_embedding: Query vector [dimension]
            candidate_embeddings: Candidate vectors [n_candidates, dimension]

        Returns:
            Similarity scores [n_candidates]
        """
        # Matrix multiplication for batch similarity
        similarities = np.dot(candidate_embeddings, query_embedding)
        return similarities

    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None

    def unload(self) -> None:
        """Unload model from memory"""
        if self.model is not None:
            logger.info("Unloading embedding model")
            self.model = None
            self._dimension = None

    def __repr__(self) -> str:
        status = "loaded" if self.is_loaded() else "not loaded"
        return f"EmbeddingModel(model={self.model_name}, status={status}, dim={self._dimension})"


# Singleton instance
# This is loaded lazily on first use
_embedding_model: Optional[EmbeddingModel] = None


def get_embedding_model() -> EmbeddingModel:
    """
    Get the global embedding model instance

    Returns:
        EmbeddingModel singleton
    """
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = EmbeddingModel()

    return _embedding_model
