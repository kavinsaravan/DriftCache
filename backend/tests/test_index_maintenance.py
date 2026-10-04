from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np

from app.core.config import settings
from app.models.search_schemas import VectorMetadata
from app.services.index_maintenance import IndexMaintenanceService
from app.vectorstore.faiss_index import FAISSIndex
from app.vectorstore.storage import MetadataStore


class FakeEmbeddingService:
    def embed_batch(self, texts):
        embeddings = [
            SimpleNamespace(vector=[float(index + 1), 1.0])
            for index, _ in enumerate(texts)
        ]
        return SimpleNamespace(embeddings=embeddings)


def test_rebuild_removes_expired_entries_and_persists(monkeypatch, tmp_path):
    index = FAISSIndex(dimension=2, index_type="Flat")
    index.create_index()
    index.add_vectors(
        np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        ids=np.asarray([5, 8], dtype=np.int64),
    )

    metadata_path = tmp_path / "metadata.json"
    store = MetadataStore(str(metadata_path))
    now = datetime.utcnow()
    for vector_id, timestamp in ((5, now), (8, now - timedelta(hours=2))):
        store.add(
            VectorMetadata(
                vector_id=vector_id,
                prompt_id=str(vector_id),
                prompt_text=f"prompt {vector_id}",
                response_text="response",
                model_name="model",
                embedding_model="embedding",
                timestamp=timestamp,
            )
        )

    search_service = SimpleNamespace(
        faiss_index=index,
        metadata_store=store,
        embedding_service=FakeEmbeddingService(),
    )
    monkeypatch.setattr(
        type(settings),
        "get_index_path",
        lambda self: str(tmp_path / "faiss.index"),
    )

    service = IndexMaintenanceService(search_service)
    preview = service.rebuild(dry_run=True, ttl_seconds=3600)
    assert preview["new_vector_count"] == 1
    assert preview["vectors_removed"] == 1
    assert len(index) == 2

    result = service.rebuild(dry_run=False, ttl_seconds=3600)
    assert result["validation_passed"] is True
    assert len(index) == 1
    assert list(store.metadata) == [5]
    assert (tmp_path / "faiss.index").exists()
    assert metadata_path.exists()


def test_stats_report_count_mismatch(tmp_path, monkeypatch):
    index = FAISSIndex(dimension=2, index_type="Flat")
    index.create_index()
    index.add_vectors(np.asarray([[1.0, 0.0]], dtype=np.float32))
    store = MetadataStore(str(tmp_path / "metadata.json"))
    search_service = SimpleNamespace(faiss_index=index, metadata_store=store)
    monkeypatch.setattr(
        type(settings),
        "get_index_path",
        lambda self: str(tmp_path / "missing.index"),
    )

    stats = IndexMaintenanceService(search_service).get_stats()
    assert stats["status"] == "critical"
    assert stats["orphaned_vector_count"] == 1
