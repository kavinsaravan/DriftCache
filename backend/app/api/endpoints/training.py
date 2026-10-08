"""
Training API Endpoints

Provides REST API for:
1. Collecting training data from cache interactions
2. Starting fine-tuning jobs
3. Monitoring training progress
4. Managing model versions
5. Deploying a trained model to the live semantic index
"""
import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.database.session import get_db, get_db_manager
from app.models.training_schemas import (
    DataCollectionRequest,
    DataCollectionResponse,
    TrainingJobCreate,
    TrainingJobResponse,
    TrainingConfig,
    ModelVersionResponse,
)
from app.models.training_job import TrainingJob
from app.models.model_version import ModelVersion
from app.models.embedding_record import EmbeddingRecord
from app.models.index_version import IndexVersion
from app.training.data_generator import TrainingDataGenerator
from app.training.trainer import TrainingJobManager
from app.training.deployment import deploy_embedding_model
from app.core.config import settings
from datetime import datetime

logger = logging.getLogger(__name__)

def require_training_enabled() -> None:
    if not settings.ENABLE_TRAINING:
        raise HTTPException(status_code=503, detail="Model training is disabled")


router = APIRouter(dependencies=[Depends(require_training_enabled)])


# ==================== Data Collection Endpoints ====================

@router.post("/collect-data", response_model=DataCollectionResponse)
async def collect_training_data(
    request: DataCollectionRequest,
    db: Session = Depends(get_db)
):
    """
    Collect training data from cache interactions

    This loads curated labels and records observed cache matches for review.

    **Strategy:**
    - Validated positives: Canonical semantic-duplicate fixtures
    - Observed positives: Real cache matches retained as unvalidated candidates
    - Hard negatives: Canonical similar-looking prompts that must not match
    - Easy negatives: Prompts drawn from different curated topics

    **Returns:**
    - Number of pairs collected by type
    - Total collection time
    """
    try:
        logger.info("Starting training data collection")

        # Create data generator
        generator = TrainingDataGenerator(db)

        # Collect data
        start_time = datetime.utcnow()

        result = generator.collect_training_data(
            min_positive_pairs=request.min_positive_pairs,
            min_hard_negatives=request.min_hard_negatives,
            min_easy_negatives=request.min_easy_negatives,
            positive_threshold=request.positive_threshold,
            hard_negative_min=request.hard_negative_min,
            hard_negative_max=request.hard_negative_max,
            days_lookback=request.days_lookback
        )

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        return DataCollectionResponse(
            num_positive_pairs=result["num_positive_pairs"],
            num_hard_negative_pairs=result["num_hard_negative_pairs"],
            num_easy_negative_pairs=result["num_easy_negative_pairs"],
            total_pairs=result["total_pairs"],
            collection_time_seconds=duration,
            message=f"Successfully collected {result['total_pairs']} training pairs"
        )

    except Exception as e:
        logger.error(f"Data collection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Training Job Endpoints ====================

@router.post("/jobs", response_model=TrainingJobResponse)
async def create_training_job(
    request: TrainingJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create and start a fine-tuning job

    This will:
    1. Create a training job record
    2. Start fine-tuning in the background using PyTorch
    3. Optionally upload the model to Hugging Face Hub

    **Training Process:**
    - Loads training pairs from database
    - Fine-tunes using a configured contrastive loss
    - Saves checkpoints during training
    - Evaluates on a held-out validation split
    - Optionally uploads to HF Hub

    **Returns:**
    - Job ID for tracking progress
    - Initial job status
    """
    try:
        logger.info("Creating training job")

        # Create job manager
        manager = TrainingJobManager(db)

        # Create job
        job = manager.create_training_job(
            base_model=request.base_model,
            config=request.training_config or TrainingConfig(),
            output_model_name=request.output_model_name
        )

        # Start training in background
        job_id = job.job_id
        upload_to_hub = request.upload_to_hub
        hub_model_id = request.hub_model_id

        def run_training():
            try:
                with get_db_manager().session_scope() as background_db:
                    TrainingJobManager(background_db).run_training_job(
                        job_id=job_id,
                        upload_to_hub=upload_to_hub,
                        hub_model_id=hub_model_id,
                    )
            except Exception as e:
                logger.error(f"Background training failed: {e}")

        background_tasks.add_task(run_training)

        return TrainingJobResponse.model_validate(job)

    except Exception as e:
        logger.error(f"Failed to create training job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=TrainingJobResponse)
async def get_training_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get training job status and results

    **Returns:**
    - Job status (pending, training, completed, failed)
    - Training progress
    - Evaluation metrics (if completed)
    - Error message (if failed)
    """
    job = db.query(TrainingJob).filter(
        TrainingJob.job_id == job_id
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")

    return TrainingJobResponse.model_validate(job)


@router.get("/jobs", response_model=List[TrainingJobResponse])
async def list_training_jobs(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    List all training jobs

    **Returns:**
    - List of training jobs, most recent first
    """
    jobs = db.query(TrainingJob).order_by(
        TrainingJob.created_at.desc()
    ).limit(limit).all()

    return [TrainingJobResponse.model_validate(job) for job in jobs]


# ==================== Model Version Endpoints ====================

@router.get("/models", response_model=List[ModelVersionResponse])
async def list_model_versions(
    db: Session = Depends(get_db)
):
    """
    List all embedding model versions

    **Returns:**
    - List of model versions
    - Performance metrics for each
    - Deployment status
    """
    models = db.query(ModelVersion).order_by(
        ModelVersion.created_at.desc()
    ).all()

    return [ModelVersionResponse.model_validate(model) for model in models]


@router.get("/models/{version_id}", response_model=ModelVersionResponse)
async def get_model_version(
    version_id: str,
    db: Session = Depends(get_db)
):
    """
    Get details for a specific model version

    **Returns:**
    - Model metadata
    - Performance metrics
    - Training info
    - Deployment status
    """
    model = db.query(ModelVersion).filter(
        ModelVersion.version_id == version_id
    ).first()

    if not model:
        raise HTTPException(status_code=404, detail="Model version not found")

    return ModelVersionResponse.model_validate(model)


@router.post("/models/{version_id}/deploy")
async def deploy_model_version(
    version_id: str,
    traffic_percentage: float = 100.0,
    db: Session = Depends(get_db)
):
    """
    Deploy a model version and rebuild the live semantic index.

    **Args:**
    - traffic_percentage: must be 100 because the service has one live index

    **Returns:**
    - Deployment status
    """
    if traffic_percentage != 100:
        raise HTTPException(
            status_code=400,
            detail="DriftCache uses one live FAISS index; deployments must use 100% traffic"
        )

    # Get model
    model = db.query(ModelVersion).filter(
        ModelVersion.version_id == version_id
    ).first()

    if not model:
        raise HTTPException(status_code=404, detail="Model version not found")

    try:
        deployment = await run_in_threadpool(deploy_embedding_model, model.model_name)
    except Exception as exc:
        logger.exception("Failed to deploy embedding model %s", version_id)
        raise HTTPException(status_code=500, detail=f"Model deployment failed: {exc}") from exc

    deployed_at = datetime.utcnow()
    try:
        db.query(ModelVersion).filter(ModelVersion.id != model.id).update(
            {
                ModelVersion.is_active: False,
                ModelVersion.traffic_percentage: 0.0,
            },
            synchronize_session=False,
        )
        model.is_active = True
        model.traffic_percentage = 100.0
        model.deployed_at = deployed_at

        db.query(EmbeddingRecord).update(
            {
                EmbeddingRecord.embedding_model: deployment.model_name,
                EmbeddingRecord.embedding_dimension: deployment.dimension,
            },
            synchronize_session=False,
        )
        db.query(IndexVersion).filter(IndexVersion.active_until.is_(None)).update(
            {
                IndexVersion.active_until: deployed_at,
                IndexVersion.is_active: False,
            },
            synchronize_session=False,
        )
        db.add(
            IndexVersion(
                version_name=f"deploy-{deployed_at:%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}",
                embedding_model=deployment.model_name,
                embedding_dimension=deployment.dimension,
                index_type=settings.VECTOR_INDEX_TYPE,
                vector_count=deployment.rebuilt_vectors,
                reason=f"Deployed model version {version_id}",
                created_by="training_api",
                file_path=settings.get_index_path(),
                is_active=True,
                active_from=deployed_at,
            )
        )
        db.commit()
        db.refresh(model)
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to persist deployment metadata; restoring previous model")
        try:
            await run_in_threadpool(
                deploy_embedding_model,
                deployment.previous_model_name,
            )
        except Exception:
            logger.exception("Failed to restore previous embedding model")
        raise HTTPException(
            status_code=500,
            detail="Model deployment metadata could not be committed",
        ) from exc

    logger.info("Deployed model %s and rebuilt %s vectors", version_id, deployment.rebuilt_vectors)

    return {
        "version_id": version_id,
        "is_active": True,
        "traffic_percentage": 100.0,
        "embedding_dimension": deployment.dimension,
        "rebuilt_vectors": deployment.rebuilt_vectors,
        "deployed_at": model.deployed_at,
        "message": "Model deployed to all traffic and the FAISS index was rebuilt"
    }


@router.post("/models/{version_id}/deactivate")
async def deactivate_model_version(
    version_id: str,
    db: Session = Depends(get_db)
):
    """
    Deactivate a model version

    **Returns:**
    - Deactivation status
    """
    model = db.query(ModelVersion).filter(
        ModelVersion.version_id == version_id
    ).first()

    if not model:
        raise HTTPException(status_code=404, detail="Model version not found")

    if model.is_active:
        raise HTTPException(
            status_code=409,
            detail="Deploy another model before deactivating the live embedding model",
        )

    # Mark an inactive registry entry as deprecated.
    model.is_active = False
    model.traffic_percentage = 0.0
    model.deprecated_at = datetime.utcnow()

    db.commit()

    logger.info(f"Deactivated model {version_id}")

    return {
        "version_id": version_id,
        "is_active": False,
        "deprecated_at": model.deprecated_at,
        "message": "Model deactivated"
    }


# ==================== Stats Endpoint ====================

@router.get("/stats")
async def get_training_stats(
    db: Session = Depends(get_db)
):
    """
    Get overall training statistics

    **Returns:**
    - Number of training pairs collected
    - Number of completed training jobs
    - Number of active models
    - Latest training metrics
    """
    from app.models.training_pair import TrainingPair, PairType

    # Count training pairs
    num_positive = db.query(TrainingPair).filter(
        TrainingPair.pair_type == PairType.POSITIVE
    ).count()

    num_hard_neg = db.query(TrainingPair).filter(
        TrainingPair.pair_type == PairType.HARD_NEGATIVE
    ).count()

    num_easy_neg = db.query(TrainingPair).filter(
        TrainingPair.pair_type == PairType.EASY_NEGATIVE
    ).count()

    # Count jobs
    from app.models.training_job import JobStatus

    num_completed_jobs = db.query(TrainingJob).filter(
        TrainingJob.status == JobStatus.COMPLETED
    ).count()

    num_failed_jobs = db.query(TrainingJob).filter(
        TrainingJob.status == JobStatus.FAILED
    ).count()

    # Count active models
    num_active_models = db.query(ModelVersion).filter(
        ModelVersion.is_active == True
    ).count()

    # Get latest completed job
    latest_job = db.query(TrainingJob).filter(
        TrainingJob.status == JobStatus.COMPLETED
    ).order_by(TrainingJob.completed_at.desc()).first()

    stats = {
        "training_data": {
            "num_positive_pairs": num_positive,
            "num_hard_negative_pairs": num_hard_neg,
            "num_easy_negative_pairs": num_easy_neg,
            "total_pairs": num_positive + num_hard_neg + num_easy_neg,
        },
        "training_jobs": {
            "num_completed": num_completed_jobs,
            "num_failed": num_failed_jobs,
        },
        "models": {
            "num_active": num_active_models,
        },
        "latest_training": {
            "job_id": latest_job.job_id if latest_job else None,
            "completed_at": latest_job.completed_at if latest_job else None,
            "metrics": latest_job.eval_metrics if latest_job else {},
        } if latest_job else None,
    }

    return stats
