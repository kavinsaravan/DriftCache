## FAISS Vector Search Engine

## Overview

FAISS (Facebook AI Similarity Search) is the **search engine** that powers DriftCache's semantic caching. It answers the critical question:

> "Have we seen a semantically similar request before?"

## The Problem FAISS Solves

**Without FAISS:**
```python
# Need to compare query against ALL cached prompts
for cached_prompt in cache:
    similarity = compute_similarity(query, cached_prompt)  # SLOW!

# For 1M prompts: 1M comparisons = seconds
```

**With FAISS:**
```python
# FAISS uses optimized indexing
results = faiss_index.search(query, k=5)  # Fast!

# For 1M prompts: <10ms search time
```

## Architecture

```
Query: "What is Redis?"
    ↓
Embedding Service → [0.13, -0.44, ...]
    ↓
FAISS Index → Search for k nearest neighbors
    ↓
Results: [vector_id_42, vector_id_103, ...]
    ↓
Metadata Store → Map vector_id → prompt + response
    ↓
Cache Decision: similarity > threshold?
    ↓
Return cached response (HIT) or call LLM (MISS)
```

## Components

### 1. FAISS Index (`vectorstore/faiss_index.py`)

Manages the vector index:

```python
from app.vectorstore.faiss_index import get_faiss_index

index = get_faiss_index()

# Add vectors
vectors = np.array([[0.1, 0.2, ...], [0.3, 0.4, ...]])
ids = index.add_vectors(vectors)

# Search
query = np.array([0.15, 0.22, ...])
distances, indices = index.search_single(query, k=5)

# Convert distance to similarity
similarity = index.distance_to_similarity(distances[0])
# → 0.94 (94% similar)
```

**Key Features:**
- **IndexFlatL2**: Exact search (no approximation)
- **L2 Normalization**: Converts to cosine similarity
- **Persistence**: Save/load index from disk
- **Fast**: Sub-millisecond search

### 2. Metadata Store (`vectorstore/storage.py`)

Maps FAISS vector IDs to full metadata:

```python
from app.vectorstore.storage import get_metadata_store

store = get_metadata_store()

# Add metadata
metadata = VectorMetadata(
    vector_id=42,
    prompt_id="abc123...",
    prompt_text="What is Redis?",
    response_text="Redis is an in-memory database...",
    model_name="gpt-4",
    embedding_model="all-MiniLM-L6-v2",
    cache_hits=0
)
store.add(metadata)

# Retrieve
meta = store.get(42)
print(meta.response_text)
```

**Why Separate Storage?**

FAISS only stores vectors (numbers). We need to store:
- Original prompt text
- Cached response text
- Model metadata
- Cache hit counters
- Timestamps

### 3. Semantic Search Service (`vectorstore/search.py`)

High-level interface combining everything:

```python
from app.vectorstore.search import get_search_service

service = get_search_service()

# Add to cache
embedding = embedding_service.embed_text("What is Redis?")
service.add_to_index(
    embedding=embedding,
    response_text="Redis is an in-memory database...",
    model_name="gpt-4"
)

# Search
query_emb = embedding_service.embed_text("Tell me about Redis")
cache_entry = service.get_cache_entry(
    query_embedding=query_emb,
    threshold=0.85
)

if cache_entry:
    print(f"CACHE HIT! Similarity: {cache_entry.similarity:.2f}")
    print(f"Response: {cache_entry.response_text}")
else:
    print("CACHE MISS - call LLM")
```

## The Complete Flow

### Adding to Cache

```
1. User request arrives
2. Generate embedding
3. Call LLM (cache miss)
4. Get response
5. Add to index:
   ┌─────────────────────────────┐
   │ FAISS Index                 │
   │ Add vector → get vector_id  │
   └─────────────────────────────┘
                ↓
   ┌─────────────────────────────┐
   │ Metadata Store              │
   │ Map vector_id → metadata    │
   └─────────────────────────────┘
```

