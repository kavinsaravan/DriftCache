# DriftCache

**Adaptive Semantic Caching & Autonomous Optimization Platform for LLM Systems**

DriftCache is a semantic caching layer that sits between applications and LLM providers, using embeddings and FAISS vector search to identify semantically similar queries and reuse responses, with autonomous agents to detect semantic drift over time and optimize cache performance.

## Key Features

- **Semantic Caching** - OpenAI embeddings + FAISS vector search to recognize paraphrased queries
- **Fine-Tuning Pipeline** - PyTorch & Hugging Face integration to fine-tune embeddings on domain-specific data
- **Autonomous Optimization** - LangGraph agents detect drift and auto-tune similarity thresholds
- **Self-Healing Infrastructure** - Automatic index rebuilds when degradation is detected
- **A/B Testing Framework** - Safe model deployment with gradual traffic rollout
- **OpenAI-Compatible API** - Drop-in replacement for existing integrations

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, Python 3.11, Pydantic |
| Frontend | React, Recharts, Nginx |
| Caching | Redis 7, PostgreSQL 15 |
| Vector Search | FAISS, sentence-transformers |
| ML Training | PyTorch 2.2, Hugging Face Transformers |
| LLM | OpenAI GPT-4/4o-mini, Anthropic Claude |
| AI Agents | LangChain 0.3+, LangGraph |
| Infrastructure | Docker, Alembic |

## Project Structure

```
DriftCache/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/           # API route handlers
│   │   │   │   ├── chat.py         # Chat completions (OpenAI-compatible)
│   │   │   │   ├── metrics.py      # Cache metrics & analytics
│   │   │   │   ├── training.py     # Fine-tuning pipeline
│   │   │   │   ├── supervisor.py   # Autonomous optimization
│   │   │   │   ├── drift.py        # Drift detection
│   │   │   │   ├── evaluation.py   # Cache quality evaluation
│   │   │   │   ├── vectorstore.py  # FAISS index management
│   │   │   │   └── models.py       # Model listing
│   │   │   └── routes.py           # Route registration
│   │   ├── agents/                  # LangGraph autonomous agents
│   │   │   ├── threshold_optimizer.py
│   │   │   ├── index_rebuilder.py
│   │   │   └── supervisor.py
│   │   ├── llm/                     # LLM provider integrations
│   │   │   ├── anthropic_provider.py
│   │   │   ├── openai_provider.py
│   │   │   └── router.py
│   │   ├── training/                # Fine-tuning pipeline
│   │   │   ├── data_collector.py   # Training data generation
│   │   │   ├── trainer.py          # PyTorch contrastive learning
│   │   │   └── evaluator.py        # Model evaluation
│   │   ├── cache/                   # Cache decision engine
│   │   │   ├── service.py          # Main cache orchestrator
│   │   │   ├── store.py            # Redis/PostgreSQL storage
│   │   │   └── decision.py         # Hit/miss decision logic
│   │   ├── vectorstore/             # FAISS vector search
│   │   │   ├── faiss_index.py      # FAISS operations
│   │   │   ├── storage.py          # Metadata storage
│   │   │   └── search.py           # Semantic search service
│   │   ├── embeddings/              # Embedding generation
│   │   │   ├── service.py          # Embedding service
│   │   │   ├── model.py            # sentence-transformers wrapper
│   │   │   └── utils.py            # Text processing utilities
│   │   ├── optimization/            # Multi-objective optimization
│   │   ├── drift/                   # Drift detection system
│   │   ├── evaluation/              # Cache quality evaluation
│   │   ├── metrics/                 # Metrics collection
│   │   ├── database/                # PostgreSQL connection
│   │   ├── repositories/            # Data access layer
│   │   ├── services/                # Business logic
│   │   ├── models/                  # Pydantic & SQLAlchemy schemas
│   │   ├── core/                    # Config & dependencies
│   │   └── main.py                  # FastAPI application
│   ├── alembic/
│   │   └── versions/                # Database migrations
│   ├── tests/                       # Unit & integration tests
│   │   ├── test_vectorstore.py
│   │   ├── test_embeddings.py
│   │   ├── test_streaming.py
│   │   └── test_gateway.py
│   ├── data/cache/                  # FAISS index & metadata files
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/                   # Dashboard pages
│   │   │   ├── Dashboard.tsx       # Main overview
│   │   │   ├── CacheAnalytics.tsx  # Cache performance
│   │   │   ├── LatencyAnalytics.tsx
│   │   │   ├── CostSavings.tsx
│   │   │   ├── RequestExplorer.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/              # Reusable components
│   │   │   ├── Layout.tsx
│   │   │   ├── MetricCard.tsx
│   │   │   └── LoadingSpinner.tsx
│   │   ├── api/                     # API client
│   │   │   ├── metricsApi.ts
│   │   │   └── mockData.ts
│   │   ├── utils/                   # Utility functions
│   │   │   ├── formatting.ts
│   │   │   └── constants.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── Dockerfile
├── benchmarks/
│   ├── semantic_cache_benchmark.py  # Comprehensive benchmark suite
│   ├── load_test.py                 # Concurrent load testing
│   ├── datasets/                    # Benchmark test data
│   └── results/                     # JSON benchmark outputs
├── scripts/
│   ├── populate_demo_data.py        # Populate production with demo data
│   ├── simple_benchmark_simulation.py
│   ├── smoke_test.sh                # E2E system test
│   └── demo/                        # Interactive demos
│       ├── run_demo.py             # Semantic cache demo
│       ├── generate_drift.py       # Drift detection demo
│       ├── seed_cache.py           # Seed local cache
│       └── prompts/                # Demo prompt datasets
├── docker/                          # Docker configurations
├── data/cache/                      # Shared cache data
├── docker-compose.yml
└── README.md
```

