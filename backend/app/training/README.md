# Fine-Tuning Module

This module fine-tunes a Sentence Transformers embedding model on query pairs mined from cache history.

## Flow

1. `TrainingDataGenerator` creates positive, hard-negative, and easy-negative pairs.
2. `ContrastiveTrainer` reserves a configurable validation split and trains with Multiple Negatives Ranking Loss, Cosine Similarity Loss, or Contrastive Loss.
3. The completed job records validation loss, accuracy, precision, recall, F1, confusion counts, and average positive/negative similarity.
4. `TrainingJobManager` saves the model and creates a `ModelVersion` record. Upload to Hugging Face Hub is optional.
5. Deploying a version loads it, re-embeds every live FAISS entry, persists the replacement index, and switches the process to the new model.

DriftCache has one live FAISS index. Deployment is therefore a 100% cutover; partial traffic routing and A/B model serving are not supported.

## API

All routes require the main API key and return `503` when `ENABLE_TRAINING=false`.

```text
POST /api/v1/training/collect-data
POST /api/v1/training/jobs
GET  /api/v1/training/jobs/{job_id}
GET  /api/v1/training/models
POST /api/v1/training/models/{version_id}/deploy
GET  /api/v1/training/stats
```

Example training request:

```json
{
  "base_model": "all-MiniLM-L6-v2",
  "training_config": {
    "learning_rate": 0.00002,
    "batch_size": 16,
    "num_epochs": 3,
    "loss_function": "MultipleNegativesRankingLoss",
    "validation_split": 0.2,
    "random_seed": 42
  },
  "upload_to_hub": false
}
```

Deploy the registered model after reviewing its validation metrics:

```bash
curl -X POST \
  'http://localhost:8000/api/v1/training/models/{version_id}/deploy?traffic_percentage=100' \
  -H 'Authorization: Bearer your-api-key'
```

Training runs as a FastAPI background task. This is suitable for a single-process demonstration; a production deployment should move long-running training into a durable job queue.
