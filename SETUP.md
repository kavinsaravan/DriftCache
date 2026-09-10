# DriftCache Setup Guide

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 20+
- Anthropic API Key

## Quick Start with Docker

### 1. Clone and Configure

```bash
cd Projects/DriftCache
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:
```
ANTHROPIC_API_KEY=your_actual_api_key_here
```

### 2. Start Services

```bash
docker-compose up -d
```

This will start:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Backend API (port 8000)
- Frontend (port 3000)

### 3. Access the Application

- **Frontend Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health

## Local Development Setup

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

## Database Migrations

```bash
cd backend

# Initialize Alembic (first time only)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

## Testing the Cache

### Using curl

```bash
# Send a query
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What are the benefits of solar energy?",
    "model": "claude-3-5-sonnet-20241022"
  }'

# Send a semantically similar query (should hit cache)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Can you explain advantages of solar power?",
    "model": "claude-3-5-sonnet-20241022"
  }'
```

## Configuration

Key settings in `.env`:

- `SIMILARITY_THRESHOLD`: Minimum similarity score for cache hits (0.0-1.0)
- `CACHE_TTL_SECONDS`: How long to keep cached responses
- `EMBEDDING_MODEL`: Sentence transformer model to use
- `DEFAULT_MODEL`: Default Claude model

## Troubleshooting

### Backend won't start
- Check PostgreSQL is running: `docker ps | grep postgres`
- Check Redis is running: `docker ps | grep redis`
- Verify API key is set in `.env`

### Frontend can't connect to API
- Verify backend is running on port 8000
- Check CORS settings in `backend/app/core/config.py`
- Ensure proxy is configured in `frontend/vite.config.ts`

### Cache not working
- Check Redis connection: `redis-cli ping`
- Verify embedding model downloaded
- Check logs: `docker-compose logs backend`

## Next Steps

1. Review the [Architecture Documentation](ARCHITECTURE.md)
2. Explore the API at http://localhost:8000/docs
3. Check the frontend dashboard at http://localhost:3000
4. Start building your integration!