## High-Level Architecture

```
┌─────────────┐
│ Application │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│         DriftCache API                      │
│  ┌─────────────────────────────────────┐   │
│  │   Semantic Cache Layer              │   │
│  │  - Embedding Generation             │   │
│  │  - Vector Similarity Search         │   │
│  │  - Cache Hit/Miss Logic             │   │
│  └─────────────────────────────────────┘   │
│                                            │
│  ┌─────────────────────────────────────┐   │
│  │  Fine-Tuning Pipeline               │   │
│  │  - Training Data Collection         │   │
│  │  - PyTorch Contrastive Learning     │   │
│  │  - Model Evaluation & A/B Testing   │   │
│  └─────────────────────────────────────┘   │
│                                            │
│  ┌─────────────────────────────────────┐   │
│  │  Autonomous Optimization            │   │
│  │  - Drift Detection                  │   │
│  │  - Self-Repair Agents               │   │
│  │  - Performance Monitoring           │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
       │                    │
       ▼                    ▼
┌─────────────┐      ┌─────────────┐
│ PostgreSQL  │      │   Redis     │
│ (Metadata)  │      │  (Cache)    │
└─────────────┘      └─────────────┘
       │
       ▼
┌─────────────┐      ┌──────────────────┐
│   Claude    │      │ Hugging Face Hub │
│   (LLM)     │      │ (Model Registry) │
└─────────────┘      └──────────────────┘
```

## Core Components

### 1. Semantic Cache Layer
- **Embedding Service**: Generates vector embeddings from prompts
- **Vector Store**: Stores and indexes embeddings for fast similarity search
- **Cache Manager**: Handles cache hits, misses, and TTL

### 2. LLM Integration
- **Provider Abstraction**: Unified interface for LLM providers (Claude, etc.)
- **Request/Response Handling**: Manages API calls to LLM providers
- **Error Handling & Retries**: Resilient LLM communication

### 3. Fine-Tuning Pipeline (PyTorch + Hugging Face)
- **Training Data Collection**: Mines cache interactions for positive/negative pairs
- **Contrastive Learning**: PyTorch training with Multiple Negatives Ranking Loss
- **Model Evaluation**: Precision@K, Recall@K, MRR, NDCG metrics
- **Model Versioning**: Hugging Face Hub integration for model registry
- **A/B Testing**: Gradual model rollout with traffic splitting

### 4. Autonomous Optimization (LangGraph Agents)
- **Drift Detection Agent**: Monitors cache quality degradation
- **Optimization Agent**: Automatically adjusts similarity thresholds
- **Repair Agent**: Self-heals cache inconsistencies

### 5. Data Persistence
- **PostgreSQL**: Stores metadata, analytics, and configuration
- **Redis**: Fast in-memory cache for responses and embeddings

### 6. API Layer (FastAPI)
- **REST Endpoints**: HTTP API for applications
- **WebSocket**: Real-time updates and monitoring
- **Authentication**: API key management

### 7. Frontend Dashboard (React)
- **Analytics View**: Cache hit rates, cost savings
- **Configuration**: Threshold adjustments, model selection
- **Monitoring**: Real-time system health

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd DriftCache
cp .env.example .env
# Add your OPENAI_API_KEY to .env

# Start with Docker (recommended)
docker compose up --build

# Open dashboard
open http://localhost
```

Services:
- Frontend: http://localhost
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Integration Guide

DriftCache is **OpenAI-compatible**, making it a drop-in replacement for existing LLM integrations. Just change your `base_url` to start caching responses and reducing costs.

### Live Demo

Try our hosted instance:
- **API URL**: `https://driftcache-api-production.up.railway.app/api/v1`
- **Dashboard**: https://frontend-kavinsaravan-1858s-projects.vercel.app
- **Supported Models**: `claude-sonnet-5`, `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku`

### Quick Integration

#### Python (OpenAI SDK)

```python
from openai import OpenAI

# Just point to DriftCache instead of OpenAI
client = OpenAI(
    base_url="https://driftcache-api-production.up.railway.app/api/v1",
    api_key="dummy"  # Not required, but SDK expects it
)

response = client.chat.completions.create(
    model="claude-sonnet-5",
    messages=[
        {"role": "user", "content": "What is machine learning?"}
    ]
)

print(response.choices[0].message.content)
print(f"Cache hit: {response.cache_hit}")  # Check if response was cached
```

