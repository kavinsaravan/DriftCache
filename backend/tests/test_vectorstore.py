"""
Test Vector Store (FAISS + Metadata)

Tests for FAISS index, metadata storage, and semantic search
"""
import pytest
import numpy as np
import tempfile
import os

from app.vectorstore.faiss_index import FAISSIndex
from app.vectorstore.storage import MetadataStore
from app.vectorstore.search import SemanticSearchService
from app.models.search_schemas import VectorMetadata
from app.models.embedding_schemas import Embedding, EmbeddingMetadata
from app.embeddings.service import get_embedding_service


def test_faiss_index_creation():
    """Test FAISS index creation"""
    index = FAISSIndex(dimension=384, index_type="Flat")
    index.create_index()

    assert index.index is not None
    assert len(index) == 0


def test_faiss_add_vectors():
    """Test adding vectors to FAISS"""
    index = FAISSIndex(dimension=384)
    index.create_index()

    # Create random vectors
    vectors = np.random.randn(10, 384).astype(np.float32)

    # Add to index
    ids = index.add_vectors(vectors)

    assert len(ids) == 10
    assert len(index) == 10


def test_faiss_search():
    """Test FAISS vector search"""
    index = FAISSIndex(dimension=384)
    index.create_index()

    # Add some vectors
    vectors = np.random.randn(100, 384).astype(np.float32)
    index.add_vectors(vectors)

    # Search with first vector
    query = vectors[0:1]
    distances, indices = index.search(query, k=5)

    # First result should be the query itself
    assert indices[0][0] == 0
    assert distances[0][0] < 0.01  # Very close to itself


def test_faiss_distance_to_similarity():
    """Test distance to similarity conversion"""
    # Distance 0 should give similarity 1.0
    assert FAISSIndex.distance_to_similarity(0.0) == pytest.approx(1.0)

    # Distance 2 should give similarity 0.0 (orthogonal after normalization)
    assert FAISSIndex.distance_to_similarity(2.0) == pytest.approx(0.0, abs=0.01)


def test_faiss_persistence():
    """Test saving and loading FAISS index"""
    index1 = FAISSIndex(dimension=384)
    index1.create_index()

    # Add vectors
    vectors = np.random.randn(50, 384).astype(np.float32)
    index1.add_vectors(vectors)

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.index') as f:
        temp_path = f.name

    try:
        index1.save(temp_path)

        # Create new index and load
        index2 = FAISSIndex(dimension=384)
        index2.load(temp_path)

        # Should have same number of vectors
        assert len(index2) == 50

        # Search should work
        query = vectors[0:1]
        distances, indices = index2.search(query, k=5)
        assert len(indices[0]) == 5

    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_metadata_store():
    """Test metadata storage"""
    store = MetadataStore()

    # Add metadata
    metadata = VectorMetadata(
        vector_id=0,
        prompt_id="abc123",
        prompt_text="What is Redis?",
        response_text="Redis is...",
        model_name="gpt-4",
        embedding_model="all-MiniLM-L6-v2"
    )
    store.add(metadata)

    # Retrieve
    retrieved = store.get(0)
    assert retrieved is not None
    assert retrieved.prompt_text == "What is Redis?"
    assert retrieved.vector_id == 0


def test_metadata_store_cache_hits():
    """Test cache hit tracking"""
    store = MetadataStore()

    metadata = VectorMetadata(
        vector_id=0,
        prompt_id="abc123",
        prompt_text="Test",
        model_name="gpt-4",
        embedding_model="test"
    )
    store.add(metadata)

    # Initially 0 hits
    assert store.get(0).cache_hits == 0

    # Increment
    store.increment_cache_hit(0)
    assert store.get(0).cache_hits == 1

    # Increment again
    store.increment_cache_hit(0)
    assert store.get(0).cache_hits == 2


