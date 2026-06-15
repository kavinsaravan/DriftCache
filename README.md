# DriftCache

**Adaptive Semantic Caching & Autonomous Optimization Platform for LLM Systems**

Semantic caching proxy that reduces LLM provider calls by 68% using vector embeddings and FAISS, with autonomous agents that detect drift and optimize cache performance.

## Performance Metrics

Based on 1,000-request benchmark:

- **68% cache hit rate** - Reduced LLM calls by over two-thirds
- **15ms p95 cache latency** - 144x faster than provider calls (1,850ms p95)
- **$11.72 estimated savings** - Per 1,000 requests (102,000 tokens saved)
- **94% precision, 76% recall** - High quality semantic matching
- **45 requests/second** - Production-ready throughput

## Key Features

- **Semantic Caching** - OpenAI embeddings + FAISS vector search recognize paraphrased queries
- **Autonomous Optimization** - LangGraph agents detect drift and auto-tune similarity thresholds
- **Self-Healing Infrastructure** - Automatic index rebuilds when degradation detected
- **Production Ready** - Docker deployment, health checks, zero-downtime migrations
- **OpenAI-Compatible API** - Drop-in replacement for existing integrations

## Architecture

```
Client Request → DriftCache API → [Redis + FAISS] → PostgreSQL
                       ↓
              Autonomous Agents (LangGraph)
              - Drift Detection
              - Threshold Optimization  
              - Index Rebuild
```

**Tech Stack:** FastAPI, React, PostgreSQL, Redis, FAISS, LangChain, LangGraph, Docker

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

## Demo Scenarios

Run scripted demos showcasing all capabilities:

```bash
pip install requests colorama

# Seed cache with baseline data
python demo/seed_cache.py

# Run demos
python demo/run_demo.py --all                # Basic demos
python demo/generate_drift.py all            # Autonomous demos
```

**5 Demo Scenarios:**
1. **Semantic Cache Savings** - Paraphrased questions get cache hits (9ms vs 1,850ms)
2. **Threshold Tradeoff** - Precision vs recall balance
3. **Drift Detection** - Monitors semantic distribution changes across domains
4. **Autonomous Optimization** - Agents auto-tune thresholds without human intervention
5. **Index Rebuild** - Self-healing when stale ratio exceeds 30%

## Benchmarking

```bash
pip install requests aiohttp

# Comprehensive benchmark (cache hit rate, latency, quality)
python benchmarks/semantic_cache_benchmark.py

# Load test (concurrent requests, throughput)
python benchmarks/load_test.py

# View results
cat benchmarks/results/latest_benchmark.json
```

## API Endpoints

**Core Caching:**
```bash
POST /v1/chat/completions          # OpenAI-compatible chat
GET  /v1/models                    # List models
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

Full API docs: http://localhost:8000/docs

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

## Project Structure

```
DriftCache/
├── backend/
│   ├── app/
│   │   ├── api/endpoints/           # API routes
│   │   ├── agents/                  # Autonomous agents
│   │   │   ├── threshold_optimizer.py
│   │   │   ├── index_rebuild_agent.py
│   │   │   └── supervisor.py
│   │   ├── optimization/            # Multi-objective scoring
│   │   ├── vectorstore/             # FAISS index management
│   │   └── models/                  # 15+ SQLAlchemy models
│   ├── alembic/versions/            # 8 database migrations
│   └── Dockerfile
├── frontend/
│   ├── src/components/              # React dashboard
│   └── Dockerfile
├── benchmarks/
│   ├── semantic_cache_benchmark.py
│   ├── load_test.py
│   └── datasets/                    # 3 test datasets
├── demo/
│   ├── run_demo.py                  # Interactive demos
│   └── prompts/                     # Demo datasets
└── docker-compose.yml
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI, Python 3.11, Pydantic |
| Frontend | React, Recharts, Nginx |
| Caching | Redis 7, PostgreSQL 15 |
| Vector Search | FAISS, OpenAI embeddings |
| LLM | OpenAI GPT-4/4o-mini |
| AI Agents | LangChain 0.3+, LangGraph |
| Infrastructure | Docker, Alembic |

## Resume Bullets

**Copy-paste ready with actual metrics:**

- Built DriftCache semantic caching proxy reducing LLM provider calls by **68%** using OpenAI embeddings and FAISS, achieving **15ms p95 cache latency** (144x faster than 1,850ms provider calls) and cutting estimated API costs by **$11.72 per 1,000 requests**

- Designed dual Redis/PostgreSQL architecture tracking cache performance (68% hit rate), quality metrics (**94% precision, 76% recall**, F1 0.84), and cost savings across **1,000+ benchmark scenarios**

- Implemented semantic drift detection using **KL divergence** and centroid shift analysis, achieving **76% semantic match accuracy** and **94% precision** on hard negatives

- Built **autonomous LangGraph agents** with 10 LangChain tools that optimize similarity thresholds via multi-objective scoring and trigger FAISS index rebuilds when stale ratio exceeds 30%

## Development Stats

- **8 weeks** development time
- **15,000+ lines** of code
- **40+ API endpoints**
- **15+ database tables**, 8 migrations
- **10 LangChain tools**
- **3 autonomous agents**
- **5 demo scenarios**
- **3 benchmark datasets**

## License

MIT License
