"""Load labeled prompt groups for similarity-threshold evaluation."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.embeddings.service import EmbeddingService, get_embedding_service
from app.embeddings.utils import cosine_similarity, list_to_vector

logger = logging.getLogger(__name__)
DATASETS_DIR = Path(__file__).parents[3] / "datasets"


def load_threshold_evaluation_pairs(
    dataset_paths: Optional[List[str]] = None,
    embedding_service: Optional[EmbeddingService] = None,
) -> List[Dict[str, Any]]:
    """Load canonical labeled groups and compute pairwise similarities.

    The function intentionally does not cache results: callers receive values
    computed with the currently configured embedding model.
    """
    paths = (
        [Path(path) for path in dataset_paths]
        if dataset_paths
        else [
            DATASETS_DIR / "semantic_duplicates.json",
            DATASETS_DIR / "hard_negatives.json",
        ]
    )

    groups = []
    for path in paths:
        try:
            with path.open() as file:
                data = json.load(file)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Evaluation dataset not found: {path}") from exc
        for group in data.get("prompt_groups", []):
            groups.append(
                {
                    "prompts": group["prompts"],
                    "should_cache": group["expected_behavior"] == "should_match",
                }
            )

    if not groups:
        raise ValueError(
            "No labeled prompt groups were found in the evaluation datasets"
        )

    service = embedding_service or get_embedding_service()
    pairs: List[Dict[str, Any]] = []
    for group in groups:
        prompts = group["prompts"]
        for first in range(len(prompts)):
            for second in range(first + 1, min(first + 3, len(prompts))):
                embedding_a = service.embed_text(prompts[first])
                embedding_b = service.embed_text(prompts[second])
                similarity = float(
                    cosine_similarity(
                        list_to_vector(embedding_a.vector),
                        list_to_vector(embedding_b.vector),
                    )
                )
                pairs.append(
                    {
                        "similarity": similarity,
                        "should_cache": group["should_cache"],
                        "prompt1": prompts[first],
                        "prompt2": prompts[second],
                    }
                )

    logger.info("Loaded %d threshold evaluation pairs", len(pairs))
    return pairs
