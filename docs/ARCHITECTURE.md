# DriftCache Architecture

## System Overview

DriftCache is a semantic caching layer that sits between applications and LLM providers, using embeddings and vector search to identify semantically similar queries and reuse responses.



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
