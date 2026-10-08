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
import random
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

import numpy as np
import torch
from torch.utils.data import DataLoader
from sentence_transformers import (
    SentenceTransformer,
    InputExample,
    losses,
)
from sentence_transformers.evaluation import EmbeddingSimilarityEvaluator
from sqlalchemy.orm import Session

from app.models.training_pair import TrainingPair, PairType
from app.models.training_job import TrainingJob, JobStatus
from app.models.model_version import ModelVersion
from app.models.training_schemas import TrainingConfig
from app.core.config import settings

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
        max_seq_length: int = 128,
        loss_function: str = "CosineSimilarityLoss",
        validation_split: float = 0.2,
        random_seed: int = 42,
    ) -> tuple[DataLoader, List[InputExample]]:
        """
        Prepare training data from database

        Args:
            db: Database session
            batch_size: Training batch size
            max_seq_length: Maximum sequence length
            loss_function: Loss function to be used (affects data format)

        Returns:
            Training DataLoader and held-out validation examples
        """
        logger.info("Preparing training data from database")

        # Observed cache hits remain review candidates. Training only consumes
        # curated or explicitly human-validated labels.
        training_pairs = [
            pair for pair in db.query(TrainingPair).all() if pair.is_validated == 1
        ]

        if not training_pairs:
            raise ValueError("No validated training pairs found in database")

        logger.info(f"Loaded {len(training_pairs)} training pairs")

        rng = random.Random(random_seed)

        # Keep equivalent prompts together. Negative edges do not form groups:
        # joining them would connect unrelated topics into one giant component.
        parent: Dict[str, str] = {}

        def normalized(text: str) -> str:
            return " ".join(text.lower().split())

        def find(value: str) -> str:
            parent.setdefault(value, value)
            if parent[value] != value:
                parent[value] = find(parent[value])
            return parent[value]

        def union(first: str, second: str) -> None:
            first_root, second_root = find(first), find(second)
            if first_root != second_root:
                parent[second_root] = first_root

        for pair in training_pairs:
            anchor = normalized(pair.anchor_text)
            comparison = normalized(pair.comparison_text)
            find(anchor)
            find(comparison)
            if pair.pair_type == PairType.POSITIVE:
                union(anchor, comparison)

        prompt_groups: Dict[str, set[str]] = {}
        for prompt in list(parent):
            prompt_groups.setdefault(find(prompt), set()).add(prompt)

        group_ids = list(prompt_groups)
        positive_group_ids = {
            find(normalized(pair.anchor_text))
            for pair in training_pairs
            if pair.pair_type == PairType.POSITIVE
        }
        if len(positive_group_ids) < 2:
            raise ValueError(
                "At least two disconnected positive prompt groups are required "
                "for leakage-free training and validation"
            )

        validation_group_count = max(3, round(len(group_ids) * validation_split))
        validation_group_count = min(validation_group_count, len(group_ids) - 1)
        training_pairs_split: List[TrainingPair] = []
        validation_pairs: List[TrainingPair] = []

        # Try deterministic seeded assignments until both partitions contain
        # the classes needed by training/evaluation. Negative pairs spanning
        # the boundary are omitted rather than leaking either prompt.
        for _ in range(200):
            rng.shuffle(group_ids)
            validation_ids = set(group_ids[:validation_group_count])
            candidate_training: List[TrainingPair] = []
            candidate_validation: List[TrainingPair] = []
            for pair in training_pairs:
                anchor_group = find(normalized(pair.anchor_text))
                comparison_group = find(normalized(pair.comparison_text))
                anchor_is_validation = anchor_group in validation_ids
                comparison_is_validation = comparison_group in validation_ids
                if anchor_is_validation and comparison_is_validation:
                    candidate_validation.append(pair)
                elif not anchor_is_validation and not comparison_is_validation:
                    candidate_training.append(pair)

            validation_types = {pair.pair_type for pair in candidate_validation}
            has_validation_negative = bool(
                validation_types & {PairType.HARD_NEGATIVE, PairType.EASY_NEGATIVE}
            )
            has_training_positive = any(
                pair.pair_type == PairType.POSITIVE for pair in candidate_training
            )
            if (
                PairType.POSITIVE in validation_types
                and has_validation_negative
                and has_training_positive
            ):
                training_pairs_split = candidate_training
                validation_pairs = candidate_validation
                break
        else:
            raise ValueError(
                "Could not create a leakage-free split containing both validation classes"
            )

        def to_example(pair: TrainingPair) -> InputExample:
            return InputExample(
                texts=[pair.anchor_text, pair.comparison_text],
                label=1.0 if pair.pair_type == PairType.POSITIVE else 0.0,
            )

        if loss_function == "MultipleNegativesRankingLoss":
            train_examples = [
                to_example(pair)
                for pair in training_pairs_split
                if pair.pair_type == PairType.POSITIVE
            ]
        else:
            train_examples = [to_example(pair) for pair in training_pairs_split]
            rng.shuffle(train_examples)

        validation_examples = [to_example(pair) for pair in validation_pairs]
        rng.shuffle(validation_examples)

        if not train_examples:
            raise ValueError(
                "Not enough compatible training pairs. At least two positive pairs are "
                "required for MultipleNegativesRankingLoss."
            )
        if len(validation_examples) < 2:
            raise ValueError(
                "At least two held-out pairs are required for validation; collect more training data"
            )
        validation_labels = {example.label for example in validation_examples}
        if validation_labels != {0.0, 1.0}:
            raise ValueError("Validation split must contain positive and negative pairs")

        logger.info(
            "Prepared %s training and %s validation examples",
            len(train_examples),
            len(validation_examples),
        )

        # Set max sequence length
        self.model.max_seq_length = max_seq_length

        # Create DataLoader
        train_dataloader = DataLoader(
            train_examples,
            shuffle=True,
            batch_size=batch_size
        )

        return train_dataloader, validation_examples

    def evaluate(
        self,
        validation_examples: List[InputExample],
        threshold: float,
    ) -> Dict[str, Any]:
        """Evaluate pair classification on data excluded from training."""
        anchors = [example.texts[0] for example in validation_examples]
        comparisons = [example.texts[1] for example in validation_examples]
        labels = np.asarray([float(example.label) for example in validation_examples])

        anchor_embeddings = self.model.encode(
            anchors, normalize_embeddings=True, convert_to_numpy=True
        )
        comparison_embeddings = self.model.encode(
            comparisons, normalize_embeddings=True, convert_to_numpy=True
        )
        similarities = np.sum(anchor_embeddings * comparison_embeddings, axis=1)
        predictions = similarities >= threshold
        positives = labels == 1.0
        negatives = ~positives

        true_positives = int(np.sum(predictions & positives))
        false_positives = int(np.sum(predictions & negatives))
        false_negatives = int(np.sum(~predictions & positives))
        true_negatives = int(np.sum(~predictions & negatives))

        precision = true_positives / max(true_positives + false_positives, 1)
        recall = true_positives / max(true_positives + false_negatives, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-12)

        return {
            "validation_examples": len(validation_examples),
            "similarity_threshold": threshold,
            "mean_squared_error": float(np.mean((similarities - labels) ** 2)),
            "accuracy": float((true_positives + true_negatives) / len(labels)),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "true_negatives": true_negatives,
            "false_negatives": false_negatives,
            "avg_similarity_positive": (
                float(np.mean(similarities[positives])) if np.any(positives) else None
            ),
            "avg_similarity_negative": (
                float(np.mean(similarities[negatives])) if np.any(negatives) else None
            ),
        }

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
        validation_examples: List[InputExample],
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

        evaluator = EmbeddingSimilarityEvaluator.from_input_examples(
            validation_examples,
            name="validation",
        )

        # Train the model
        try:
            self.model.fit(
                train_objectives=[(train_dataloader, train_loss)],
                evaluator=evaluator,
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
        eval_metrics = self.evaluate(
            validation_examples,
            threshold=settings.SIMILARITY_THRESHOLD,
        )

        # Collect metrics
        metrics = {
            "training_time_seconds": training_time,
            "num_epochs": config.num_epochs,
            "num_train_steps": num_train_steps,
            "learning_rate": config.learning_rate,
            "batch_size": config.batch_size,
            "loss_function": config.loss_function,
            "final_loss": eval_metrics["mean_squared_error"],
            "eval_metrics": eval_metrics,
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
        token = token or settings.HF_TOKEN or None

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
            TrainingPair.pair_type == PairType.POSITIVE,
            TrainingPair.is_validated == 1,
        ).count()

        num_hard_neg = self.db.query(TrainingPair).filter(
            TrainingPair.pair_type == PairType.HARD_NEGATIVE,
            TrainingPair.is_validated == 1,
        ).count()

        num_easy_neg = self.db.query(TrainingPair).filter(
            TrainingPair.pair_type == PairType.EASY_NEGATIVE,
            TrainingPair.is_validated == 1,
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
            train_dataloader, validation_examples = trainer.prepare_training_data(
                db=self.db,
                batch_size=config.batch_size,
                max_seq_length=config.max_seq_length,
                loss_function=config.loss_function,
                validation_split=config.validation_split,
                random_seed=config.random_seed,
            )

            # Train
            metrics = trainer.train(
                train_dataloader=train_dataloader,
                validation_examples=validation_examples,
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
            job.final_loss = metrics["final_loss"]
            job.eval_metrics = metrics["eval_metrics"]

            # Store HF Hub URL if uploaded
            if hub_url:
                job.training_config["huggingface_url"] = hub_url

            model_path = str(Path(output_path).resolve())
            model_size_bytes = sum(
                path.stat().st_size for path in Path(model_path).rglob("*") if path.is_file()
            )
            model_version = ModelVersion(
                version_id=f"model-{uuid.uuid4().hex[:12]}",
                model_name=model_path,
                base_model=job.base_model,
                is_finetuned=True,
                training_job_id=job.job_id,
                huggingface_url=hub_url,
                performance_metrics=metrics["eval_metrics"],
                dimension=trainer.model.get_sentence_embedding_dimension(),
                model_size_mb=model_size_bytes / (1024 * 1024),
                description=f"Fine-tuned by training job {job.job_id}",
            )
            self.db.add(model_version)
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