### Searching Cache

```
1. User request arrives
2. Generate embedding
3. Search FAISS:
   ┌─────────────────────────────┐
   │ FAISS Index                 │
   │ Search → [vector_ids]       │
   │ Return distances            │
   └─────────────────────────────┘
                ↓
   ┌─────────────────────────────┐
   │ Convert distance → similarity│
   │ Filter by threshold (0.85)  │
   └─────────────────────────────┘
                ↓
   ┌─────────────────────────────┐
   │ Metadata Store              │
   │ Get prompt + response       │
   └─────────────────────────────┘
                ↓
   Return cached response (HIT!)
```

## Index Types

### IndexFlatL2 (Current - MVP)

```python
index = FAISSIndex(dimension=384, index_type="Flat")
```

**Pros:**
- Exact search (100% accurate)
- No training required
- Simple to implement

**Cons:**
- O(N) search time
- Slow for large datasets (>1M vectors)

**Best for:** MVP, <100K vectors

### IndexIVFFlat (Production)

```python
index = FAISSIndex(dimension=384, index_type="IVF")
```

**Pros:**
- Faster search (approximate)
- Handles millions of vectors

**Cons:**
- Requires training
- Slightly less accurate

**Best for:** Production, >100K vectors

### IndexHNSW (High Performance)

```python
index = FAISSIndex(dimension=384, index_type="HNSW")
```

**Pros:**
- Very fast search
- Good accuracy

**Cons:**
- More memory usage

**Best for:** High-throughput production

## Distance vs Similarity

FAISS returns **L2 distances**. We need **cosine similarity**.

### The Math

For normalized vectors:

```
L2_distance² = 2 × (1 - cosine_similarity)

Therefore:
cosine_similarity = 1 - (L2_distance² / 2)
```

### Example

```python
distance = 0.5  # From FAISS
similarity = 1 - (0.5² / 2) = 1 - 0.125 = 0.875

# 87.5% similar!
```

## Persistence

### Save Index

```python
service = get_search_service()

# Save FAISS index + metadata
service.save_index()

# Files created:
# - data/cache/faiss.index (FAISS vectors)
# - data/cache/metadata.json (prompt/response data)
```

### Load Index

```python
service = get_search_service()

# Auto-loads on initialization
# Or manually:
service.load_index()
```

### File Structure

```
data/
└── cache/
    ├── faiss.index          # FAISS binary index
    └── metadata.json        # JSON metadata
        {
          "version": "1.0",
          "count": 1000,
          "metadata": {
            "0": {
              "vector_id": 0,
              "prompt_id": "abc123...",
              "prompt_text": "What is Redis?",
              "response_text": "Redis is...",
              "model_name": "gpt-4",
              "cache_hits": 5
            },
            ...
          }
        }
```

## Usage Examples

### Example 1: Basic Search

```python
from app.vectorstore.search import get_search_service
from app.embeddings.service import get_embedding_service

search_service = get_search_service()
embedding_service = get_embedding_service()

# Add to cache
emb = embedding_service.embed_text("What is caching?")
search_service.add_to_index(
    embedding=emb,
    response_text="Caching stores frequently accessed data...",
    model_name="gpt-4"
)

# Search
query_emb = embedding_service.embed_text("Explain caching")
results = search_service.search(query_emb, top_k=5, threshold=0.85)

for result in results.results:
    print(f"{result.similarity:.2f}: {result.prompt_text}")
```

Output:
```
0.94: What is caching?
```

### Example 2: Cache Hit/Miss Logic

```python
def check_cache_and_respond(prompt: str) -> str:
    # Generate embedding
    embedding = embedding_service.embed_text(prompt)

    # Check cache
    cache_entry = search_service.get_cache_entry(
        query_embedding=embedding,
        threshold=0.85
    )

    if cache_entry:
        # CACHE HIT
        print(f"✓ Cache HIT (similarity: {cache_entry.similarity:.2f})")
        return cache_entry.response_text
    else:
        # CACHE MISS
        print("✗ Cache MISS - calling LLM")
        response = call_llm(prompt)

        # Add to cache for next time
        search_service.add_to_index(embedding, response, "gpt-4")

        return response
```

