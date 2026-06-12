# DriftCache

**Adaptive Semantic Caching & Autonomous Optimization Platform for LLM Systems**

## Overview

DriftCache is an AI infrastructure platform that sits between applications and large language model providers. Instead of applications calling an LLM directly, they call DriftCache first, which intelligently decides whether to reuse cached responses or forward requests to the actual LLM.

## The Problem

LLM systems are expensive because:
- Many prompts are repetitive
- Users rephrase the same questions
- Enterprises repeatedly ask similar queries
- AI systems waste tokens recomputing similar outputs

### Example

**User A:** "Summarize the benefits of solar energy."
**User B:** "Can you explain advantages of solar power?"

These are semantically identical, but traditional systems send BOTH requests to the LLM, paying twice and incurring full latency twice.

## The Solution

DriftCache uses **semantic similarity** instead of exact string matching:
- Embeddings + vector search for semantic matching
- Autonomous optimization and self-repair
- Production-grade observability

## Key Features

- **Lower LLM costs** - Avoid redundant API calls
- **Lower latency** - Serve from cache when possible
- **Scalable infrastructure** - Built for production workloads
- **Autonomous optimization** - Self-healing and adaptive
- **Semantic caching** - Beyond exact string matching

## Technology Stack

- **Backend:** FastAPI, Python
- **Frontend:** React
- **Databases:** PostgreSQL, Redis
- **LLM:** Claude (Anthropic)
- **AI Framework:** LangChain, LangGraph
- **Infrastructure:** Docker

## Project Structure

```
DriftCache/
├── backend/           # FastAPI backend
├── frontend/          # React frontend
├── docker/            # Docker configurations
├── docs/              # Documentation
└── README.md
```

## Getting Started


