# DriftCache

**Semantic Caching Platform for LLM Systems**

DriftCache is an OpenAI-compatible API proxy that caches semantically similar LLM responses using sentence transformers and FAISS vector search. It reduces repeated API calls by recognizing paraphrased queries, while monitoring cache quality and semantic drift over time.

## Key Features

- **Semantic Caching** - Sentence Transformers + FAISS to recognize paraphrased queries beyond exact matches
- **OpenAI-Compatible Proxy** - Drop-in replacement for existing `/v1/chat/completions` integrations
- **Dual Storage Architecture** - Redis for fast retrieval + PostgreSQL for analytics and persistence
- **Drift Detection** - Statistical monitoring (KS-test, Wasserstein distance) to detect query distribution changes
- **Fine-Tuning Pipeline** *(Experimental)* - PyTorch-based contrastive learning to adapt embeddings to domain-specific queries
- **Threshold Optimization** - Automated search over candidate similarity thresholds with multi-objective scoring

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, Python 3.11, Pydantic |
| Frontend | React, TypeScript, Recharts, TailwindCSS |
| Caching | Redis 7, PostgreSQL 15 |
| Vector Search | FAISS, sentence-transformers (all-MiniLM-L6-v2) |
| ML Training | PyTorch 2.2, Sentence Transformers, Hugging Face |
| Drift Detection | SciPy (KS-test, Wasserstein), NumPy |
| Agent Orchestration | LangGraph (StateGraph), LangChain (BaseTool) |
| LLM Providers | OpenAI GPT-4/4o-mini, Anthropic Claude |
| Infrastructure | Docker, Alembic, SQLAlchemy |

## Project Structure

```
DriftCache/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/           
│   │   │   │   ├── chat.py         
│   │   │   │   ├── metrics.py      
│   │   │   │   ├── training.py     
│   │   │   │   ├── supervisor.py   
│   │   │   │   ├── drift.py        
│   │   │   │   ├── evaluation.py   
│   │   │   │   ├── vectorstore.py  
│   │   │   │   └── models.py       
│   │   │   └── routes.py           
│   │   ├── agents/                  
│   │   │   ├── threshold_optimizer.py
│   │   │   ├── index_rebuilder.py
│   │   │   └── supervisor.py
│   │   ├── llm/                     
│   │   │   ├── anthropic_provider.py
│   │   │   ├── openai_provider.py
│   │   │   └── router.py
│   │   ├── training/                
│   │   │   ├── data_collector.py   
│   │   │   ├── trainer.py          
│   │   │   └── evaluator.py        
│   │   ├── cache/                   
│   │   │   ├── service.py          
│   │   │   ├── store.py            
│   │   │   └── decision.py         
│   │   ├── vectorstore/            
│   │   │   ├── faiss_index.py     
│   │   │   ├── storage.py          
│   │   │   └── search.py          
│   │   ├── embeddings/              
│   │   │   ├── service.py          
│   │   │   ├── model.py           
│   │   │   └── utils.py            
│   │   ├── optimization/            
│   │   ├── drift/                  
│   │   ├── evaluation/             
│   │   ├── metrics/               
│   │   ├── database/                
│   │   ├── repositories/            
│   │   ├── services/                
│   │   ├── models/                  
│   │   ├── core/                   
│   │   └── main.py                 
│   ├── alembic/
│   │   └── versions/               
│   ├── tests/                       
│   │   ├── test_vectorstore.py
│   │   ├── test_embeddings.py
│   │   ├── test_streaming.py
│   │   └── test_gateway.py
│   ├── data/cache/                
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/                  
│   │   │   ├── Dashboard.tsx      
│   │   │   ├── CacheAnalytics.tsx  
│   │   │   ├── LatencyAnalytics.tsx
│   │   │   ├── CostSavings.tsx
│   │   │   ├── RequestExplorer.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/             
│   │   │   ├── Layout.tsx
│   │   │   ├── MetricCard.tsx
│   │   │   └── LoadingSpinner.tsx
│   │   ├── api/                     
│   │   │   ├── metricsApi.ts
│   │   │   └── mockData.ts
│   │   ├── utils/                  
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
│   ├── semantic_cache_benchmark.py  
│   ├── load_test.py                 
│   ├── datasets/                    
│   └── results/                     
├── scripts/
│   ├── populate_demo_data.py        
│   ├── simple_benchmark_simulation.py
│   ├── smoke_test.sh                
│   └── demo/                       
│       ├── run_demo.py             
│       ├── generate_drift.py       
│       ├── seed_cache.py          
│       └── prompts/               
├── docker/                          
├── data/cache/                      
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
│  │  - Model Evaluation & Versioning    │   │
│  └─────────────────────────────────────┘   │
│                                            │
│  ┌─────────────────────────────────────┐   │
│  │  Optimization & Monitoring          │   │
│  │  - Drift Detection (SciPy stats)    │   │
│  │  - Threshold Optimization           │   │
│  │  - Performance Analytics            │   │
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

### 4. Optimization & Drift Detection
- **Statistical Drift Detection**: KS-test, Wasserstein distance on similarity distributions
- **Threshold Optimization**: Grid search with multi-objective scoring (precision/recall/cost/latency)
- **Remediation Policies**: Rule-based recommendations for threshold adjustments and index rebuilds

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
# Configure environment variables in .env:
# - API_KEY: Main API key for chat/completions (required)
# - METRICS_API_KEY: Read-only key for dashboard (optional, recommended)
# - OPENAI_API_KEY or ANTHROPIC_API_KEY: For LLM provider

# Start with Docker (recommended)
docker compose up --build

# Open dashboard
open http://localhost
```