#### JavaScript/TypeScript

```javascript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: "https://driftcache-api-production.up.railway.app/api/v1",
  apiKey: "dummy"
});

const response = await client.chat.completions.create({
  model: "claude-sonnet-5",
  messages: [
    { role: "user", content: "Explain quantum computing" }
  ]
});

console.log(response.choices[0].message.content);
console.log(`Cache hit: ${response.cache_hit}`);
```

#### cURL

```bash
curl https://driftcache-api-production.up.railway.app/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-5",
    "messages": [
      {"role": "user", "content": "What is Python?"}
    ]
  }'
```

### Framework Integration

#### LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="https://driftcache-api-production.up.railway.app/api/v1",
    model="claude-sonnet-5",
    api_key="dummy"
)

response = llm.invoke("Explain semantic caching")
print(response.content)
```

#### LlamaIndex

```python
from llama_index.llms.openai import OpenAI

llm = OpenAI(
    api_base="https://driftcache-api-production.up.railway.app/api/v1",
    model="claude-sonnet-5",
    api_key="dummy"
)

response = llm.complete("What is vector search?")
print(response.text)
```

### Benefits

- **Reduce Costs**: Cache hits avoid LLM API calls (save ~$0.001-0.01 per request)
- **Improve Latency**: Cached responses return in ~50ms vs 2-5 seconds for LLM calls
- **Semantic Matching**: Paraphrased queries hit the same cache (not just exact matches)
- **OpenAI Compatible**: Works with any tool/framework that supports OpenAI API


## Performance Metrics

Based on 1,000-request benchmark:

- **68% cache hit rate** - Reduced LLM calls by over two-thirds
- **15ms p95 cache latency** - 144x faster than provider calls (1,850ms p95)
- **$11.72 estimated savings** - Per 1,000 requests (102,000 tokens saved)
- **94% precision, 76% recall** - High quality semantic matching
- **45 requests/second** - Production-ready throughput

## API Endpoints

**Core Caching:**
```bash
POST /v1/chat/completions          # OpenAI-compatible chat
GET  /v1/models                    # List models
```

**Fine-Tuning:**
```bash
POST /training/collect-data        # Collect training pairs from cache
POST /training/jobs                # Start fine-tuning job
GET  /training/jobs/{job_id}       # Monitor training progress
POST /models/{version_id}/deploy   # Deploy model with A/B testing
GET  /training/stats               # Training statistics
```

**Autonomous Agents:**
```bash
POST /supervisor/run               # Trigger autonomous optimization
GET  /supervisor/latest            # Most recent workflow
GET  /benchmark/summary            # Latest benchmark results
```

**Metrics & Drift:**
```bash
GET  /metrics/cache-performance    # Hit rate, latency
GET  /drift/status                 # Current drift score
```

## Fine-Tuning Pipeline

**End-to-End ML Infrastructure:**

DriftCache includes a complete fine-tuning pipeline to adapt the embedding model to your specific domain:

**1. Training Data Collection**
```bash
POST /api/v1/training/collect-data
```
- Automatically mines cache interactions
- Generates positive pairs (high similarity, cache hits)
- Generates hard negatives (medium similarity, shouldn't match)
- Generates easy negatives (random dissimilar queries)

**2. PyTorch Training**
```bash
POST /api/v1/training/jobs
```
- Contrastive learning with Multiple Negatives Ranking Loss
- Learning rate warmup and checkpoint management
- Configurable hyperparameters (batch size, epochs, learning rate)

**3. Model Evaluation**
- Precision@K, Recall@K metrics
- Mean Reciprocal Rank (MRR)
- Normalized Discounted Cumulative Gain (NDCG)
- Latency benchmarking

**4. A/B Testing & Deployment**
```bash
POST /api/v1/training/models/{version_id}/deploy
```
- Deploy new models with traffic percentage (10% → 50% → 100%)
- Compare performance against baseline
- Safe rollback if regression detected

**5. Hugging Face Integration**
- Upload models to Hugging Face Hub
- Model versioning and registry
- Easy sharing and collaboration

See [FINE_TUNING_IMPLEMENTATION.md](FINE_TUNING_IMPLEMENTATION.md) for detailed documentation.

## Autonomous Agent System

**3-Layer Architecture:**

1. **Tool Layer** - 10 LangChain tools (drift detection, quality evaluation, threshold tuning, index rebuild)
2. **Agent Layer** - Specialized agents (Threshold Optimizer, Index Rebuilder)
3. **Orchestration Layer** - Supervisor agent with 8-category diagnosis

**How It Works:**
- Monitors semantic drift using KL divergence and centroid shift
- Tests multiple threshold candidates (0.75-0.98)
- Multi-objective optimization: precision 45%, recall 25%, cost 20%, latency 10%
- Safe index rebuild: build new → validate → swap → backup
- Complete audit trail of all decisions
