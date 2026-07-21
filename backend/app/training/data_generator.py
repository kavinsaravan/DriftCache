"""
Training Data Generator

Generates training pairs from cache interactions for contrastive learning.

Strategies:
1. Positive pairs: Queries with high similarity that resulted in cache hits
2. Hard negatives: Queries with medium similarity that shouldn't match
3. Easy negatives: Random dissimilar queries
"""
import logging
import random
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.cache_entry import CacheEntry
from app.models.training_pair import TrainingPair, PairType
from app.embeddings.service import get_embedding_service
from app.embeddings.utils import list_to_vector
import numpy as np

logger = logging.getLogger(__name__)


class TrainingDataGenerator:
    """
    Generates training pairs from cache interactions

    This is a key component for fine-tuning the embedding model
    using real production data.
    """

    def __init__(self, db: Session):
        """
        Initialize data generator

        Args:
            db: Database session
        """
        self.db = db
        self.embedding_service = get_embedding_service()

    def generate_positive_pairs(
        self,
        min_pairs: int = 1000,
        similarity_threshold: float = 0.85,
        days_lookback: int = 30
    ) -> List[TrainingPair]:
        """
        Generate positive pairs from cache hits

        Strategy: Find queries that resulted in cache hits with high similarity

        Args:
            min_pairs: Minimum number of pairs to generate
            similarity_threshold: Minimum similarity for positive pairs
            days_lookback: Days of history to analyze

        Returns:
            List of positive training pairs
        """
        logger.info(f"Generating positive pairs (target: {min_pairs})")

        # Get cache entries with hits from recent history
        cutoff_date = datetime.utcnow() - timedelta(days=days_lookback)

        cache_entries = self.db.query(CacheEntry).filter(
            and_(
                CacheEntry.cache_hits > 0,
                CacheEntry.created_at >= cutoff_date
            )
        ).limit(5000).all()  # Limit for performance

        logger.info(f"Found {len(cache_entries)} cache entries with hits")

        positive_pairs = []

        # Generate pairs by finding similar cached queries
        for i, entry1 in enumerate(cache_entries):
            if len(positive_pairs) >= min_pairs:
                break

            # Get embedding for this entry
            emb1 = self.embedding_service.embed_text(entry1.prompt_text)
            vec1 = list_to_vector(emb1.vector)

            # Find similar entries
            for entry2 in cache_entries[i+1:]:
                if len(positive_pairs) >= min_pairs:
                    break

                # Skip if same prompt
                if entry1.prompt_hash == entry2.prompt_hash:
                    continue

                # Compute similarity
                emb2 = self.embedding_service.embed_text(entry2.prompt_text)
                vec2 = list_to_vector(emb2.vector)
                similarity = float(np.dot(vec1, vec2))

                # Create positive pair if similarity is high
                if similarity >= similarity_threshold:
                    pair = TrainingPair(
                        anchor_text=entry1.prompt_text,
                        comparison_text=entry2.prompt_text,
                        pair_type=PairType.POSITIVE,
                        similarity_score=similarity,
                        anchor_cache_id=entry1.cache_id,
                        comparison_cache_id=entry2.cache_id
                    )
                    positive_pairs.append(pair)

                    logger.debug(f"Created positive pair: similarity={similarity:.3f}")

        logger.info(f"Generated {len(positive_pairs)} positive pairs")
        return positive_pairs

    def generate_hard_negative_pairs(
        self,
        min_pairs: int = 500,
        similarity_min: float = 0.6,
        similarity_max: float = 0.84,
        days_lookback: int = 30
    ) -> List[TrainingPair]:
        """
        Generate hard negative pairs

        Strategy: Find queries with medium similarity that should NOT match
        These are the hardest cases for the model to learn

        Args:
            min_pairs: Minimum number of pairs to generate
            similarity_min: Minimum similarity for hard negatives
            similarity_max: Maximum similarity for hard negatives
            days_lookback: Days of history to analyze

        Returns:
            List of hard negative training pairs
        """
        logger.info(f"Generating hard negative pairs (target: {min_pairs})")

        # Get cache entries from recent history
        cutoff_date = datetime.utcnow() - timedelta(days=days_lookback)

        cache_entries = self.db.query(CacheEntry).filter(
            CacheEntry.created_at >= cutoff_date
        ).limit(5000).all()

        hard_negatives = []

        # Generate pairs by finding medium similarity queries
        for i, entry1 in enumerate(cache_entries):
            if len(hard_negatives) >= min_pairs:
                break

            # Get embedding for this entry
            emb1 = self.embedding_service.embed_text(entry1.prompt_text)
            vec1 = list_to_vector(emb1.vector)

            # Find medium similarity entries (hard negatives)
            for entry2 in cache_entries[i+1:]:
                if len(hard_negatives) >= min_pairs:
                    break

                # Skip if same prompt
                if entry1.prompt_hash == entry2.prompt_hash:
                    continue

                # Skip if same model (we want different domains)
                if entry1.model == entry2.model:
                    continue

                # Compute similarity
                emb2 = self.embedding_service.embed_text(entry2.prompt_text)
                vec2 = list_to_vector(emb2.vector)
                similarity = float(np.dot(vec1, vec2))

                # Create hard negative if similarity is in the sweet spot
                if similarity_min <= similarity <= similarity_max:
                    pair = TrainingPair(
                        anchor_text=entry1.prompt_text,
                        comparison_text=entry2.prompt_text,
                        pair_type=PairType.HARD_NEGATIVE,
                        similarity_score=similarity,
                        anchor_cache_id=entry1.cache_id,
                        comparison_cache_id=entry2.cache_id
                    )
                    hard_negatives.append(pair)

                    logger.debug(f"Created hard negative pair: similarity={similarity:.3f}")

        logger.info(f"Generated {len(hard_negatives)} hard negative pairs")
        return hard_negatives

    def generate_easy_negative_pairs(
        self,
        min_pairs: int = 500,
        days_lookback: int = 30
    ) -> List[TrainingPair]:
        """
        Generate easy negative pairs

        Strategy: Random pairs from different domains

        Args:
            min_pairs: Minimum number of pairs to generate
            days_lookback: Days of history to analyze

        Returns:
            List of easy negative training pairs
        """
        logger.info(f"Generating easy negative pairs (target: {min_pairs})")

        # Get cache entries from recent history
        cutoff_date = datetime.utcnow() - timedelta(days=days_lookback)

        cache_entries = self.db.query(CacheEntry).filter(
            CacheEntry.created_at >= cutoff_date
        ).all()

        if len(cache_entries) < 2:
            logger.warning("Not enough cache entries for easy negatives")
            return []

        easy_negatives = []

        # Generate random pairs
        for _ in range(min_pairs):
            # Pick two random entries
            entry1, entry2 = random.sample(cache_entries, 2)

            # Skip if same prompt
            if entry1.prompt_hash == entry2.prompt_hash:
                continue

            # Optionally compute similarity
            emb1 = self.embedding_service.embed_text(entry1.prompt_text)
            emb2 = self.embedding_service.embed_text(entry2.prompt_text)
            vec1 = list_to_vector(emb1.vector)
            vec2 = list_to_vector(emb2.vector)
            similarity = float(np.dot(vec1, vec2))

            # Only use if similarity is low
            if similarity < 0.5:
                pair = TrainingPair(
                    anchor_text=entry1.prompt_text,
                    comparison_text=entry2.prompt_text,
                    pair_type=PairType.EASY_NEGATIVE,
                    similarity_score=similarity,
                    anchor_cache_id=entry1.cache_id,
                    comparison_cache_id=entry2.cache_id
                )
                easy_negatives.append(pair)

                logger.debug(f"Created easy negative pair: similarity={similarity:.3f}")

        logger.info(f"Generated {len(easy_negatives)} easy negative pairs")
        return easy_negatives

    def collect_training_data(
        self,
        min_positive_pairs: int = 1000,
        min_hard_negatives: int = 500,
        min_easy_negatives: int = 500,
        positive_threshold: float = 0.85,
        hard_negative_min: float = 0.6,
        hard_negative_max: float = 0.84,
        days_lookback: int = 30
    ) -> Dict[str, int]:
        """
        Collect all training data and save to database

        This is the main method to call for data collection

        Args:
            min_positive_pairs: Target number of positive pairs
            min_hard_negatives: Target number of hard negative pairs
            min_easy_negatives: Target number of easy negative pairs
            positive_threshold: Similarity threshold for positives
            hard_negative_min: Min similarity for hard negatives
            hard_negative_max: Max similarity for hard negatives
            days_lookback: Days of history to analyze

        Returns:
            Dictionary with counts of generated pairs
        """
        logger.info("Starting training data collection")
        start_time = datetime.utcnow()

        # Generate positive pairs
        positive_pairs = self.generate_positive_pairs(
            min_pairs=min_positive_pairs,
            similarity_threshold=positive_threshold,
            days_lookback=days_lookback
        )

        # Generate hard negatives
        hard_negatives = self.generate_hard_negative_pairs(
            min_pairs=min_hard_negatives,
            similarity_min=hard_negative_min,
            similarity_max=hard_negative_max,
            days_lookback=days_lookback
        )

        # Generate easy negatives
        easy_negatives = self.generate_easy_negative_pairs(
            min_pairs=min_easy_negatives,
            days_lookback=days_lookback
        )

        # Save all pairs to database
        all_pairs = positive_pairs + hard_negatives + easy_negatives

        self.db.bulk_save_objects(all_pairs)
        self.db.commit()

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        result = {
            "num_positive_pairs": len(positive_pairs),
            "num_hard_negative_pairs": len(hard_negatives),
            "num_easy_negative_pairs": len(easy_negatives),
            "total_pairs": len(all_pairs),
            "collection_time_seconds": duration
        }

        logger.info(f"Training data collection complete: {result}")

        return result