**Security Note:** The dashboard uses `METRICS_API_KEY` (read-only) instead of the main `API_KEY`. This prevents write operations but still exposes:
- Cached prompts via `/metrics/top-cached-prompts`
- Performance data for any `tenant_id`

For single-user demos, embedding `METRICS_API_KEY` in the frontend is acceptable. For production multi-tenant deployments, implement server-side rendering or a backend proxy to keep all keys secure. Set both keys in your backend `.env` file.

## Integration Guide

DriftCache is **OpenAI-compatible**, making it a drop-in replacement for existing LLM integrations. Just change your `base_url` to start caching responses and reducing costs.

### Quick Integration

#### Python (OpenAI SDK)

```python
from openai import OpenAI

# Just point to DriftCache instead of OpenAI
client = OpenAI(
    base_url="https://driftcache-api-production.up.railway.app/api/v1",
    api_key="your-api-key-here"  # Set API_KEY in backend .env
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
    api_key="your-api-key-here"
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
    api_key="your-api-key-here"
)

response = llm.complete("What is vector search?")
print(response.text)
```

### Benefits

- **Reduce Costs**: Cache hits avoid LLM API calls (save ~$0.001-0.01 per request)
- **Improve Latency**: Cached responses return in ~50ms vs 2-5 seconds for LLM calls
- **Semantic Matching**: Paraphrased queries hit the same cache (not just exact matches)
- **OpenAI Compatible**: Works with any tool/framework that supports OpenAI API


## How It Works

```
Request → Embed prompt → FAISS search → Similarity ≥ threshold?
                                              ↓
                                    Yes: Return from Redis/cache
                                    No:  Call LLM → Store response
```

**Core Flow:**
1. Incoming request is embedded using Sentence Transformers (384-dim vectors)
2. FAISS performs k-NN search against cached prompt embeddings
3. If similarity score ≥ threshold (default 0.85), retrieve from Redis
4. Otherwise, forward to LLM provider and cache the response
5. All decisions logged to PostgreSQL for drift detection and optimization

**Optimization Pipeline:**
- Drift detector monitors similarity score distributions using KS-test and Wasserstein distance
- Threshold optimizer evaluates candidate thresholds using multi-objective scoring (precision/recall/cost)
- Fine-tuning trainer uses contrastive learning on cached query pairs to improve domain-specific matching

