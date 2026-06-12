"""
Metadata Storage

Maps FAISS vector IDs to prompt metadata and responses.

FAISS only stores vectors. We need to store:
- vector_id → prompt_id
- prompt_id → {prompt_text, response_text, metadata}

For MVP: Simple JSON file storage
For Production: PostgreSQL + Redis
"""
import json
import os
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

from app.models.search_schemas import VectorMetadata
from app.core.config import settings

logger = logging.getLogger(__name__)


class MetadataStore:
    """
    Storage for vector metadata

    Maps vector_id (FAISS) → VectorMetadata (prompt, response, etc.)
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize metadata store

        Args:
            storage_path: Path to JSON file for persistence
        """
        self.storage_path = storage_path or self._default_storage_path()
        self.metadata: Dict[int, VectorMetadata] = {}

        logger.info(f"MetadataStore initialized: {self.storage_path}")

    def _default_storage_path(self) -> str:
        """Get default storage path"""
        # Store in project directory
        base_dir = Path(__file__).parent.parent.parent.parent
        storage_dir = base_dir / "data" / "cache"
        storage_dir.mkdir(parents=True, exist_ok=True)
        return str(storage_dir / "metadata.json")

    def add(self, metadata: VectorMetadata) -> None:
        """
        Add metadata for a vector

        Args:
            metadata: Vector metadata to store
        """
        self.metadata[metadata.vector_id] = metadata
        logger.debug(f"Added metadata for vector_id={metadata.vector_id}")

    def add_batch(self, metadata_list: List[VectorMetadata]) -> None:
        """
        Add multiple metadata entries

        Args:
            metadata_list: List of metadata to store
        """
        for metadata in metadata_list:
            self.metadata[metadata.vector_id] = metadata

        logger.info(f"Added {len(metadata_list)} metadata entries")

    def get(self, vector_id: int) -> Optional[VectorMetadata]:
        """
        Get metadata by vector ID

        Args:
            vector_id: FAISS vector ID

        Returns:
            VectorMetadata or None if not found
        """
        return self.metadata.get(vector_id)

    def get_batch(self, vector_ids: List[int]) -> List[Optional[VectorMetadata]]:
        """
        Get multiple metadata entries

        Args:
            vector_ids: List of FAISS vector IDs

        Returns:
            List of VectorMetadata (None for missing IDs)
        """
        return [self.metadata.get(vid) for vid in vector_ids]

    def update(self, vector_id: int, **updates) -> None:
        """
        Update metadata fields

        Args:
            vector_id: Vector ID to update
            **updates: Fields to update
        """
        if vector_id not in self.metadata:
            logger.warning(f"Cannot update missing vector_id={vector_id}")
            return

        metadata = self.metadata[vector_id]

        # Update fields
        for key, value in updates.items():
            if hasattr(metadata, key):
                setattr(metadata, key, value)

        logger.debug(f"Updated vector_id={vector_id}: {updates}")

    def increment_cache_hit(self, vector_id: int) -> None:
        """
        Increment cache hit counter for a vector

        Args:
            vector_id: Vector ID that was reused
        """
        if vector_id in self.metadata:
            self.metadata[vector_id].cache_hits += 1
            self.metadata[vector_id].last_accessed = datetime.utcnow()
            logger.debug(
                f"Cache hit #{self.metadata[vector_id].cache_hits} "
                f"for vector_id={vector_id}"
            )

    def delete(self, vector_id: int) -> None:
        """
        Delete metadata by vector ID

        Args:
            vector_id: Vector ID to delete
        """
        if vector_id in self.metadata:
            del self.metadata[vector_id]
            logger.debug(f"Deleted metadata for vector_id={vector_id}")

    def search_by_prompt_id(self, prompt_id: str) -> Optional[VectorMetadata]:
        """
        Search for metadata by prompt ID (hash)

        Args:
            prompt_id: Prompt hash to search for

        Returns:
            VectorMetadata or None
        """
        for metadata in self.metadata.values():
            if metadata.prompt_id == prompt_id:
                return metadata
        return None

    def get_all(self) -> List[VectorMetadata]:
        """
        Get all metadata entries

        Returns:
            List of all VectorMetadata
        """
        return list(self.metadata.values())

    def count(self) -> int:
        """Get count of stored metadata"""
        return len(self.metadata)

    def save(self, path: Optional[str] = None) -> None:
        """
        Save metadata to JSON file

        Args:
            path: Optional custom path (defaults to self.storage_path)
        """
        save_path = path or self.storage_path

        # Create directory if needed
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Convert to serializable format
        data = {
            "version": "1.0",
            "count": len(self.metadata),
            "saved_at": datetime.utcnow().isoformat(),
            "metadata": {
                str(vid): meta.to_dict()
                for vid, meta in self.metadata.items()
            }
        }

        # Write to file
        with open(save_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(
            f"Saved {len(self.metadata)} metadata entries to {save_path}"
        )

    def load(self, path: Optional[str] = None) -> None:
        """
        Load metadata from JSON file

        Args:
            path: Optional custom path (defaults to self.storage_path)
        """
        load_path = path or self.storage_path

        if not os.path.exists(load_path):
            logger.warning(f"Metadata file not found: {load_path}")
            return

        # Read from file
        with open(load_path, 'r') as f:
            data = json.load(f)

        # Parse metadata
        self.metadata = {}
        for vid_str, meta_dict in data.get("metadata", {}).items():
            vector_id = int(vid_str)
            metadata = VectorMetadata.from_dict(meta_dict)
            self.metadata[vector_id] = metadata

        logger.info(
            f"Loaded {len(self.metadata)} metadata entries from {load_path}"
        )

    def clear(self) -> None:
        """Clear all metadata"""
        self.metadata.clear()
        logger.info("Cleared all metadata")

    def get_stats(self) -> dict:
        """
        Get statistics about stored metadata

        Returns:
            Dictionary with stats
        """
        if not self.metadata:
            return {
                "total_entries": 0,
                "total_cache_hits": 0,
                "average_cache_hits": 0.0,
                "models_used": [],
            }

        cache_hits = [m.cache_hits for m in self.metadata.values()]
        models = set(m.model_name for m in self.metadata.values())

        return {
            "total_entries": len(self.metadata),
            "total_cache_hits": sum(cache_hits),
            "average_cache_hits": sum(cache_hits) / len(cache_hits),
            "max_cache_hits": max(cache_hits) if cache_hits else 0,
            "models_used": list(models),
        }

    def __len__(self) -> int:
        """Get count of metadata entries"""
        return len(self.metadata)

    def __repr__(self) -> str:
        return f"MetadataStore(entries={len(self.metadata)}, path={self.storage_path})"


# Global instance
_metadata_store: Optional[MetadataStore] = None


def get_metadata_store() -> MetadataStore:
    """
    Get global metadata store instance

    Returns:
        MetadataStore singleton
    """
    global _metadata_store

    if _metadata_store is None:
        _metadata_store = MetadataStore()
        # Try to load existing metadata
        try:
            _metadata_store.load()
        except Exception as e:
            logger.warning(f"Could not load existing metadata: {e}")

    return _metadata_store
