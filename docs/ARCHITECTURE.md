# DriftCache Architecture

## System Overview

DriftCache is a semantic caching layer that sits between applications and LLM providers, using embeddings and vector search to identify semantically similar queries and reuse responses.

## High-Level Architecture

```
┌─────────────┐
│ Application │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│         DriftCache API              │
│  ┌─────────────────────────────┐   │
│  │   Semantic Cache Layer      │   │
│  │  - Embedding Generation     │   │
│  │  - Vector Similarity Search │   │
│  │  - Cache Hit/Miss Logic     │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  Autonomous Optimization    │   │
│  │  - Drift Detection          │   │
│  │  - Self-Repair Agents       │   │
│  │  - Performance Monitoring   │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
       │                    │
       ▼                    ▼
┌─────────────┐      ┌─────────────┐
│ PostgreSQL  │      │   Redis     │
│ (Metadata)  │      │  (Cache)    │
└─────────────┘      └─────────────┘
       │
       ▼
┌─────────────┐
│   Claude    │
│   (LLM)     │
└─────────────┘
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

### 3. Autonomous Optimization (LangGraph Agents)
- **Drift Detection Agent**: Monitors cache quality degradation
- **Optimization Agent**: Automatically adjusts similarity thresholds
- **Repair Agent**: Self-heals cache inconsistencies

### 4. Data Persistence
- **PostgreSQL**: Stores metadata, analytics, and configuration
- **Redis**: Fast in-memory cache for responses and embeddings

### 5. API Layer (FastAPI)
- **REST Endpoints**: HTTP API for applications
- **WebSocket**: Real-time updates and monitoring
- **Authentication**: API key management

### 6. Frontend Dashboard (React)
- **Analytics View**: Cache hit rates, cost savings
- **Configuration**: Threshold adjustments, model selection
- **Monitoring**: Real-time system health

## Request Flow

### Cache Hit Path
1. Application sends prompt to DriftCache API
2. Generate embedding for prompt
3. Search vector store for similar embeddings (above threshold)
4. If match found → return cached response
5. Log cache hit, update metrics

### Cache Miss Path
1. Application sends prompt to DriftCache API
2. Generate embedding for prompt
3. Search vector store → no match found
4. Forward request to Claude
5. Store response + embedding in cache
6. Return response to application
7. Log cache miss, update metrics

## Technology Decisions

### Why FastAPI?
- Async support for high concurrency
- Automatic API documentation
- Type safety with Pydantic
- High performance

### Why PostgreSQL + Redis?
- **PostgreSQL**: Complex queries, analytics, metadata
- **Redis**: Ultra-fast cache lookups, TTL support

### Why Sentence Transformers?
- Efficient embedding generation
- Pre-trained models available
- CPU/GPU support

### Why LangGraph?
- Agent orchestration
- State management for autonomous systems
- Built for LLM-powered workflows

## Scaling Considerations

### Horizontal Scaling
- Stateless API servers
- Shared Redis cluster
- Load balancer for API instances

### Vertical Scaling
- Increase Redis memory
- Larger PostgreSQL instance
- GPU for faster embeddings

### Future Enhancements
- Distributed vector index (Pinecone, Weaviate)
- Multi-tenant support
- Advanced caching strategies (hierarchical, context-aware)