## API Endpoints

**Core Caching:**
```bash
POST /v1/chat/completions          # OpenAI-compatible chat
GET  /v1/models                    # List models
```

**Fine-Tuning (Experimental):**
```bash
POST /training/collect-data        # Collect training pairs from cache
POST /training/jobs                # Start fine-tuning job
GET  /training/jobs/{job_id}       # Monitor training progress
POST /models/{version_id}/deploy   # Deploy fine-tuned model (requires manual integration)
GET  /training/stats               # Training statistics
```

**Optimization & Monitoring:**
```bash
POST /supervisor/run               # Run threshold optimization workflow
GET  /supervisor/latest            # Latest optimization results
GET  /metrics/cache-performance    # Hit rate, latency, cost savings
GET  /drift/status                 # Current drift severity and statistics
GET  /benchmark/summary            # Benchmark results
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

**4. Hugging Face Integration**
- Upload models to Hugging Face Hub
- Model versioning and registry
- Easy sharing and collaboration

See [FINE_TUNING_IMPLEMENTATION.md](FINE_TUNING_IMPLEMENTATION.md) for detailed documentation.

## Optimization System

**LangGraph-Powered Remediation:**

Built with **LangGraph StateGraph** for stateful workflow orchestration:

### Architecture

```
┌─────────────────────────────────────────────┐
│         LangGraph StateGraph                │
│                                             │
│  load_system_state → diagnose → recommend  │
│         ↓                                   │
│    execute_action ←─┐                       │
│         ↓           │ (conditional loop)    │
│  validate_action ───┘                       │
│         ↓                                   │
│     finalize → END                          │
└─────────────────────────────────────────────┘
```

### Workflow Steps

1. **load_system_state** - Query drift, quality, and metrics tools (LangChain BaseTool)
2. **diagnose** - Classify system into 8 health categories (healthy, low precision, high drift, stale index, etc.)
3. **recommend** - Map diagnosis to remediation actions using policy rules
4. **execute_action** - Run specialized agents (ThresholdOptimizer, IndexRebuilder)
5. **validate_action** - Check if metrics improved (precision, recall, false hit rate)
6. **Conditional routing** - Continue with more actions or finalize based on validation

All state transitions managed by LangGraph with full audit trail stored in PostgreSQL.

**Threshold Optimization:**
- Grid search over candidate thresholds (e.g., [0.75, 0.80, 0.85, 0.90, 0.95, 0.98])
- Multi-objective scoring: precision (45%), recall (25%), cost savings (20%), latency (10%)
- Safety constraints: never lower precision below 85%, penalize false hits 2x

**Drift Detection:**
- Compares recent vs. reference embedding distributions using SciPy
- Metrics: centroid shift (cosine distance), variance shift, KS-test p-value, Wasserstein distance
- Triggers optimization when drift severity reaches threshold


## Performance Metrics

Evaluation results on 140 labeled test pairs (semantic duplicates + hard negatives):

| Similarity Threshold | Precision | Recall | F1 Score | Use Case |
|---------------------|-----------|--------|----------|----------|
| **0.85** (Balanced) | **97.5%** | **55.7%** | **70.9%** | Production default - high safety with good coverage |
| **0.90** (Conservative) | **100%** | **31.4%** | **47.8%** | Maximum safety - zero wrong answers |
| 0.92 | 100% | 20.0% | 33.3% | Ultra-conservative |
| 0.95 | 100% | 5.7% | 10.8% | Near-exact match only |

**Key Insights:**
- **Precision**: Accuracy of cache hits (% of cached responses that are correct)
- **Recall**: Coverage (% of matching pairs successfully cached at this threshold)
- **Trade-off**: Higher thresholds = safer but less coverage; lower thresholds = more coverage but higher risk
- **Testing method**: Pair-wise similarity on labeled data (not full cache simulation)

At 0.85, precision of 97.5% means 1 questionable hit out of 40 on this test set.
