"""
PyTorch Fine-Tuning Pipeline

Implements contrastive learning to fine-tune sentence-transformers models
using training data collected from cache interactions.

Uses:
- PyTorch for training loop
- Hugging Face Transformers for model loading
- Sentence Transformers for specialized loss functions
"""
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

import torch
from torch.utils.data import DataLoader
from sentence_transformers import (
    SentenceTransformer,
    InputExample,
    losses,
    evaluation,
)
from sentence_transformers.util import batch_to_device
from sqlalchemy.orm import Session

from app.models.training_pair import TrainingPair, PairType
from app.models.training_job import TrainingJob, JobStatus
from app.models.training_schemas import TrainingConfig

logger = logging.getLogger(__name__)


class ContrastiveTrainer:
    """
    PyTorch-based trainer for fine-tuning embedding models

    Implements contrastive learning with Multiple Negatives Ranking Loss
    or Triplet Loss for learning better semantic representations.
    """

    def __init__(
        self,
        base_model: str,
        output_path: str,
        device: Optional[str] = None
    ):
        """
        Initialize trainer

        Args:
            base_model: Name or path of base sentence-transformer model
            output_path: Directory to save fine-tuned model
            device: Device to train on (cuda/cpu). Auto-detected if None
        """
        self.base_model = base_model
        self.output_path = output_path

        # Auto-detect device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"Initializing ContrastiveTrainer on device: {self.device}")
        logger.info(f"Base model: {base_model}")
        logger.info(f"Output path: {output_path}")

        # Load model
        self.model = SentenceTransformer(base_model, device=self.device)

        # Training state
        self.best_loss = float('inf')
        self.training_metrics = {}

    def prepare_training_data(
        self,
        db: Session,
        batch_size: int = 16,
        max_seq_length: int = 128
    ) -> DataLoader:
        """
        Prepare training data from database

        Args:
            db: Database session
            batch_size: Training batch size
            max_seq_length: Maximum sequence length

        Returns:
            DataLoader for training
        """
        logger.info("Preparing training data from database")

        # Query all training pairs
        training_pairs = db.query(TrainingPair).all()

        if not training_pairs:
            raise ValueError("No training pairs found in database")

        logger.info(f"Loaded {len(training_pairs)} training pairs")

        # Convert to InputExample format
        train_examples = []

        for pair in training_pairs:
            # For positive pairs: (anchor, positive, label=1.0)
            if pair.pair_type == PairType.POSITIVE:
                example = InputExample(
                    texts=[pair.anchor_text, pair.comparison_text],
                    label=1.0  # Similar
                )
                train_examples.append(example)

            # For negative pairs: (anchor, negative, label=0.0)
            elif pair.pair_type in [PairType.HARD_NEGATIVE, PairType.EASY_NEGATIVE]:
                example = InputExample(
                    texts=[pair.anchor_text, pair.comparison_text],
                    label=0.0  # Dissimilar
                )
                train_examples.append(example)

        logger.info(f"Created {len(train_examples)} training examples")

        # Set max sequence length
        self.model.max_seq_length = max_seq_length

        # Create DataLoader
        train_dataloader = DataLoader(
            train_examples,
            shuffle=True,
            batch_size=batch_size
        )

        return train_dataloader

    def create_loss_function(self, loss_name: str):
        """
        Create loss function for training

        Args:
            loss_name: Name of loss function to use

        Returns:
            Loss function instance
        """
        if loss_name == "MultipleNegativesRankingLoss":
            # Contrastive loss: learns to maximize similarity for positives
            # and minimize for negatives
            loss = losses.MultipleNegativesRankingLoss(self.model)
            logger.info("Using MultipleNegativesRankingLoss")

        elif loss_name == "CosineSimilarityLoss":
            # Direct cosine similarity loss
            loss = losses.CosineSimilarityLoss(self.model)
            logger.info("Using CosineSimilarityLoss")

        elif loss_name == "ContrastiveLoss":
            # Classic contrastive loss with margin
            loss = losses.ContrastiveLoss(self.model, margin=0.5)
            logger.info("Using ContrastiveLoss with margin=0.5")

        else:
            raise ValueError(f"Unknown loss function: {loss_name}")

        return loss

    def train(
        self,
        train_dataloader: DataLoader,
        config: TrainingConfig,
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Train the model

        Args:
            train_dataloader: DataLoader with training data
            config: Training configuration
            job_id: Optional job ID for tracking

        Returns:
            Dictionary with training metrics
        """
        logger.info("Starting training")
        logger.info(f"Config: {config.model_dump()}")

        start_time = datetime.utcnow()

        # Create loss function
        train_loss = self.create_loss_function(config.loss_function)

        # Calculate warmup steps
        num_train_steps = len(train_dataloader) * config.num_epochs
        warmup_steps = config.warmup_steps

        logger.info(f"Total training steps: {num_train_steps}")
        logger.info(f"Warmup steps: {warmup_steps}")

        # Train the model
        try:
            self.model.fit(
                train_objectives=[(train_dataloader, train_loss)],
                epochs=config.num_epochs,
                warmup_steps=warmup_steps,
                optimizer_params={'lr': config.learning_rate},
                output_path=self.output_path,
                save_best_model=True,
                show_progress_bar=True,
                evaluation_steps=config.evaluation_steps,
                checkpoint_save_steps=config.save_steps,
                checkpoint_path=os.path.join(self.output_path, "checkpoints"),
            )

        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise

        end_time = datetime.utcnow()
        training_time = (end_time - start_time).total_seconds()

        # Collect metrics
        metrics = {
            "training_time_seconds": training_time,
            "num_epochs": config.num_epochs,
            "num_train_steps": num_train_steps,
            "learning_rate": config.learning_rate,
            "batch_size": config.batch_size,
            "loss_function": config.loss_function,
        }

        logger.info(f"Training complete in {training_time:.2f}s")
        logger.info(f"Model saved to: {self.output_path}")

        return metrics

    def save_to_hub(
        self,
        hub_model_id: str,
        token: Optional[str] = None,
        private: bool = True
    ) -> str:
        """
        Upload model to Hugging Face Hub

        Args:
            hub_model_id: Model ID on HF Hub (e.g., "username/model-name")
            token: HF API token (uses HF_TOKEN env var if None)
            private: Whether to make the model private

        Returns:
            URL to the model on HF Hub
        """
        logger.info(f"Uploading model to Hugging Face Hub: {hub_model_id}")

        try:
            # Load the saved model
            model = SentenceTransformer(self.output_path)

            # Push to hub
            model.push_to_hub(
                repo_id=hub_model_id,
                token=token,
                private=private,
                commit_message="Fine-tuned on DriftCache data"
            )

            hub_url = f"https://huggingface.co/{hub_model_id}"
            logger.info(f"Model uploaded successfully: {hub_url}")

            return hub_url

        except Exception as e:
            logger.error(f"Failed to upload to HF Hub: {e}")
            raise


class TrainingJobManager:
    """
    Manages training jobs and coordinates the training process
    """

    def __init__(self, db: Session):
        """
        Initialize job manager

        Args:
            db: Database session
        """
        self.db = db

    def create_training_job(
        self,
        base_model: str,
        config: TrainingConfig,
        output_model_name: Optional[str] = None
    ) -> TrainingJob:
        """
        Create a new training job

        Args:
            base_model: Base model to fine-tune
            config: Training configuration
            output_model_name: Name for output model

        Returns:
            Created TrainingJob
        """
        job_id = str(uuid.uuid4())

        # Generate output model name if not provided
        if output_model_name is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            output_model_name = f"{base_model}-driftcache-{timestamp}"

        # Count training pairs
        num_positive = self.db.query(TrainingPair).filter(
            TrainingPair.pair_type == PairType.POSITIVE
        ).count()

        num_hard_neg = self.db.query(TrainingPair).filter(
            TrainingPair.pair_type == PairType.HARD_NEGATIVE
        ).count()

        num_easy_neg = self.db.query(TrainingPair).filter(
            TrainingPair.pair_type == PairType.EASY_NEGATIVE
        ).count()

        total_pairs = num_positive + num_hard_neg + num_easy_neg

        # Create job
        job = TrainingJob(
            job_id=job_id,
            status=JobStatus.PENDING,
            base_model=base_model,
            output_model_name=output_model_name,
            training_config=config.model_dump(),
            num_training_pairs=total_pairs,
            num_positive_pairs=num_positive,
            num_negative_pairs=num_hard_neg + num_easy_neg,
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        logger.info(f"Created training job: {job_id}")

        return job

    def run_training_job(
        self,
        job_id: str,
        upload_to_hub: bool = False,
        hub_model_id: Optional[str] = None
    ) -> TrainingJob:
        """
        Execute a training job

        Args:
            job_id: ID of job to run
            upload_to_hub: Whether to upload to HF Hub
            hub_model_id: Model ID on HF Hub

        Returns:
            Updated TrainingJob
        """
        # Get job
        job = self.db.query(TrainingJob).filter(
            TrainingJob.job_id == job_id
        ).first()

        if not job:
            raise ValueError(f"Job not found: {job_id}")

        try:
            # Update status
            job.status = JobStatus.TRAINING
            job.started_at = datetime.utcnow()
            self.db.commit()

            # Create output directory
            output_path = f"models/{job.output_model_name}"
            os.makedirs(output_path, exist_ok=True)

            # Initialize trainer
            trainer = ContrastiveTrainer(
                base_model=job.base_model,
                output_path=output_path
            )

            # Prepare training config
            config = TrainingConfig(**job.training_config)

            # Prepare data
            train_dataloader = trainer.prepare_training_data(
                db=self.db,
                batch_size=config.batch_size,
                max_seq_length=config.max_seq_length
            )

            # Train
            metrics = trainer.train(
                train_dataloader=train_dataloader,
                config=config,
                job_id=job_id
            )

            # Upload to HF Hub if requested
            hub_url = None
            if upload_to_hub and hub_model_id:
                hub_url = trainer.save_to_hub(hub_model_id=hub_model_id)

            # Update job with results
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.training_time_seconds = metrics["training_time_seconds"]
            job.num_epochs_completed = config.num_epochs

            # Store HF Hub URL if uploaded
            if hub_url:
                job.training_config["huggingface_url"] = hub_url

            self.db.commit()

            logger.info(f"Training job {job_id} completed successfully")

            return job

        except Exception as e:
            # Mark job as failed
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            self.db.commit()

            logger.error(f"Training job {job_id} failed: {e}")
            raise
