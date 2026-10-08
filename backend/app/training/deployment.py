"""Runtime deployment for fine-tuned embedding models."""

from dataclasses import dataclass

from app.embeddings.model import EmbeddingModel
from app.vectorstore.search import get_search_service


@dataclass(frozen=True)
class DeploymentResult:
    model_name: str
    dimension: int
    rebuilt_vectors: int


def deploy_embedding_model(model_name: str) -> DeploymentResult:
    """Load a candidate model and rebuild FAISS before switching live traffic."""
    candidate = EmbeddingModel(model_name=model_name)
    candidate.load()
    rebuilt_vectors = get_search_service().rebuild_with_embedding_model(candidate)
    return DeploymentResult(
        model_name=candidate.model_name,
        dimension=candidate.dimension,
        rebuilt_vectors=rebuilt_vectors,
    )
