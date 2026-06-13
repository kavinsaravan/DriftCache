"""
Cache Store

Stores cached prompt-response pairs.

For Week 2 MVP: Simple in-memory + JSON persistence
For Production: Redis (hot) + PostgreSQL (cold)
"""
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from app.models.cache_schemas import CachedResponse, CacheStats
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheStore:
    """
    Simple cache store for MVP

    Stores CachedResponse objects by cache_id
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize cache store

        Args:
            storage_path: Path to JSON file for persistence
        """
        self.storage_path = storage_path or self._default_storage_path()
        self.cache: Dict[str, CachedResponse] = {}
        self.stats = CacheStats()

        logger.info(f"CacheStore initialized: {self.storage_path}")

    def _default_storage_path(self) -> str:
        """Get default storage path"""
        base_dir = Path(__file__).parent.parent.parent.parent
        storage_dir = base_dir / "data" / "cache"
        storage_dir.mkdir(parents=True, exist_ok=True)
        return str(storage_dir / "responses.json")

    def add(self, response: CachedResponse) -> None:
        """
        Add a cached response

        Args:
            response: CachedResponse to store
        """
        self.cache[response.cache_id] = response
        logger.debug(f"Added cache entry: {response.cache_id}")

    def get(self, cache_id: str) -> Optional[CachedResponse]:
        """
        Get a cached response by ID

        Args:
            cache_id: Cache entry ID

        Returns:
            CachedResponse or None
        """
        response = self.cache.get(cache_id)

        # Check expiration
        if response and response.is_expired():
            logger.debug(f"Cache entry expired: {cache_id}")
            self.delete(cache_id)
            return None

        return response

    def delete(self, cache_id: str) -> None:
        """
        Delete a cached response

        Args:
            cache_id: Cache entry ID
        """
        if cache_id in self.cache:
            del self.cache[cache_id]
            logger.debug(f"Deleted cache entry: {cache_id}")

    def clear(self) -> None:
        """Clear all cached responses"""
        self.cache.clear()
        self.stats = CacheStats()
        logger.info("Cleared all cache entries")

    def clear_expired(self) -> int:
        """
        Clear expired cache entries

        Returns:
            Number of entries cleared
        """
        now = datetime.utcnow()
        expired_ids = [
            cache_id
            for cache_id, response in self.cache.items()
            if response.is_expired()
        ]

        for cache_id in expired_ids:
            self.delete(cache_id)

        if expired_ids:
            logger.info(f"Cleared {len(expired_ids)} expired entries")

        return len(expired_ids)

    def find_by_tenant(self, tenant_id: str) -> List[CachedResponse]:
        """
        Find all cache entries for a tenant

        Args:
            tenant_id: Tenant ID

        Returns:
            List of CachedResponse
        """
        return [
            response
            for response in self.cache.values()
            if response.tenant_id == tenant_id and not response.is_expired()
        ]

    def find_by_model(self, model_name: str) -> List[CachedResponse]:
        """
        Find all cache entries for a model

        Args:
            model_name: Model name

        Returns:
            List of CachedResponse
        """
        return [
            response
            for response in self.cache.values()
            if response.model_name == model_name and not response.is_expired()
        ]

    def count(self) -> int:
        """Get count of cached responses (excluding expired)"""
        return len([r for r in self.cache.values() if not r.is_expired()])

    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        return self.stats

    def record_hit(self, cache_id: str) -> None:
        """
        Record a cache hit

        Args:
            cache_id: Cache entry that was hit
        """
        self.stats.cache_hits += 1
        self.stats.total_requests += 1

        # Increment hit counter on response
        if cache_id in self.cache:
            self.cache[cache_id].increment_hit()

    def record_miss(self, decision_type: str = "general") -> None:
        """
        Record a cache miss

        Args:
            decision_type: Type of miss (threshold, model, expired, etc.)
        """
        self.stats.cache_misses += 1
        self.stats.total_requests += 1

        # Track miss types
        if decision_type == "threshold":
            self.stats.threshold_misses += 1
        elif decision_type == "model":
            self.stats.model_misses += 1
        elif decision_type == "system":
            self.stats.system_misses += 1
        elif decision_type == "expired":
            self.stats.expired_misses += 1

    def save(self, path: Optional[str] = None) -> None:
        """
        Save cache to JSON file

        Args:
            path: Optional custom path
        """
        save_path = path or self.storage_path

        # Convert to serializable format
        data = {
            "version": "1.0",
            "count": len(self.cache),
            "saved_at": datetime.utcnow().isoformat(),
            "stats": self.stats.model_dump(),
            "responses": {
                cache_id: self._serialize_response(response)
                for cache_id, response in self.cache.items()
            }
        }

        # Write to file
        with open(save_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(self.cache)} cache entries to {save_path}")

    def load(self, path: Optional[str] = None) -> None:
        """
        Load cache from JSON file

        Args:
            path: Optional custom path
        """
        load_path = path or self.storage_path

        if not Path(load_path).exists():
            logger.warning(f"Cache file not found: {load_path}")
            return

        # Read from file
        with open(load_path, 'r') as f:
            data = json.load(f)

        # Parse responses
        self.cache = {}
        for cache_id, response_dict in data.get("responses", {}).items():
            response = self._deserialize_response(response_dict)
            # Only load non-expired
            if not response.is_expired():
                self.cache[cache_id] = response

        # Load stats
        if "stats" in data:
            self.stats = CacheStats(**data["stats"])

        logger.info(
            f"Loaded {len(self.cache)} cache entries from {load_path}"
        )

    def _serialize_response(self, response: CachedResponse) -> dict:
        """Convert CachedResponse to dict for JSON"""
        data = response.model_dump()
        # Convert datetimes to ISO format
        if data.get("created_at"):
            data["created_at"] = data["created_at"].isoformat()
        if data.get("expires_at"):
            data["expires_at"] = data["expires_at"].isoformat()
        if data.get("last_accessed"):
            data["last_accessed"] = data["last_accessed"].isoformat()
        return data

    def _deserialize_response(self, data: dict) -> CachedResponse:
        """Convert dict to CachedResponse"""
        # Convert ISO strings back to datetime
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("expires_at") and isinstance(data["expires_at"], str):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        if data.get("last_accessed") and isinstance(data["last_accessed"], str):
            data["last_accessed"] = datetime.fromisoformat(data["last_accessed"])

        return CachedResponse(**data)

    def __len__(self) -> int:
        """Get count of cache entries"""
        return self.count()

    def __repr__(self) -> str:
        return f"CacheStore(entries={self.count()}, path={self.storage_path})"


# Global instance
_cache_store: Optional[CacheStore] = None


def get_cache_store() -> CacheStore:
    """
    Get global cache store instance

    Returns:
        CacheStore singleton
    """
    global _cache_store

    if _cache_store is None:
        _cache_store = CacheStore()
        # Try to load existing cache
        try:
            _cache_store.load()
        except Exception as e:
            logger.warning(f"Could not load existing cache: {e}")

    return _cache_store
