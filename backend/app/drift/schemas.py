"""Typed inputs and outputs for similarity-score drift monitoring."""

from datetime import datetime
from typing import Annotated, Literal

import math
from pydantic import BaseModel, ConfigDict, Field, field_validator

SimilarityScore = Annotated[float, Field(ge=-1.0, le=1.0)]


class DriftConfig(BaseModel):
    """Configuration for comparing historical and recent similarity scores."""

    minimum_samples: int = Field(default=30, ge=5, le=10_000)
    reference_days: int = Field(default=7, ge=1, le=90)
    recent_hours: int = Field(default=24, ge=1, le=168)
    max_reference_samples: int = Field(default=10_000, ge=5, le=100_000)
    max_recent_samples: int = Field(default=2_000, ge=5, le=100_000)
    significance_level: float = Field(default=0.05, gt=0.0, lt=1.0)
    wasserstein_threshold: float = Field(default=0.08, gt=0.0, le=2.0)
    mean_shift_threshold: float = Field(default=0.05, gt=0.0, le=2.0)
    variance_ratio_lower: float = Field(default=0.5, gt=0.0)
    variance_ratio_upper: float = Field(default=2.0, gt=0.0)

    model_config = ConfigDict(frozen=True)

    @field_validator("variance_ratio_upper")
    @classmethod
    def validate_variance_bounds(cls, value: float, info):
        lower = info.data.get("variance_ratio_lower")
        if lower is not None and value <= lower:
            raise ValueError("variance_ratio_upper must exceed variance_ratio_lower")
        return value


class SimilaritySamples(BaseModel):
    """Similarity scores and the time range from which they were collected."""

    scores: list[SimilarityScore]
    start: datetime
    end: datetime

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    @field_validator("scores")
    @classmethod
    def reject_non_finite_scores(cls, values: list[float]) -> list[float]:
        if any(not math.isfinite(value) for value in values):
            raise ValueError("similarity scores must be finite")
        return values


class DriftReport(BaseModel):
    """Explainable result of comparing two similarity-score distributions."""

    status: Literal["stable", "drift_detected", "insufficient_data"]
    drift_detected: bool
    severity: Literal["none", "low", "medium", "high"]
    drift_score: float = Field(ge=0.0, le=1.0)
    reference_sample_size: int = Field(ge=0)
    recent_sample_size: int = Field(ge=0)
    reference_window_start: datetime
    reference_window_end: datetime
    recent_window_start: datetime
    recent_window_end: datetime
    ks_statistic: float = Field(ge=0.0, le=1.0)
    ks_p_value: float = Field(ge=0.0, le=1.0)
    wasserstein_distance: float = Field(ge=0.0)
    reference_mean: float
    recent_mean: float
    mean_shift: float
    reference_variance: float = Field(ge=0.0)
    recent_variance: float = Field(ge=0.0)
    variance_ratio: float = Field(ge=0.0)
    reasons: list[str]

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
