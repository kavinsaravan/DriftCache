# DriftCache

**Semantic Caching Platform for LLM Systems**

DriftCache is an OpenAI-compatible API proxy that caches semantically similar LLM requests using sentence transformers and FAISS vector search. It reduces repeated API calls by recognizing paraphrased queries, while monitoring cache quality and semantic drift over time.

## Key Features

- **Semantic Caching** - Sentence Transformers + FAISS to recognize paraphrased queries beyond exact matches
- **OpenAI-Compatible Proxy** - Compatible with `/api/v1/chat/completions` and `/api/v1/models` endpoints
- **Dual Storage Architecture** - Redis for fast retrieval + PostgreSQL for analytics and persistence
- **Drift Detection** - Statistical monitoring (KS-test, Wasserstein distance) to detect query distribution changes
- **Fine-Tuning Pipeline** - PyTorch-based contrastive learning to adapt embeddings to domain-specific queries
- **Threshold Evaluation** - Offline utilities for comparing precision and recall at candidate thresholds

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, Python 3.11, Pydantic |
| Frontend | React, TypeScript, Recharts, TailwindCSS |
| Caching | Redis 7, PostgreSQL 15 |
| Vector Search | FAISS, sentence-transformers (all-MiniLM-L6-v2) |
| ML Training | PyTorch 2.2, Sentence Transformers, Hugging Face |
| Drift Detection | SciPy (KS-test, Wasserstein), NumPy |
| LLM Providers | OpenAI GPT-4/4o-mini, Anthropic Claude |
| Infrastructure | Docker, Alembic, SQLAlchemy |

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
│  │  Evaluation & Monitoring            │   │
│  │  - Drift Detection (SciPy stats)    │   │
│  │  - Offline Threshold Analysis       │   │
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

## Quick Start

```bash
# Clone and setup
git clone https://github.com/kavinsaravan/DriftCache.git
cd DriftCache
cp .env.example .env
# Configure environment variables in .env:
# - API_KEY: Bootstrap administrator key used to provision project keys
# - METRICS_API_KEY: Read-only key for dashboard (optional, recommended)
# - OPENAI_API_KEY or ANTHROPIC_API_KEY: For LLM provider

# Start with Docker
make up

# Open dashboard
open http://localhost
```

The root Makefile is the supported development interface:

```bash
make help
make test
make smoke
make demo DEMO_SCENARIO=semantic
make benchmark
```

Use `API_BASE_URL=https://your-host` for a remote API and export
`DRIFTCACHE_API_KEY` when authentication is enabled.

### Create a project key

Use the bootstrap `API_KEY` to create one isolated project credential for each
application integrating with DriftCache:

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Support assistant","key_name":"production"}'
```

The response contains a `dc_live_...` key exactly once. Store it in the client
application's secret manager as `DRIFTCACHE_API_KEY`. DriftCache stores only its
SHA-256 hash and derives the project's cache namespace from the verified key.
The bootstrap key can list projects, create additional keys, and revoke keys:

```text
GET    /api/v1/projects
POST   /api/v1/projects/{project_id}/keys
GET    /api/v1/projects/{project_id}/keys
DELETE /api/v1/projects/{project_id}/keys/{api_key_id}
```

### Dashboard authentication and request history

Enter a read-only `METRICS_API_KEY` or a project API key in the dashboard's
**Metrics or project API key** field, then select **Apply key**. The key is stored
only in the current tab's session storage and sent as a Bearer token. Do not put
an administrator key into frontend build variables. Changing or clearing the key
resets cached dashboard queries. A project key can see only its own tenant;
the shared metrics key sees the default tenant.

Request Explorer reads individual cache decisions, including misses, from
`GET /api/v1/metrics/requests?limit=100&offset=0&period=24h`. Results are paginated,
newest first; search and status filters apply to the displayed page. CSV export
uses the displayed events. API errors are shown explicitly. Sample data is used
only when `VITE_USE_MOCK_DATA=true`, with a visible demo banner.

Cache matching requires the same provider model by default. Compatible
below-threshold candidates contribute similarity observations to drift monitoring
without being served or counted as hits; requests with no compatible candidate
have no similarity observation. Historical missing scores are not backfilled.

Each stored response has one absolute expiration deadline shared by Redis,
vector metadata, and database history. Lookup, cleanup, and index rebuilds honor
that deadline, including custom TTLs. Legacy persisted vectors without an
expiration deadline expire conservatively rather than receiving a new lifetime.
The Anthropic adapter sends all system instructions as ordered text blocks in
both streaming and non-streaming requests. Normal Claude completions map to
`stop`; token limits map to `length`. Only confirmed normal completions are
cached. A stream ending without its terminal message event raises an error
instead of marking the partial answer complete.


### Backend container build

Build from the repository root: `docker build -f backend/Dockerfile .`.
Compose uses this same context. The image includes the root `datasets/` directory
at `/datasets` for training-data collection. For Railway, use the repository root
as the service root and `backend/Dockerfile` as the Dockerfile path.

## Integration Guide

The proxy supports text-only chat messages and the request parameters declared in
its API schema. Unsupported fields (including tools, tool choice, response format,
and multiple completions) return HTTP 422 rather than being silently discarded.
Cache context preserves all message roles, boundaries, order, and assistant
continuations. Only the current query is matched semantically. Redis keys use
versioned canonical JSON rather than delimiter-separated fields. Entries with
older context encodings miss safely and expire normally; the cache refills as
new requests arrive.


DriftCache implements **OpenAI-compatible chat completions**, providing a proxy for LLM integrations. Just change your `base_url` to start caching responses and reducing costs.

### Quick Integration

#### Python (OpenAI SDK)

```python
import os
from openai import OpenAI

