"""
FAISS Index Manager

Manages the FAISS vector index for fast similarity search.

FAISS (Facebook AI Similarity Search) enables:
- Sub-millisecond k-NN search
- Efficient memory usage
- Scalable to millions of vectors
"""
import os
import logging
from typing import List, Optional, Tuple
import numpy as np
import faiss

from app.core.config import settings

logger = logging.getLogger(__name__)


class FAISSIndex:
    """
    FAISS index manager

    Handles creation, indexing, searching, and persistence of FAISS index
    """

    def __init__(
        self,
        dimension: int,
        index_type: str = "Flat",
        metric: str = "L2"
    ):
        """
        Initialize FAISS index

        Args:
            dimension: Vector dimension (e.g., 384 for all-MiniLM-L6-v2)
            index_type: Index type (Flat, IVF, HNSW)
            metric: Distance metric (L2 or IP for inner product)
        """
        self.dimension = dimension
        self.index_type = index_type
        self.metric = metric
        self.index: Optional[faiss.Index] = None
        self._next_id = 0

        logger.info(
            f"Initializing FAISS index: dim={dimension}, "
            f"type={index_type}, metric={metric}"
        )

    def create_index(self) -> None:
        """
        Create a new FAISS index

        For MVP, we use IndexFlatL2 (exact search, no training needed)
        """
        if self.index_type.lower() == "flat":
            # Exact search using L2 distance
            self.index = faiss.IndexFlatL2(self.dimension)
            logger.info("Created IndexFlatL2 (exact search)")

        elif self.index_type.lower() == "ivf":
            # Inverted File Index (faster, approximate)
            # Requires training
            quantizer = faiss.IndexFlatL2(self.dimension)
            nlist = 100  # Number of clusters
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, nlist)
            logger.info(f"Created IndexIVFFlat with {nlist} clusters")

        elif self.index_type.lower() == "hnsw":
            # Hierarchical Navigable Small World (very fast, approximate)
            M = 32  # Number of connections per vertex
            self.index = faiss.IndexHNSWFlat(self.dimension, M)
            logger.info(f"Created IndexHNSWFlat with M={M}")

        else:
            raise ValueError(f"Unknown index type: {self.index_type}")

    def add_vectors(
        self,
        vectors: np.ndarray,
        ids: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Add vectors to the index

        Args:
            vectors: Array of vectors [n_vectors, dimension]
            ids: Optional array of IDs [n_vectors]

        Returns:
            Array of assigned IDs
        """
        if self.index is None:
            self.create_index()

        # Ensure correct dtype
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)

        # Normalize vectors for cosine similarity
        # After normalization, L2 distance approximates cosine distance
        faiss.normalize_L2(vectors)

        n_vectors = vectors.shape[0]

        # Auto-generate IDs if not provided
        if ids is None:
            ids = np.arange(self._next_id, self._next_id + n_vectors, dtype=np.int64)
            self._next_id += n_vectors

        # Add to index
        self.index.add(vectors)

        logger.info(f"Added {n_vectors} vectors to index (total: {self.index.ntotal})")

        return ids

    def search(
        self,
        query_vectors: np.ndarray,
        k: int = 5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Search for k nearest neighbors

        Args:
            query_vectors: Query vectors [n_queries, dimension]
            k: Number of neighbors to return

        Returns:
            distances: L2 distances [n_queries, k]
            indices: Vector indices [n_queries, k]
        """
        if self.index is None:
            raise ValueError("Index not created. Call create_index() first.")

        if self.index.ntotal == 0:
            logger.warning("Searching empty index")
            n_queries = query_vectors.shape[0]
            return np.full((n_queries, k), float('inf')), np.full((n_queries, k), -1)

        # Ensure correct dtype
        if query_vectors.dtype != np.float32:
            query_vectors = query_vectors.astype(np.float32)

        # Normalize query vectors
        faiss.normalize_L2(query_vectors)

        # Adjust k if larger than index size
        actual_k = min(k, self.index.ntotal)

        # Search
        distances, indices = self.index.search(query_vectors, actual_k)

        logger.debug(
            f"Searched {query_vectors.shape[0]} queries, "
            f"k={actual_k}, found {indices.shape[1]} results"
        )

        return distances, indices

    def search_single(
        self,
        query_vector: np.ndarray,
        k: int = 5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Search for k nearest neighbors (single query)

        Args:
            query_vector: Single query vector [dimension]
            k: Number of neighbors to return

        Returns:
            distances: L2 distances [k]
            indices: Vector indices [k]
        """
        # Reshape to [1, dimension]
        query_vectors = query_vector.reshape(1, -1)

        # Search
        distances, indices = self.search(query_vectors, k)

        # Return flattened results
        return distances[0], indices[0]

    def remove_vectors(self, ids: np.ndarray) -> None:
        """
        Remove vectors from index

        Note: Not all FAISS index types support removal
        IndexFlatL2 does NOT support removal
        """
        if not hasattr(self.index, 'remove_ids'):
            logger.warning(f"{self.index_type} does not support removal")
            return

        self.index.remove_ids(ids)
        logger.info(f"Removed {len(ids)} vectors from index")

    def save(self, path: str) -> None:
        """
        Save index to disk

        Args:
            path: Path to save index file
        """
        if self.index is None:
            raise ValueError("No index to save")

        # Create directory if needed
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Save index
        faiss.write_index(self.index, path)

        logger.info(f"Saved FAISS index to {path} ({self.index.ntotal} vectors)")

    def load(self, path: str) -> None:
        """
        Load index from disk

        Args:
            path: Path to index file
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Index file not found: {path}")

        # Load index
        self.index = faiss.read_index(path)

        # Update next_id based on index size
        self._next_id = self.index.ntotal

        logger.info(
            f"Loaded FAISS index from {path} "
            f"({self.index.ntotal} vectors, dim={self.dimension})"
        )

    def get_stats(self) -> dict:
        """
        Get index statistics

        Returns:
            Dictionary with index stats
        """
        if self.index is None:
            return {
                "total_vectors": 0,
                "dimension": self.dimension,
                "index_type": self.index_type,
                "is_trained": False
            }

        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "index_type": self.index_type,
            "is_trained": getattr(self.index, 'is_trained', True),
            "metric": self.metric
        }

    def reset(self) -> None:
        """Reset index (clear all vectors)"""
        if self.index is not None:
            self.index.reset()
            self._next_id = 0
            logger.info("Reset FAISS index")

    @staticmethod
    def distance_to_similarity(distance: float) -> float:
        """
        Convert L2 distance to cosine similarity

        For normalized vectors:
        L2_distance² = 2 * (1 - cosine_similarity)

        So:
        cosine_similarity = 1 - (L2_distance² / 2)

        Args:
            distance: L2 distance

        Returns:
            Cosine similarity [0, 1]
        """
        # Clamp distance to valid range
        distance = max(0.0, distance)

        # Convert to similarity
        similarity = 1.0 - (distance ** 2 / 2.0)

        # Clamp to [0, 1]
        return max(0.0, min(1.0, similarity))

    def __len__(self) -> int:
        """Get number of vectors in index"""
        if self.index is None:
            return 0
        return self.index.ntotal

    def __repr__(self) -> str:
        vectors = len(self) if self.index else 0
        return f"FAISSIndex(type={self.index_type}, dim={self.dimension}, vectors={vectors})"


# Global instance
_faiss_index: Optional[FAISSIndex] = None


def get_faiss_index(dimension: Optional[int] = None) -> FAISSIndex:
    """
    Get global FAISS index instance

    Args:
        dimension: Vector dimension (defaults to settings)

    Returns:
        FAISSIndex singleton
    """
    global _faiss_index

    if _faiss_index is None:
        dim = dimension or settings.EMBEDDING_DIMENSION
        index_type = settings.VECTOR_INDEX_TYPE
        _faiss_index = FAISSIndex(dimension=dim, index_type=index_type)
        _faiss_index.create_index()

    return _faiss_index
