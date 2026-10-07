"""Operational maintenance for the live FAISS index."""

from __future__ import annotations

import os
import tempfile
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np

from app.core.config import settings
from app.vectorstore.faiss_index import FAISSIndex
from app.vectorstore.search import SemanticSearchService, get_search_service


class IndexMaintenanceService:
    """Inspect and rebuild the index used by ``SemanticSearchService``."""

    _lock = threading.RLock()

    def __init__(self, search_service: Optional[SemanticSearchService] = None):
        self.search_service = search_service or get_search_service()

    def get_stats(
        self,
        tenant_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        ttl = ttl_seconds or settings.CACHE_TTL_SECONDS
        now = datetime.utcnow()
        all_metadata = self.search_service.metadata_store.get_all()
        metadata = [
            m for m in all_metadata if not tenant_id or m.tenant_id == tenant_id
        ]
        stale = [m for m in metadata if (now - m.timestamp).total_seconds() > ttl]
        vector_count = len(self.search_service.faiss_index)
        metadata_count = len(all_metadata)

        if tenant_id:
            visible_vector_count = len(metadata)
            orphaned_vectors = 0
            missing_vectors = 0
        else:
            visible_vector_count = vector_count
            orphaned_vectors = max(vector_count - metadata_count, 0)
            missing_vectors = max(metadata_count - vector_count, 0)

        stale_ratio = len(stale) / len(metadata) if metadata else 0.0
        inconsistent = orphaned_vectors > 0 or missing_vectors > 0
        if inconsistent or stale_ratio >= 0.5:
            status = "critical"
        elif stale_ratio >= 0.2:
            status = "degraded"
        else:
            status = "healthy"

        index_path = settings.get_index_path()
        index_age_hours = None
        index_size_bytes = 0
        if os.path.exists(index_path):
            index_age_hours = max(
                0.0, (time.time() - os.path.getmtime(index_path)) / 3600
            )
            index_size_bytes = os.path.getsize(index_path)

        return {
            "status": status,
            "vector_count": visible_vector_count,
            "total_vector_count": vector_count,
            "metadata_count": len(metadata),
            "active_vector_count": len(metadata) - len(stale),
            "stale_vector_count": len(stale),
            "stale_vector_ratio": stale_ratio,
            "orphaned_vector_count": orphaned_vectors,
            "missing_vector_count": missing_vectors,
            "dimension": self.search_service.faiss_index.dimension,
            "index_type": self.search_service.faiss_index.index_type,
            "index_age_hours": index_age_hours,
            "index_size_bytes": index_size_bytes,
            "tenant_id": tenant_id,
            "measured_at": now.isoformat(),
        }

    def rebuild(
        self,
        *,
        dry_run: bool = True,
        ttl_seconds: Optional[int] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Re-embed active entries and atomically replace the persisted index files.

        FAISS is shared by all tenants, so a rebuild always preserves active entries
        from every tenant. ``tenant_id`` is retained in the response for callers that
        initiated maintenance from a tenant-scoped workflow.
        """
        started = time.perf_counter()
        ttl = ttl_seconds or settings.CACHE_TTL_SECONDS
        now = datetime.utcnow()
        metadata = self.search_service.metadata_store.get_all()
        active = [m for m in metadata if (now - m.timestamp).total_seconds() <= ttl]
        active.sort(key=lambda item: item.vector_id)
        stale_count = len(metadata) - len(active)
        old_count = len(self.search_service.faiss_index)

        result = {
            "status": "preview" if dry_run else "completed",
            "dry_run": dry_run,
            "old_vector_count": old_count,
            "new_vector_count": len(active),
            "vectors_reembedded": len(active),
            "vectors_removed": stale_count,
            "tenant_id": tenant_id,
            "validation_passed": old_count == len(metadata),
        }
        if dry_run:
            result["duration_ms"] = (time.perf_counter() - started) * 1000
            return result

        with self._lock:
            candidate = FAISSIndex(
                dimension=self.search_service.faiss_index.dimension,
                index_type="Flat",
                metric=self.search_service.faiss_index.metric,
            )
            candidate.create_index()

            if active:
                batch = self.search_service.embedding_service.embed_batch(
                    [item.prompt_text for item in active]
                )
                vectors = np.asarray(
                    [item.vector for item in batch.embeddings], dtype=np.float32
                )
                ids = np.asarray([item.vector_id for item in active], dtype=np.int64)
                candidate.add_vectors(vectors, ids=ids)
                candidate._next_id = int(ids.max()) + 1

            if len(candidate) != len(active):
                raise RuntimeError(
                    "Rebuilt FAISS index and metadata counts do not match"
                )

            index_path = settings.get_index_path()
            metadata_path = self.search_service.metadata_store.storage_path
            index_dir = os.path.dirname(index_path)
            metadata_dir = os.path.dirname(metadata_path)
            os.makedirs(index_dir, exist_ok=True)
            os.makedirs(metadata_dir, exist_ok=True)

            previous_metadata = self.search_service.metadata_store.metadata
            self.search_service.metadata_store.metadata = {
                item.vector_id: item for item in active
            }
            index_tmp = tempfile.NamedTemporaryFile(
                dir=index_dir, suffix=".index", delete=False
            )
            metadata_tmp = tempfile.NamedTemporaryFile(
                dir=metadata_dir, suffix=".json", delete=False
            )
            index_tmp.close()
            metadata_tmp.close()
            try:
                candidate.save(index_tmp.name)
                self.search_service.metadata_store.save(metadata_tmp.name)
                os.replace(index_tmp.name, index_path)
                os.replace(metadata_tmp.name, metadata_path)
            except Exception:
                self.search_service.metadata_store.metadata = previous_metadata
                for path in (index_tmp.name, metadata_tmp.name):
                    if os.path.exists(path):
                        os.unlink(path)
                raise

            live_index = self.search_service.faiss_index
            live_index.index = candidate.index
            live_index.index_type = candidate.index_type
            live_index._next_id = candidate._next_id

        result["validation_passed"] = len(self.search_service.faiss_index) == len(
            active
        )
        result["duration_ms"] = (time.perf_counter() - started) * 1000
        return result