# Just point to DriftCache instead of OpenAI
client = OpenAI(
    base_url="http://localhost:8000/api/v1",
    api_key=os.environ["DRIFTCACHE_API_KEY"]
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
  baseURL: "http://localhost:8000/api/v1",
  apiKey: process.env.DRIFTCACHE_API_KEY
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
curl http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key-here" \
  -d '{
    "model": "claude-sonnet-5",
    "messages": [
      {"role": "user", "content": "What is Python?"}
    ]
  }'
```

### Framework Integration

**Note:** These examples show using DriftCache as an external client. DriftCache does not depend on LangChain or LlamaIndex internally.

#### LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8000/api/v1",
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
    api_base="http://localhost:8000/api/v1",
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
5. All decisions are logged to PostgreSQL for analytics and drift detection

**Analysis Pipeline:**
- Drift detector monitors similarity score distributions using KS-test and Wasserstein distance
- Standalone threshold benchmarks evaluate the configured similarity threshold against canonical datasets
- Fine-tuning trainer uses contrastive learning on cached query pairs to improve domain-specific matching

## API Endpoints

**Core Caching:**
```bash
POST /api/v1/chat/completions      # OpenAI-compatible chat
GET  /api/v1/models                # List models
```

**Fine-Tuning (Experimental):**
```bash
POST /api/v1/training/collect-data        # Collect training pairs from cache
POST /api/v1/training/jobs                # Start fine-tuning job
GET  /api/v1/training/jobs/{job_id}       # Monitor training progress
POST /api/v1/training/models/{version_id}/deploy
GET  /api/v1/training/stats               # Training statistics
```

**Monitoring:**
```bash
GET  /api/v1/metrics/summary       # Hit rate, latency, cost savings
GET  /api/v1/drift/latest          # Latest drift alert
```

## Fine-Tuning Pipeline

**End-to-End ML Infrastructure:**

DriftCache includes an experimental end-to-end pipeline to adapt the embedding model to your domain:

**1. Training Data Collection**
```bash
POST /api/v1/training/collect-data
```
- Generates positive pairs based on embedding similarity scores
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
- Held-out validation split
- Pair-classification accuracy, precision, recall, and F1
- Positive/negative similarity averages and mean squared error

**4. Hugging Face Integration**
- Upload models to Hugging Face Hub
- Register completed models and their validation metrics in PostgreSQL
- Deploy a model with a full FAISS re-embedding and runtime cutover
- Easy sharing and collaboration

See [the training module guide](backend/app/training/README.md) for configuration and deployment details.

## Drift Detection

DriftCache monitors semantic distribution changes using statistical methods:

**Detection Method:**
- Compares recent cache similarity scores against a reference baseline
- Uses multiple statistical tests:
  - **Kolmogorov-Smirnov test**: Detects distribution shifts (p-value threshold)
  - **Wasserstein distance**: Measures how far distributions have moved
  - **Mean shift**: Tracks average similarity score changes
  - **Variance ratio**: Monitors spread changes in similarity scores
- Requires minimum sample sizes (50 reference, 30 recent) for reliable detection

**Output:**
- Drift severity classification (no_drift, moderate_drift, high_drift)
- Statistical metrics and confidence levels
- Drift alert logging to PostgreSQL for historical analysis

Access via `GET /api/v1/drift/latest` to view current drift status.