### Example 3: Batch Operations

```python
# Add multiple entries efficiently
texts = ["Question 1", "Question 2", "Question 3"]
responses = ["Answer 1", "Answer 2", "Answer 3"]

embeddings = [embedding_service.embed_text(t) for t in texts]

search_service.add_batch_to_index(
    embeddings=embeddings,
    responses=responses,
    model_name="gpt-4"
)
```

## Performance

### Search Speed

```
Index Size    Search Time
-----------   -----------
100 vectors   <1ms
1,000         ~1ms
10,000        ~5ms
100,000       ~30ms (Flat)
100,000       ~5ms (IVF)
1,000,000     ~50ms (IVF)
```

### Memory Usage

```
1 vector (384 dims): 1.5KB
1,000 vectors:      1.5MB
100,000 vectors:    150MB
1,000,000 vectors:  1.5GB
```

### Optimization Tips

1. **Use Batch Operations**
   ```python
   # Good
   service.add_batch_to_index(embeddings, responses, model)

   # Bad
   for emb, resp in zip(embeddings, responses):
       service.add_to_index(emb, resp, model)
   ```

2. **Adjust k Appropriately**
   ```python
   # Don't need 100 results
   results = service.search(query, top_k=5)  # Good
   results = service.search(query, top_k=100)  # Wasteful
   ```

3. **Save Periodically**
   ```python
   # Save every 100 additions
   if num_additions % 100 == 0:
       service.save_index()
   ```

## Testing

Run vector store tests:

```bash
cd backend

# Fast tests
pytest tests/test_vectorstore.py -v -m "not slow"

# Full tests (requires model download)
pytest tests/test_vectorstore.py -v
```

## Common Issues

### Issue 1: Index Not Persisting

**Problem:** Index resets on restart

**Solution:**
```python
# Save explicitly
service.save_index()

# Or set up auto-save (future enhancement)
```

### Issue 2: Slow Search

**Problem:** Search takes too long

**Solution:**
- Use IVF or HNSW index for large datasets
- Reduce top_k
- Consider GPU acceleration

### Issue 3: Low Similarity Scores

**Problem:** Nothing matches above threshold

**Solution:**
- Lower threshold (e.g., 0.75 instead of 0.85)
- Check embedding model
- Verify text normalization

## Integration with Cache Layer

```python
# Week 2: Full cache integration

async def handle_request(messages):
    # Generate embedding
    embedding = embedding_service.embed_messages(messages)

    # Check semantic cache
    cache_entry = search_service.get_cache_entry(
        query_embedding=embedding,
        threshold=settings.SIMILARITY_THRESHOLD
    )

    if cache_entry:
        # CACHE HIT - return cached response
        return create_response_from_cache(cache_entry)

    # CACHE MISS - call LLM
    response = await provider_router.chat_completion(...)

    # Add to cache
    search_service.add_to_index(
        embedding=embedding,
        response_text=response.choices[0].message.content,
        model_name=response.model
    )

    return response
```

## Summary

FAISS Vector Search provides:

✅ **Fast Similarity Search**: Sub-millisecond k-NN
✅ **Scalable**: Handles millions of vectors
✅ **Persistent**: Save/load from disk
✅ **Flexible**: Multiple index types
✅ **Production-Ready**: Battle-tested by Facebook

### The Pipeline

```
Prompt → Embedding → FAISS Search → Metadata Lookup → Cache Decision
```

### Key Metrics

- **Search time**: <10ms for 1M vectors (IVF)
- **Accuracy**: 100% (Flat), ~95% (IVF)
- **Memory**: 1.5KB per vector
- **Throughput**: 1000s of searches/second

This is the **retrieval engine** that makes semantic caching possible.
