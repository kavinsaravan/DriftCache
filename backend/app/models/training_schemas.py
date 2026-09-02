"""
Training Schemas

Pydantic models for training API requests/responses
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class PairTypeEnum(str, Enum):
    """Type of training pair"""
    POSITIVE = "positive"
    HARD_NEGATIVE = "hard_negative"
    EASY_NEGATIVE = "easy_negative"


class JobStatusEnum(str, Enum):
    """Training job status"""
    PENDING = "pending"
    COLLECTING_DATA = "collecting_data"
    TRAINING = "training"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"


# Training Pair Schemas
class TrainingPairCreate(BaseModel):
    """Schema for creating a training pair"""
    anchor_text: str
    comparison_text: str
    pair_type: PairTypeEnum
    similarity_score: Optional[float] = None
    anchor_cache_id: Optional[str] = None
    comparison_cache_id: Optional[str] = None


class TrainingPairResponse(BaseModel):
    """Schema for training pair response"""
    id: int
    anchor_text: str
    comparison_text: str
    pair_type: str
    similarity_score: Optional[float] = None
    is_validated: int
    used_in_training: int
    created_at: datetime

    class Config:
        from_attributes = True


# Data Collection Schemas
class DataCollectionRequest(BaseModel):
    """Request to collect training data"""
    min_positive_pairs: int = Field(default=1000, description="Minimum positive pairs to collect")
    min_hard_negatives: int = Field(default=500, description="Minimum hard negative pairs")
    min_easy_negatives: int = Field(default=500, description="Minimum easy negative pairs")
    positive_threshold: float = Field(default=0.85, description="Similarity threshold for positives")
    hard_negative_min: float = Field(default=0.6, description="Min similarity for hard negatives")
    hard_negative_max: float = Field(default=0.84, description="Max similarity for hard negatives")
    days_lookback: int = Field(default=30, description="Days of cache history to analyze")


class DataCollectionResponse(BaseModel):
    """Response from data collection"""
    num_positive_pairs: int
    num_hard_negative_pairs: int
    num_easy_negative_pairs: int
    total_pairs: int
    collection_time_seconds: float
    message: str


# Training Job Schemas
class TrainingConfig(BaseModel):
    """Training configuration"""
    learning_rate: float = Field(default=2e-5, description="Learning rate")
    batch_size: int = Field(default=16, description="Training batch size")
    num_epochs: int = Field(default=3, description="Number of training epochs")
    warmup_steps: int = Field(default=100, description="Warmup steps")
    max_seq_length: int = Field(default=128, description="Maximum sequence length")
    loss_function: str = Field(default="MultipleNegativesRankingLoss", description="Loss function to use")
    evaluation_steps: int = Field(default=100, description="Steps between evaluations")
    save_steps: int = Field(default=500, description="Steps between checkpoints")
    use_wandb: bool = Field(default=False, description="Enable Weights & Biases logging")


class TrainingJobCreate(BaseModel):
    """Request to create a training job"""
    base_model: str = Field(default="all-MiniLM-L6-v2", description="Base model to fine-tune")
    output_model_name: Optional[str] = None
    training_config: Optional[TrainingConfig] = Field(default_factory=TrainingConfig)
    upload_to_hub: bool = Field(default=False, description="Upload to Hugging Face Hub")
    hub_model_id: Optional[str] = None


class TrainingJobResponse(BaseModel):
    """Response for training job"""
    job_id: str
    status: str
    base_model: str
    output_model_name: Optional[str]
    num_training_pairs: Optional[int]
    num_positive_pairs: Optional[int]
    num_negative_pairs: Optional[int]
    final_loss: Optional[float]
    num_epochs_completed: int
    training_time_seconds: Optional[float]
    eval_metrics: Dict[str, Any]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# Model Version Schemas
class ModelVersionCreate(BaseModel):
    """Request to create a model version"""
    version_id: str
    model_name: str
    base_model: str
    is_finetuned: bool = False
    training_job_id: Optional[str] = None
    huggingface_url: Optional[str] = None
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)
    dimension: int
    description: Optional[str] = None


class ModelVersionResponse(BaseModel):
    """Response for model version"""
    version_id: str
    model_name: str
    base_model: str
    is_finetuned: bool
    training_job_id: Optional[str]
    huggingface_url: Optional[str]
    performance_metrics: Dict[str, Any]
    is_active: bool
    traffic_percentage: float
    dimension: int
    description: Optional[str]
    created_at: datetime
    deployed_at: Optional[datetime]

    class Config:
        from_attributes = True


# Evaluation Schemas
class EvaluationMetrics(BaseModel):
    """Evaluation metrics for a model"""
    precision_at_1: float
    precision_at_5: float
    recall_at_1: float
    recall_at_5: float
    mrr: float  # Mean Reciprocal Rank
    ndcg: float  # Normalized Discounted Cumulative Gain
    avg_similarity_positive: float
    avg_similarity_negative: float
    latency_ms: float
