# Embedding Pipeline

## Overview

The Embedding Pipeline is what makes DriftCache **semantically aware**. It converts prompts into numerical vectors that represent their meaning, enabling similarity-based caching.

## The Core Problem

**Traditional caching** (exact match):
```
"What is caching?" ≠ "Explain the concept of caching"
```
❌ **No match** - Must call LLM again

**Semantic caching** (meaning match):
```
"What is caching?" ≈ "Explain the concept of caching"
Similarity: 0.89 (89%)
```
✅ **Cache HIT** - Return cached response

## How It Works

### The Pipeline

```
User Prompt
    ↓
Text Cleaning & Normalization
    ↓
Embedding Model (all-MiniLM-L6-v2)
    ↓
384-dimensional Vector
    ↓
L2 Normalization
    ↓
Metadata Attachment
    ↓
[0.13, -0.44, 0.82, ...]
```

### Example

**Input:**
```
"Explain Redis simply"
```

**After Normalization:**
```
"explain redis simply"
```

**After Embedding:**
```python
[
  0.1342, -0.4421, 0.8201, 0.0734, -0.2156, ...
  # 384 numbers total
]
```

**With Metadata:**
```python
{
  "vector": [0.1342, -0.4421, ...],
  "dimension": 384,
  "text": "Explain Redis simply",
  "metadata": {
    "prompt_hash": "abc123...",
    "model_name": "all-MiniLM-L6-v2",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

## Model Choice: all-MiniLM-L6-v2

We use **all-MiniLM-L6-v2** because it's:

| Property | Value | Why It Matters |
|----------|-------|----------------|
| **Size** | 80MB | Downloads in seconds |
| **Speed** | <50ms | Fast enough for real-time |
| **Dimension** | 384 | Good balance (not too high/low) |
| **Quality** | Strong | Handles semantic similarity well |
| **Cost** | FREE | Runs locally, no API calls |

Compare to alternatives:

- **OpenAI text-embedding-3-small**: $$$ (costs per request)
- **all-mpnet-base-v2**: Larger (420MB), slower
- **all-MiniLM-L12-v2**: Slightly better, but 2x slower

## Architecture

### Components

```
embeddings/
├── model.py          # Embedding model loader
├── service.py        # Main embedding service
├── utils.py          # Text processing utilities
└── __init__.py

models/
└── embedding_schemas.py  # Pydantic schemas
```

### 1. EmbeddingModel (`model.py`)

Manages the sentence-transformers model:

```python
from app.embeddings.model import get_embedding_model

model = get_embedding_model()
model.load()  # Lazy loading

# Generate embedding
vector = model.encode_single("What is Redis?")
# → numpy array [384 dimensions]

# Batch encoding (more efficient)
vectors = model.encode(["Text 1", "Text 2", "Text 3"])
# → numpy array [3, 384]

# Compute similarity
similarity = model.similarity(vec1, vec2)
# → 0.89
```

### 2. EmbeddingService (`service.py`)

High-level interface for embedding generation:

```python
from app.embeddings.service import get_embedding_service

service = get_embedding_service()

# Embed text
embedding = service.embed_text(
    text="Explain Redis simply",
    model_name="gpt-4",
    user_id="user123"
)

# Embed from chat messages
from app.models.schemas import Message

messages = [
    Message(role="user", content="What is Redis?")
]
embedding = service.embed_messages(messages)

# Batch embedding
texts = ["Text 1", "Text 2", "Text 3"]
batch = service.embed_batch(texts)

# Similarity search
results = service.find_most_similar(
    query_embedding=query_emb,
    candidate_embeddings=[emb1, emb2, emb3],
    top_k=3,
    threshold=0.85
)
```

### 3. Utilities (`utils.py`)

Helper functions for text processing:

```python
from app.embeddings.utils import (
    normalize_text,
    create_prompt_hash,
    extract_prompt_from_messages,
    truncate_for_embedding,
    cosine_similarity,
)

# Normalize text
text = "  What is REDIS?  "
normalized = normalize_text(text)
# → "what is redis?"

# Create hash
hash_val = create_prompt_hash(text)
# → "abc123..." (SHA256)

# Extract from messages
messages = [...]
prompt = extract_prompt_from_messages(messages)

# Compute similarity
sim = cosine_similarity(vec1, vec2)
# → 0.89
```

## Usage Examples

### Example 1: Basic Embedding

```python
from app.embeddings.service import get_embedding_service

service = get_embedding_service()

# Generate embedding
embedding = service.embed_text("What is semantic caching?")

print(f"Dimension: {embedding.dimension}")
print(f"Vector (first 5): {embedding.vector[:5]}")
print(f"Hash: {embedding.metadata.prompt_hash[:8]}...")
```

Output:
```
Dimension: 384
Vector (first 5): [0.13, -0.44, 0.82, 0.07, -0.22]
Hash: abc12345...
```

### Example 2: Similarity Search

```python
service = get_embedding_service()

# Create query
query = service.embed_text("What is caching?")

# Create candidates
candidates = [
    service.embed_text("Explain the concept of caching"),
    service.embed_text("How does Redis work?"),
    service.embed_text("Recipe for chocolate cake"),
]