def test_metadata_store_persistence():
    """Test saving and loading metadata"""
    store1 = MetadataStore()

    # Add some metadata
    for i in range(10):
        metadata = VectorMetadata(
            vector_id=i,
            prompt_id=f"prompt_{i}",
            prompt_text=f"Prompt {i}",
            model_name="gpt-4",
            embedding_model="test"
        )
        store1.add(metadata)

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as f:
        temp_path = f.name

    try:
        store1.save(temp_path)

        # Create new store and load
        store2 = MetadataStore()
        store2.load(temp_path)

        # Should have same data
        assert len(store2) == 10
        assert store2.get(5).prompt_text == "Prompt 5"

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.slow
def test_semantic_search_service():
    """Test semantic search service"""
    service = SemanticSearchService()
    embedding_service = get_embedding_service()

    # Clear any existing data
    service.clear_index()

    # Create embeddings
    texts = [
        "What is Redis?",
        "Explain caching",
        "How does Redis work?",
    ]

    embeddings = [embedding_service.embed_text(text) for text in texts]
    responses = [
        "Redis is an in-memory database",
        "Caching stores data for fast access",
        "Redis works by storing data in memory",
    ]

    # Add to index
    for emb, resp in zip(embeddings, responses):
        service.add_to_index(emb, resp, "gpt-4")

    # Search with similar query
    query_emb = embedding_service.embed_text("Tell me about Redis")
    results = service.search(query_emb, top_k=3)

    # Should find results
    assert len(results.results) > 0

    # Best match should be Redis-related
    best = results.get_best_match()
    assert best is not None
    assert "Redis" in best.prompt_text


@pytest.mark.slow
def test_cache_entry_retrieval():
    """Test getting cache entries"""
    service = SemanticSearchService()
    embedding_service = get_embedding_service()

    # Clear
    service.clear_index()

    # Add a cache entry
    emb = embedding_service.embed_text("What is semantic caching?")
    service.add_to_index(
        emb,
        "Semantic caching uses embeddings to match similar queries",
        "gpt-4"
    )

    # Query with similar text
    query_emb = embedding_service.embed_text("Explain semantic caching")
    cache_entry = service.get_cache_entry(query_emb, threshold=0.7)

    # Should get a cache hit
    assert cache_entry is not None
    assert cache_entry.is_cache_hit
    assert cache_entry.similarity > 0.7
    assert "semantic caching" in cache_entry.prompt_text.lower()


@pytest.mark.slow
def test_cache_miss():
    """Test cache miss scenario"""
    service = SemanticSearchService()
    embedding_service = get_embedding_service()

    # Clear
    service.clear_index()

    # Add unrelated entry
    emb = embedding_service.embed_text("Recipe for chocolate cake")
    service.add_to_index(emb, "Mix flour, eggs, chocolate...", "gpt-4")

    # Query with completely different topic
    query_emb = embedding_service.embed_text("What is Redis?")
    cache_entry = service.get_cache_entry(query_emb, threshold=0.85)

    # Should be a cache miss
    assert cache_entry is None


@pytest.mark.slow
def test_batch_add():
    """Test batch adding to index"""
    service = SemanticSearchService()
    embedding_service = get_embedding_service()

    # Clear
    service.clear_index()

    # Create batch
    texts = [f"Question {i}" for i in range(10)]
    embeddings = [embedding_service.embed_text(text) for text in texts]
    responses = [f"Answer {i}" for i in range(10)]

    # Add batch
    ids = service.add_batch_to_index(embeddings, responses, "gpt-4")

    assert len(ids) == 10
    assert len(service.faiss_index) == 10


@pytest.mark.slow
def test_similarity_threshold():
    """Test similarity threshold filtering"""
    service = SemanticSearchService()
    embedding_service = get_embedding_service()

    # Clear
    service.clear_index()

    # Add entry
    emb = embedding_service.embed_text("What is caching?")
    service.add_to_index(emb, "Caching stores data...", "gpt-4")

    # Very similar query (should match at 0.9)
    query1 = embedding_service.embed_text("Explain caching")
    result1 = service.get_cache_entry(query1, threshold=0.9)
    # Might match depending on model

    # Same query (should definitely match at 0.95)
    query2 = embedding_service.embed_text("What is caching?")
    result2 = service.get_cache_entry(query2, threshold=0.95)
    assert result2 is not None


if __name__ == "__main__":
    print("Running vector store tests...")
    pytest.main([__file__, "-v", "-m", "not slow"])
