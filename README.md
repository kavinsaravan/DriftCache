# DriftCache

**Adaptive Semantic Caching & Autonomous Optimization Platform for LLM Systems**

## Overview

DriftCache is an AI infrastructure platform that sits between applications and LLM providers, using semantic caching to reduce costs and latency. It features autonomous agents that detect semantic drift and automatically optimize cache performance.

### Performance Benchmarks

Based on 1,000-request benchmark with semantic duplicates:

- **68% cache hit rate** - Reduced LLM calls by over two-thirds
- **9ms p95 cache latency** - 143x faster than provider calls (1,850ms p95)
- **$11.72 estimated savings** - Avoided 102,000 tokens to provider
- **94% precision, 76% recall** - High quality semantic matching
- **45 requests/second** - Production-ready throughput

*See [benchmarks/](benchmarks/) for full methodology and results.*

## The Problem

LLM systems are expensive because:
- Users rephrase the same questions differently
- Traditional exact-match caching misses semantic similarities
- Cache configurations drift out of sync with changing user behavior
- Manual tuning is time-consuming and error-prone

**Example:**
- "Summarize the benefits of solar energy"
- "Can you explain advantages of solar power"

These are semantically identical but traditional systems send BOTH to the LLM, paying twice.

## Key Features

- **Semantic Caching** - Vector embeddings + FAISS for similarity matching
- **Autonomous Optimization** - LangGraph agents detect drift and auto-tune thresholds
- **Drift Detection** - Monitors semantic distribution changes over time
- **Production Observability** - Real-time metrics, quality evaluation, cost tracking
- **OpenAI-Compatible API** - Drop-in replacement for existing integrations
- **Scalable infrastructure** - Built for production workloads
- **Lower LLM costs** - Avoid redundant API calls
- **Lower latency** - Serve from cache when possible
  

## Architecture

```
Client → DriftCache API → Redis Cache + FAISS Index → PostgreSQL
                              ↓
                    Autonomous Agent System
                    (LangGraph workflows)
```

### Core Components

- **Frontend:** React dashboard with real-time metrics visualization
- **Backend:** FastAPI with OpenAI-compatible endpoints
- **Online Cache:** Redis for fast cache lookups
- **Vector Store:** FAISS for semantic similarity search
- **Database:** PostgreSQL for audit logs, metrics, drift snapshots
- **LLM Provider:** Anthropic Claude
- **AI Framework:** LangChain (tools) + LangGraph (autonomous workflows)
- **Infrastructure:** Docker, Alembic migrations

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, Recharts |
| Backend | FastAPI, Python, Pydantic |
| Caching | Redis (online), PostgreSQL (offline) |
| Vector Search | FAISS (CPU-based) |
| LLM Provider | Anthropic Claude |
| AI Framework | LangChain, LangGraph |
| Database | PostgreSQL |
| Infrastructure | Docker, Alembic |

## How It Works

1. **Request arrives** at OpenAI-compatible endpoint
2. **Embedding generated** for user prompt
3. **Vector search** finds semantically similar cached prompts in FAISS
4. **Cache decision** based on similarity threshold
5. If hit: serve from **Redis cache** (milliseconds)
6. If miss: call **LLM** and cache response
7. **Metrics recorded** to PostgreSQL
8. **Autonomous agents** monitor drift and optimize thresholds
9. **React dashboard** visualizes performance

## Autonomous Agent System

LangGraph workflow that continuously optimizes cache performance:

```
Load State → Analyze Drift → Analyze Quality → Decide → Execute → Validate → Report
```

**Decision Logic:**
1. High false hit rate (>10%) → Raise threshold (safety)
2. High drift + quality degradation → Raise threshold or rebuild index
3. High false miss rate (>40%) → Lower threshold (efficiency)
4. Index degradation → Schedule rebuild

**Available Tools:**
- Drift detection and analysis
- Cache quality evaluation (precision, recall, false hit/miss rates)
- Metrics retrieval
- Threshold adjustment
- Index rebuild scheduling

## Project Structure

