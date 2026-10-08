"""Build fine-tuning pairs from labeled fixtures and observed cache matches."""

import json
import logging
import random
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
from sqlalchemy.orm import Session

from app.embeddings.service import get_embedding_service
from app.models.cache_entry import CacheEntry
from app.models.cache_event import CacheEvent, CacheStatus
from app.models.request import Request
from app.models.training_pair import PairType, TrainingPair


logger = logging.getLogger(__name__)
DATASETS_DIR = Path(__file__).parents[3] / "datasets"


class TrainingDataGenerator:
    """Create labeled pairs without treating model predictions as truth."""

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = get_embedding_service()

    @staticmethod
    def _pair_key(anchor: str, comparison: str, pair_type: PairType) -> tuple[str, str, str]:
        texts = sorted((" ".join(anchor.lower().split()), " ".join(comparison.lower().split())))
        return texts[0], texts[1], pair_type.value

    @staticmethod
    def _load_groups(filename: str) -> list[dict]:
        with (DATASETS_DIR / filename).open() as dataset_file:
            return json.load(dataset_file)["prompt_groups"]

    def _similarities(self, text_pairs: Iterable[tuple[str, str]]) -> list[float]:
        pairs = list(text_pairs)
        if not pairs:
            return []
        unique_texts = list(dict.fromkeys(text for pair in pairs for text in pair))
        batch = self.embedding_service.embed_batch(unique_texts)
        vectors = {
            text: np.asarray(embedding.vector, dtype=np.float32)
            for text, embedding in zip(unique_texts, batch.embeddings)
        }
        return [float(np.dot(vectors[first], vectors[second])) for first, second in pairs]

    def _observed_positive_pairs(
        self,
        limit: int,
        similarity_threshold: float,
        days_lookback: int,
    ) -> list[TrainingPair]:
        """Capture real matches for review, without marking them as validated."""
        cutoff = datetime.utcnow() - timedelta(days=days_lookback)
        rows = (
            self.db.query(Request, CacheEntry, CacheEvent.similarity_score)
            .join(CacheEvent, CacheEvent.request_id == Request.request_id)
            .join(CacheEntry, CacheEntry.cache_id == CacheEvent.matched_cache_id)
            .filter(
                CacheEvent.cache_status == CacheStatus.HIT,
                CacheEvent.created_at >= cutoff,
                CacheEvent.similarity_score >= similarity_threshold,
                Request.prompt_hash != CacheEntry.prompt_hash,
            )
            .order_by(CacheEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            TrainingPair(
                anchor_text=request.prompt_text,
                comparison_text=entry.prompt_text,
                pair_type=PairType.POSITIVE,
                similarity_score=similarity,
                anchor_cache_id=None,
                comparison_cache_id=entry.cache_id,
                is_validated=0,
                quality_score=similarity,
            )
            for request, entry, similarity in rows
        ]

    def generate_positive_pairs(
        self,
        min_pairs: int = 1000,
        similarity_threshold: float = 0.85,
        days_lookback: int = 30,
    ) -> List[TrainingPair]:
        """Return curated positives plus observed matches awaiting validation."""
        candidates: list[TrainingPair] = []
        groups = self._load_groups("semantic_duplicates.json")
        curated_text_pairs = [
            pair for group in groups for pair in combinations(group["prompts"], 2)
        ]
        for (anchor, comparison), similarity in zip(
            curated_text_pairs,
            self._similarities(curated_text_pairs),
        ):
            candidates.append(
                TrainingPair(
                    anchor_text=anchor,
                    comparison_text=comparison,
                    pair_type=PairType.POSITIVE,
                    similarity_score=similarity,
                    is_validated=1,
                    quality_score=1.0,
                )
            )

        remaining = max(min_pairs - len(candidates), 0)
        if remaining:
            candidates.extend(
                self._observed_positive_pairs(
                    limit=remaining,
                    similarity_threshold=similarity_threshold,
                    days_lookback=days_lookback,
                )
            )
        return candidates[:min_pairs]

    def generate_hard_negative_pairs(
        self,
        min_pairs: int = 500,
        similarity_min: float = 0.6,
        similarity_max: float = 0.84,
        days_lookback: int = 30,
    ) -> List[TrainingPair]:
        """Return human-curated similar-looking prompts that must not match."""
        del days_lookback
        groups = self._load_groups("hard_negatives.json")
        text_pairs = [
            pair for group in groups for pair in combinations(group["prompts"], 2)
        ]
        candidates = []
        for (anchor, comparison), similarity in zip(text_pairs, self._similarities(text_pairs)):
            if similarity_min <= similarity <= similarity_max:
                candidates.append(
                    TrainingPair(
                        anchor_text=anchor,
                        comparison_text=comparison,
                        pair_type=PairType.HARD_NEGATIVE,
                        similarity_score=similarity,
                        is_validated=1,
                        quality_score=1.0,
                    )
                )
        return candidates[:min_pairs]

    def generate_easy_negative_pairs(
        self,
        min_pairs: int = 500,
        days_lookback: int = 30,
    ) -> List[TrainingPair]:
        """Pair prompts from different curated topics and keep low-similarity examples."""
        del days_lookback
        groups = self._load_groups("semantic_duplicates.json")
        representatives = [group["prompts"][0] for group in groups]
        text_pairs = list(combinations(representatives, 2))
        scored = list(zip(text_pairs, self._similarities(text_pairs)))
        random.Random(42).shuffle(scored)
        return [
            TrainingPair(
                anchor_text=anchor,
                comparison_text=comparison,
                pair_type=PairType.EASY_NEGATIVE,
                similarity_score=similarity,
                is_validated=1,
                quality_score=1.0,
            )
            for (anchor, comparison), similarity in scored
            if similarity < 0.5
        ][:min_pairs]

    def collect_training_data(
        self,
        min_positive_pairs: int = 1000,
        min_hard_negatives: int = 500,
        min_easy_negatives: int = 500,
        positive_threshold: float = 0.85,
        hard_negative_min: float = 0.6,
        hard_negative_max: float = 0.84,
        days_lookback: int = 30,
    ) -> Dict[str, int]:
        """Generate unique pairs and persist only rows not already collected."""
        start_time = datetime.utcnow()
        generated = (
            self.generate_positive_pairs(min_positive_pairs, positive_threshold, days_lookback)
            + self.generate_hard_negative_pairs(
                min_hard_negatives,
                hard_negative_min,
                hard_negative_max,
                days_lookback,
            )
            + self.generate_easy_negative_pairs(min_easy_negatives, days_lookback)
        )

        existing_keys = {
            self._pair_key(pair.anchor_text, pair.comparison_text, pair.pair_type)
            for pair in self.db.query(TrainingPair).all()
        }
        unique_new_pairs: list[TrainingPair] = []
        for pair in generated:
            key = self._pair_key(pair.anchor_text, pair.comparison_text, pair.pair_type)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            unique_new_pairs.append(pair)

        self.db.add_all(unique_new_pairs)
        self.db.commit()

        counts = {pair_type: 0 for pair_type in PairType}
        for pair in unique_new_pairs:
            counts[pair.pair_type] += 1

        result = {
            "num_positive_pairs": counts[PairType.POSITIVE],
            "num_hard_negative_pairs": counts[PairType.HARD_NEGATIVE],
            "num_easy_negative_pairs": counts[PairType.EASY_NEGATIVE],
            "total_pairs": len(unique_new_pairs),
            "collection_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
        }
        logger.info("Training data collection complete: %s", result)
        return result
