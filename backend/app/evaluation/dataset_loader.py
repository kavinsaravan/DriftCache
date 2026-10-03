"""
Dataset Loader for Threshold Optimization

Loads labeled datasets and computes similarities for threshold evaluation.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np

from app.embeddings.service import get_embedding_service
from app.embeddings.utils import cosine_similarity, list_to_vector

logger = logging.getLogger(__name__)


def load_evaluation_dataset(
    dataset_paths: List[str] = None,
    min_pairs_per_type: int = 50
) -> List[Dict[str, Any]]:
    """
    Load and compute evaluation dataset from labeled prompt pairs

    Args:
        dataset_paths: Paths to dataset JSON files. Defaults to built-in datasets.
        min_pairs_per_type: Minimum number of positive/negative pairs to generate

    Returns:
        List of {similarity: float, should_cache: bool} dicts
    """
    # Default to built-in datasets
    if dataset_paths is None:
        base_path = Path(__file__).parent.parent.parent / "benchmarks" / "datasets"
        dataset_paths = [
            str(base_path / "semantic_duplicates.json"),
            str(base_path / "hard_negatives.json"),
        ]

    logger.info(f"Loading evaluation datasets from {len(dataset_paths)} files")

    # Load all datasets
    all_groups = []
    for path in dataset_paths:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                for group in data.get("prompt_groups", []):
                    all_groups.append({
                        "prompts": group["prompts"],
                        "should_match": group["expected_behavior"] == "should_match"
                    })
        except FileNotFoundError:
            logger.warning(f"Dataset file not found: {path}")
            continue
        except Exception as e:
            logger.error(f"Error loading dataset {path}: {e}")
            continue

    if not all_groups:
        logger.error("No datasets loaded, returning empty evaluation set")
        return []

    logger.info(f"Loaded {len(all_groups)} prompt groups")

    # Generate prompt pairs and compute similarities
    embedding_service = get_embedding_service()
    evaluation_pairs = []

    positive_pairs = 0
    negative_pairs = 0

    for group in all_groups:
        prompts = group["prompts"]
        should_match = group["should_match"]

        # Generate pairs within this group
        for i in range(len(prompts)):
            for j in range(i + 1, min(i + 3, len(prompts))):  # Limit pairs per group
                # Compute embeddings
                try:
                    emb1 = embedding_service.embed_text(prompts[i])
                    emb2 = embedding_service.embed_text(prompts[j])

                    # Compute similarity
                    vec1 = list_to_vector(emb1.vector)
                    vec2 = list_to_vector(emb2.vector)
                    similarity = float(cosine_similarity(vec1, vec2))

                    evaluation_pairs.append({
                        "similarity": similarity,
                        "should_cache": should_match,
                        "prompt1": prompts[i],
                        "prompt2": prompts[j],
                    })

                    if should_match:
                        positive_pairs += 1
                    else:
                        negative_pairs += 1

                except Exception as e:
                    logger.error(f"Error computing similarity: {e}")
                    continue

    logger.info(
        f"Generated {len(evaluation_pairs)} evaluation pairs: "
        f"{positive_pairs} positive (should match), "
        f"{negative_pairs} negative (should not match)"
    )

    # Log some statistics
    if evaluation_pairs:
        similarities = [p["similarity"] for p in evaluation_pairs]
        positive_sims = [p["similarity"] for p in evaluation_pairs if p["should_cache"]]
        negative_sims = [p["similarity"] for p in evaluation_pairs if not p["should_cache"]]

        logger.info(f"Similarity distribution:")
        logger.info(f"  All pairs: min={min(similarities):.3f}, max={max(similarities):.3f}, mean={np.mean(similarities):.3f}")
        if positive_sims:
            logger.info(f"  Positive pairs: min={min(positive_sims):.3f}, max={max(positive_sims):.3f}, mean={np.mean(positive_sims):.3f}")
        if negative_sims:
            logger.info(f"  Negative pairs: min={min(negative_sims):.3f}, max={max(negative_sims):.3f}, mean={np.mean(negative_sims):.3f}")

    return evaluation_pairs


def get_cached_evaluation_dataset(cache_ttl_seconds: int = 300) -> List[Dict[str, Any]]:
    """
    Get evaluation dataset with caching to avoid recomputing embeddings

    Args:
        cache_ttl_seconds: How long to cache the dataset

    Returns:
        Cached or freshly computed evaluation dataset
    """
    # TODO: Implement caching using Redis or a global variable with timestamp
    # For now, just return fresh data
    return load_evaluation_dataset()
