"""
Embedding Windows Module

Selects time-based windows of embeddings for drift comparison
"""
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
import numpy as np

from app.models.embedding_record import EmbeddingRecord
from app.models.cache_event import CacheEvent


class EmbeddingWindow:
    """Represents a time window of embeddings"""

    def __init__(
        self,
        embeddings: List[np.ndarray],
        similarity_scores: List[float],
        cache_hit_rate: float,
        start_time: datetime,
        end_time: datetime,
        sample_size: int
    ):
        self.embeddings = embeddings
        self.similarity_scores = similarity_scores
        self.cache_hit_rate = cache_hit_rate
        self.start_time = start_time
        self.end_time = end_time
        self.sample_size = sample_size

    def __repr__(self):
        return (
            f"<EmbeddingWindow(samples={self.sample_size}, "
            f"period={self.start_time.date()} to {self.end_time.date()})>"
        )


class WindowSelector:
    """Selects reference and recent embedding windows"""

    def __init__(self, session: Session):
        self.session = session

    def get_reference_window(
        self,
        reference_days: int = 7,
        max_samples: int = 10000,
        tenant_id: Optional[str] = None
    ) -> EmbeddingWindow:
        """
        Get reference window (stable baseline period)

        Args:
            reference_days: How many days back to use as reference
            max_samples: Maximum embeddings to sample
            tenant_id: Optional tenant isolation

        Returns:
            EmbeddingWindow with reference data
        """
        now = datetime.utcnow()
        # Reference window: from (reference_days + 1) days ago to 1 day ago
        # This avoids overlap with recent window
        end_time = now - timedelta(days=1)
        start_time = end_time - timedelta(days=reference_days)

        return self._get_window(start_time, end_time, max_samples, tenant_id)

    def get_recent_window(
        self,
        recent_hours: int = 24,
        max_samples: int = 1000,
        tenant_id: Optional[str] = None
    ) -> EmbeddingWindow:
        """
        Get recent window (current behavior)

        Args:
            recent_hours: How many hours back to analyze
            max_samples: Maximum embeddings to sample
            tenant_id: Optional tenant isolation

        Returns:
            EmbeddingWindow with recent data
        """
        now = datetime.utcnow()
        start_time = now - timedelta(hours=recent_hours)
        end_time = now

        return self._get_window(start_time, end_time, max_samples, tenant_id)

    def get_custom_window(
        self,
        start_time: datetime,
        end_time: datetime,
        max_samples: int = 5000,
        tenant_id: Optional[str] = None
    ) -> EmbeddingWindow:
        """
        Get custom time window

        Args:
            start_time: Window start
            end_time: Window end
            max_samples: Maximum embeddings to sample
            tenant_id: Optional tenant isolation

        Returns:
            EmbeddingWindow with custom data
        """
        return self._get_window(start_time, end_time, max_samples, tenant_id)

    def _get_window(
        self,
        start_time: datetime,
        end_time: datetime,
        max_samples: int,
        tenant_id: Optional[str]
    ) -> EmbeddingWindow:
        """
        Internal method to fetch window data

        Retrieves:
        - Embeddings from cache events
        - Similarity scores
        - Cache hit rate
        """
        # Build base query for cache events in time range
        query = self.session.query(CacheEvent).filter(
            and_(
                CacheEvent.created_at >= start_time,
                CacheEvent.created_at <= end_time
            )
        )

        if tenant_id:
            query = query.filter(CacheEvent.tenant_id == tenant_id)

        # Order by most recent first, limit samples
        events = query.order_by(desc(CacheEvent.created_at)).limit(max_samples).all()

        if not events:
            # Return empty window
            return EmbeddingWindow(
                embeddings=[],
                similarity_scores=[],
                cache_hit_rate=0.0,
                start_time=start_time,
                end_time=end_time,
                sample_size=0
            )

        # Extract similarity scores (available for all cache events)
        similarity_scores = [
            event.similarity_score
            for event in events
            if event.similarity_score is not None
        ]

        # Calculate cache hit rate
        total_events = len(events)
        hit_events = sum(1 for e in events if e.cache_status.value == "HIT")
        cache_hit_rate = hit_events / total_events if total_events > 0 else 0.0

        # Fetch embeddings from embedding_records table
        # Get prompt embeddings that were used during this period
        embeddings = []

        # For each cache event, try to get the embedding
        # In practice, you'd join with embedding_records or store embeddings differently
        # For MVP, we'll fetch from embedding_records based on the time period
        embedding_query = self.session.query(EmbeddingRecord).filter(
            and_(
                EmbeddingRecord.created_at >= start_time,
                EmbeddingRecord.created_at <= end_time
            )
        ).limit(max_samples)

        embedding_records = embedding_query.all()

        for record in embedding_records:
            if record.embedding_vector:
                # Assuming embedding_vector is stored as bytes or list
                # Convert to numpy array
                try:
                    if isinstance(record.embedding_vector, (list, tuple)):
                        embeddings.append(np.array(record.embedding_vector, dtype=np.float32))
                    elif isinstance(record.embedding_vector, bytes):
                        # If stored as bytes, decode
                        arr = np.frombuffer(record.embedding_vector, dtype=np.float32)
                        embeddings.append(arr)
                except Exception:
                    # Skip malformed embeddings
                    continue

        return EmbeddingWindow(
            embeddings=embeddings,
            similarity_scores=similarity_scores,
            cache_hit_rate=cache_hit_rate,
            start_time=start_time,
            end_time=end_time,
            sample_size=len(embeddings)
        )

    def get_windows_for_drift_check(
        self,
        tenant_id: Optional[str] = None
    ) -> Tuple[EmbeddingWindow, EmbeddingWindow]:
        """
        Get both reference and recent windows for drift detection

        Returns:
            Tuple of (reference_window, recent_window)
        """
        reference_window = self.get_reference_window(
            reference_days=7,
            max_samples=10000,
            tenant_id=tenant_id
        )

        recent_window = self.get_recent_window(
            recent_hours=24,
            max_samples=1000,
            tenant_id=tenant_id
        )

        return reference_window, recent_window