# Find similar
results = service.find_most_similar(
    query_embedding=query,
    candidate_embeddings=candidates,
    top_k=2,
    threshold=0.7
)

for embedding, similarity in results:
    print(f"{similarity:.2f}: {embedding.text}")
```

Output:
```
0.89: Explain the concept of caching
0.72: How does Redis work?
```

### Example 3: Integration with Chat Endpoint

```python
from app.embeddings.service import get_embedding_service
from app.models.schemas import Message

# In your chat endpoint
messages = request.messages
service = get_embedding_service()

# Generate embedding for cache lookup
embedding = service.embed_messages(
    messages=messages,
    model_name=request.model,
    user_id=request.user
)

# Use embedding.metadata.prompt_hash as cache key
# Use embedding.vector for similarity search
```

## Text Processing Pipeline

### Step 1: Cleaning

```python
"  What is\x00 REDIS?\n\n  "
↓
"What is REDIS?"  # Remove control chars, trim
```

### Step 2: Normalization

```python
"What is REDIS?"
↓
"what is redis?"  # Lowercase, normalize whitespace
```

### Step 3: Truncation

```python
"word " * 1000  # Very long text
↓
"word word word ... word..."  # Max 256 tokens
```

### Step 4: Embedding

```python
"what is redis?"
↓
[0.13, -0.44, 0.82, ...]  # 384 dimensions
```

### Step 5: Normalization (Vector)

```python
[0.13, -0.44, 0.82, ...]
↓
[0.131, -0.444, 0.828, ...]  # L2 norm = 1.0
```

## Similarity Computation

### Cosine Similarity

After L2 normalization, cosine similarity = dot product:

```python
vec1 = [0.13, -0.44, 0.82, ...]  # Normalized
vec2 = [0.15, -0.42, 0.80, ...]  # Normalized

similarity = dot(vec1, vec2)
# → 0.94 (94% similar)
```

### Interpretation

| Similarity | Meaning |
|------------|---------|
| 0.95 - 1.00 | Nearly identical |
| 0.85 - 0.95 | Very similar (cache hit) |
| 0.70 - 0.85 | Somewhat similar |
| 0.50 - 0.70 | Loosely related |
| 0.00 - 0.50 | Different topics |

## Performance

### Embedding Generation

```
Single text:    20-50ms
Batch (10):     50-100ms
Batch (100):    300-500ms
```

### Memory Usage

```
Model size:     80MB
Per embedding:  1.5KB (384 floats × 4 bytes)
1000 embeddings: 1.5MB
1M embeddings:  1.5GB
```

### Optimization Tips

1. **Batch when possible**
   ```python
   # Good (1 call)
   embeddings = service.embed_batch([text1, text2, text3])

   # Bad (3 calls)
   emb1 = service.embed_text(text1)
   emb2 = service.embed_text(text2)
   emb3 = service.embed_text(text3)
   ```

2. **Reuse model instance**
   ```python
   # Good (singleton)
   service = get_embedding_service()

   # Bad (creates new model each time)
   EmbeddingService()
   ```

3. **Cache embeddings**
   ```python
   # Don't re-embed the same text
   # Store embeddings in database/cache
   ```

## Testing

Run embedding tests:

```bash
cd backend

# Fast tests (no model download)
pytest tests/test_embeddings.py -v -m "not slow"

# Full tests (includes model loading)
pytest tests/test_embeddings.py -v
```

Example test:

```python
def test_semantic_similarity():
    service = get_embedding_service()

    # Similar texts
    emb1 = service.embed_text("What is caching?")
    emb2 = service.embed_text("Explain caching")

    similarity = service.compute_similarity(emb1, emb2)

    assert similarity > 0.7  # Should be similar
```

## Integration with Cache Layer

```python
# Week 2: This is how embeddings connect to caching

async def check_cache(messages: List[Message]) -> Optional[CachedResponse]:
    # Generate embedding
    embedding = service.embed_messages(messages)

    # Search for similar cached responses
    similar = await vector_store.search(
        vector=embedding.vector,
        threshold=0.85,
        top_k=1
    )

    if similar:
        return similar[0].response
    return None
```

## Common Issues

### Issue 1: Model Download

**Problem:** First run downloads 80MB model

**Solution:**
```python
# Pre-download in Docker build
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Issue 2: Slow Embedding

**Problem:** Embedding takes too long

**Solution:**
- Use batch encoding
- Enable GPU if available
- Consider model quantization

### Issue 3: High Memory

**Problem:** Model uses too much RAM

**Solution:**
- Load model lazily (we do this)
- Unload when not in use
- Use smaller model (all-MiniLM-L3-v2)

## Summary

The Embedding Pipeline transforms DriftCache from:

❌ **Exact match caching** (limited value)
```
"What is Redis?" only matches "What is Redis?"
```

✅ **Semantic caching** (high value)
```
"What is Redis?" matches:
- "Explain Redis simply"
- "Tell me about Redis"
- "Redis explanation needed"
```

### Key Benefits

1. **Intelligent Caching**: Matches meaning, not just text
2. **Higher Hit Rates**: More cache hits = lower costs
3. **Local & Free**: No API costs for embeddings
4. **Fast**: <50ms embedding generation
5. **Production-Ready**: Comprehensive error handling

This is the foundation for Week 2's semantic cache layer.
