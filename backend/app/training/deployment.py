"""Runtime deployment and cross-worker activation for embedding models."""

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings
from app.embeddings.model import EmbeddingModel, set_embedding_model
from app.vectorstore.search import get_search_service


_loaded_deployment: str | None = None
_deployment_lock = threading.RLock()


@dataclass(frozen=True)
class DeploymentResult:
    model_name: str
    dimension: int
    rebuilt_vectors: int
    previous_model_name: str


def _marker_path() -> str:
    return f"{settings.get_metadata_path()}.deployment.json"


def _write_marker(model_name: str, dimension: int) -> str:
    global _loaded_deployment
    marker_path = _marker_path()
    temporary_path = f"{marker_path}.saving"
    deployed_at = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(marker_path) or ".", exist_ok=True)
    with open(temporary_path, "w") as marker_file:
        json.dump(
            {
                "model_name": model_name,
                "dimension": dimension,
                "deployed_at": deployed_at,
            },
            marker_file,
        )
        marker_file.flush()
        os.fsync(marker_file.fileno())
    os.replace(temporary_path, marker_path)
    _loaded_deployment = deployed_at
    return deployed_at


def deploy_embedding_model(model_name: str) -> DeploymentResult:
    """Load a candidate model and rebuild FAISS before switching live traffic."""
    with _deployment_lock:
        service = get_search_service()
        previous_model_name = service.embedding_service.model.model_name
        candidate = EmbeddingModel(model_name=model_name)
        candidate.load()
        rebuilt_vectors = service.rebuild_with_embedding_model(candidate)
        _write_marker(candidate.model_name, candidate.dimension)
        return DeploymentResult(
            model_name=candidate.model_name,
            dimension=candidate.dimension,
            rebuilt_vectors=rebuilt_vectors,
            previous_model_name=previous_model_name,
        )


def refresh_deployed_model() -> bool:
    """Reload a deployment performed by another worker from shared storage."""
    global _loaded_deployment
    with _deployment_lock:
        marker_path = _marker_path()
        if not os.path.exists(marker_path):
            return False

        with open(marker_path) as marker_file:
            marker = json.load(marker_file)

        service = get_search_service()
        if _loaded_deployment == marker["deployed_at"]:
            return False

        candidate = EmbeddingModel(model_name=marker["model_name"])
        candidate.load()
        service.faiss_index.dimension = candidate.dimension
        service.load_index()
        service.embedding_service.model = candidate
        set_embedding_model(candidate)
        settings.EMBEDDING_MODEL = candidate.model_name
        settings.EMBEDDING_DIMENSION = candidate.dimension
        _loaded_deployment = marker["deployed_at"]
        return True