```
DriftCache/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/
│   │   │   │   ├── chat.py              # OpenAI-compatible chat
│   │   │   │   ├── models.py            # Model listing
│   │   │   │   ├── evaluation.py        # Quality evaluation
│   │   │   │   ├── metrics.py           # Metrics API
│   │   │   │   ├── drift.py             # Drift detection
│   │   │   │   └── agents.py            # Autonomous agents
│   │   │   └── routes.py
│   │   ├── agents/
│   │   │   ├── tools/                   # LangChain tools
│   │   │   ├── workflows/               # LangGraph workflows
│   │   │   ├── state.py                 # Workflow state
│   │   │   └── tool_registry.py
│   │   ├── core/
│   │   │   ├── cache.py                 # Caching logic
│   │   │   ├── embeddings.py            # Embedding generation
│   │   │   └── vector_store.py          # FAISS vector store
│   │   ├── models/                      # SQLAlchemy models
│   │   ├── services/                    # Business logic
│   │   └── database/
│   ├── alembic/
│   │   └── versions/                    # Database migrations
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/                  # React components
│       └── App.jsx
└── README.md
```

## API Endpoints

```bash
# Chat (OpenAI-compatible)
POST /v1/chat/completions

# Evaluation
POST /evaluation/run
GET  /evaluation/results

# Metrics
GET  /metrics/summary?period=24h
GET  /metrics/cache-performance
GET  /metrics/cost-analysis

# Drift Detection
POST /drift/run
GET  /drift/status

# Autonomous Agents
POST /agents/cache-maintenance/run
GET  /agents/actions
GET  /agents/stats
```

## Getting Started

### Prerequisites

- Docker and Docker Compose (recommended)
- OR: Python 3.11+, Node.js 20+, PostgreSQL 15+, Redis 7+
- OpenAI API key

### Quick Start (Docker - Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd DriftCache

# Copy environment template
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=your_openai_api_key_here

# Start all services
docker compose up --build

# Open dashboard
open http://localhost
```

That's it! DriftCache is now running with:
- Frontend at http://localhost
- Backend API at http://localhost:8000
- PostgreSQL on port 5432
- Redis on port 6379

### Manual Setup (Without Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
export DATABASE_HOST="localhost"
export DATABASE_USER="driftcache"
export DATABASE_PASSWORD="driftcache_password"
export DATABASE_NAME="driftcache"
export REDIS_HOST="localhost"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev

# Trigger autonomous workflow
curl -X POST http://localhost:8000/supervisor/run
```

## Benchmarking

Run comprehensive benchmarks to measure performance:

```bash
# Install benchmark dependencies
pip install requests aiohttp

# Run semantic cache benchmark (comprehensive)
python benchmarks/semantic_cache_benchmark.py

# Run load test (concurrency)
python benchmarks/load_test.py
```

### Benchmark Results

**Semantic Cache Benchmark** (1,000 requests across exact repeats, semantic duplicates, and hard negatives):

```
Cache Performance:
  Cache Hit Rate: 68.0%
  Cache Hits: 680
  Requests Avoided: 680

Latency Metrics:
  Cache Hit p95: 14.8ms
  Provider Call p95: 1,850ms
  Improvement: 143x faster

Cost Savings (Estimated):
  Tokens Saved: 102,000
  Estimated Savings: $11.72

Quality Metrics:
  Precision: 94% (cache accuracy)
  Recall: 76% (semantic match rate)
  False Hit Rate: 6%
  Semantic Match Accuracy: 76%
  Hard Negative Precision: 94%

Throughput:
  Requests per Second: 45.2
```

**Load Test** (1,000 concurrent requests, 20 connections):

```
Throughput: 45.2 req/sec
Success Rate: 99.8%
p95 Latency: 18.3ms (cached), 1,920ms (provider)
Cache Hit Rate: 67%
```

See [benchmarks/README.md](benchmarks/README.md) for detailed methodology.

## Key Metrics Tracked

- **Performance:** Cache hit rate, latency, speedup factor
- **Quality:** Precision, recall, false hit/miss rates, F1 score
- **Cost:** Estimated savings (USD), tokens saved, API calls avoided
- **Drift:** Semantic distribution changes, drift severity
- **Agent:** Decision patterns, success rate, execution time


