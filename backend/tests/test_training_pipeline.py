from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import HTTPException
from sentence_transformers import InputExample
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.endpoints.training import require_training_enabled
from app.core.config import settings
from app.database.base import Base, import_models
from app.models.model_version import ModelVersion
from app.models.search_schemas import VectorMetadata
from app.models.training_job import JobStatus, TrainingJob
from app.models.training_pair import PairType, TrainingPair
from app.models.training_schemas import TrainingConfig
from app.training import trainer as trainer_module
from app.training.trainer import ContrastiveTrainer, TrainingJobManager
from app.vectorstore.faiss_index import FAISSIndex
from app.vectorstore.search import SemanticSearchService
from app.vectorstore.storage import MetadataStore


def make_session():
    import_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_pair_evaluation_populates_quality_metrics():
    trainer = object.__new__(ContrastiveTrainer)

    class FakeModel:
        def encode(self, texts, **kwargs):
            vectors = {
                "same-a": [1.0, 0.0],
                "same-b": [1.0, 0.0],
                "other-a": [1.0, 0.0],
                "other-b": [0.0, 1.0],
            }
            return np.asarray([vectors[text] for text in texts], dtype=np.float32)

    trainer.model = FakeModel()
    metrics = trainer.evaluate(
        [
            InputExample(texts=["same-a", "same-b"], label=1.0),
            InputExample(texts=["other-a", "other-b"], label=0.0),
        ],
        threshold=0.85,
    )

    assert metrics["mean_squared_error"] == 0.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0


def test_training_data_uses_disjoint_validation_split():
    pairs = [
        TrainingPair(anchor_text=f"p{i}", comparison_text=f"p{i}-match", pair_type=PairType.POSITIVE)
        for i in range(5)
    ] + [
        TrainingPair(anchor_text=f"n{i}", comparison_text=f"n{i}-other", pair_type=PairType.HARD_NEGATIVE)
        for i in range(3)
    ]

    class FakeQuery:
        def all(self):
            return pairs

    trainer = object.__new__(ContrastiveTrainer)
    trainer.model = SimpleNamespace(max_seq_length=None)
    train_loader, validation = trainer.prepare_training_data(
        db=SimpleNamespace(query=lambda model: FakeQuery()),
        loss_function="MultipleNegativesRankingLoss",
        validation_split=0.2,
        random_seed=7,
    )

    training_texts = {tuple(example.texts) for example in train_loader.dataset}
    validation_texts = {tuple(example.texts) for example in validation}
    assert training_texts.isdisjoint(validation_texts)
    assert all(example.label == 1.0 for example in train_loader.dataset)
    assert any(example.label == 0.0 for example in validation)


def test_completed_training_job_registers_model_version(monkeypatch):
    db = make_session()
    db.add_all(
        [
            TrainingPair(anchor_text="a", comparison_text="a2", pair_type=PairType.POSITIVE),
            TrainingPair(anchor_text="b", comparison_text="b2", pair_type=PairType.POSITIVE),
            TrainingPair(anchor_text="c", comparison_text="c2", pair_type=PairType.POSITIVE),
        ]
    )
    db.commit()
    manager = TrainingJobManager(db)
    job = manager.create_training_job(
        base_model="base-model",
        config=TrainingConfig(),
        output_model_name="trained-model",
    )

    class FakeTrainer:
        def __init__(self, **kwargs):
            self.model = SimpleNamespace(get_sentence_embedding_dimension=lambda: 384)

        def prepare_training_data(self, **kwargs):
            return object(), [InputExample(texts=["a", "a2"], label=1.0)]

        def train(self, **kwargs):
            return {
                "training_time_seconds": 2.5,
                "final_loss": 0.04,
                "eval_metrics": {"precision": 0.9, "recall": 0.8},
            }

    monkeypatch.setattr(trainer_module, "ContrastiveTrainer", FakeTrainer)
    monkeypatch.setattr(trainer_module.os, "makedirs", lambda *args, **kwargs: None)

    completed = manager.run_training_job(job.job_id)
    version = db.query(ModelVersion).filter_by(training_job_id=job.job_id).one()

    assert completed.status == JobStatus.COMPLETED
    assert completed.final_loss == 0.04
    assert completed.eval_metrics["precision"] == 0.9
    assert version.dimension == 384
    assert version.performance_metrics == completed.eval_metrics


def test_model_cutover_rebuilds_vectors_and_preserves_ids(monkeypatch, tmp_path):
    index = FAISSIndex(dimension=2, index_type="Flat")
    index.create_index()
    index.add_vectors(
        np.asarray([[1.0, 0.0]], dtype=np.float32),
        ids=np.asarray([7], dtype=np.int64),
    )
    store = MetadataStore(str(tmp_path / "metadata.json"))
    store.add(
        VectorMetadata(
            vector_id=7,
            prompt_id="prompt-7",
            prompt_text="hello",
            response_text="world",
            model_name="provider-model",
            embedding_model="old-model",
            cache_key_hash="redis-key",
            timestamp=datetime.utcnow(),
        )
    )
    service = object.__new__(SemanticSearchService)
    service.faiss_index = index
    service.metadata_store = store
    service.embedding_service = SimpleNamespace(model=SimpleNamespace(model_name="old-model"))

    class CandidateModel:
        model_name = "new-model"
        dimension = 3

        def encode(self, texts, **kwargs):
            return np.asarray([[0.0, 1.0, 0.0] for _ in texts], dtype=np.float32)

    monkeypatch.setattr(type(settings), "get_index_path", lambda self: str(tmp_path / "faiss.index"))
    monkeypatch.setattr(type(settings), "get_metadata_path", lambda self: str(tmp_path / "metadata.json"))
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "old-model")
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 2)

    rebuilt = service.rebuild_with_embedding_model(CandidateModel())

    assert rebuilt == 1
    assert service.faiss_index.dimension == 3
    assert service.metadata_store.get(7).cache_key_hash == "redis-key"
    assert service.metadata_store.get(7).embedding_model == "new-model"
    new_id = service.faiss_index.add_vectors(np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32))[0]
    assert new_id == 8
    assert (tmp_path / "faiss.index").exists()


def test_training_flag_disables_training_api(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_TRAINING", False)
    with pytest.raises(HTTPException) as exc_info:
        require_training_enabled()
    assert exc_info.value.status_code == 503
