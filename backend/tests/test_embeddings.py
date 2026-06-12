"""
Test Embedding Pipeline

Tests for embedding generation, text processing, and similarity computation
"""
import pytest
import numpy as np
from app.embeddings.model import EmbeddingModel, get_embedding_model
from app.embeddings.service import EmbeddingService, get_embedding_service
from app.embeddings.utils import (
    extract_prompt_from_messages,
    normalize_text,
    create_prompt_hash,
    normalize_vector,
    cosine_similarity,
    clean_text,
    truncate_for_embedding,
    vector_to_list,
    list_to_vector,
)
from app.models.schemas import Message


def test_normalize_text():
    """Test text normalization"""
    # Extra whitespace
    text1 = "  Hello    World  "
    assert normalize_text(text1) == "hello world"

    # Mixed case
    text2 = "ReDiS is FAST"
    assert normalize_text(text2) == "redis is fast"

    # Newlines and tabs
    text3 = "Line 1\n\tLine 2"
    assert normalize_text(text3) == "line 1 line 2"


def test_create_prompt_hash():
    """Test prompt hashing"""
    # Same text should produce same hash
    hash1 = create_prompt_hash("Hello World")
    hash2 = create_prompt_hash("Hello World")
    assert hash1 == hash2

    # Different text should produce different hash
    hash3 = create_prompt_hash("Goodbye World")
    assert hash1 != hash3

    # Case and whitespace shouldn't matter (due to normalization)
    hash4 = create_prompt_hash("  HELLO   WORLD  ")
    assert hash1 == hash4


def test_extract_prompt_from_messages():
    """Test prompt extraction from chat messages"""
    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="What is Redis?"),
        Message(role="assistant", content="Redis is..."),
        Message(role="user", content="Tell me more"),
    ]

    prompt = extract_prompt_from_messages(messages)

    # Should only include user messages
    assert "What is Redis?" in prompt
    assert "Tell me more" in prompt
    assert "helpful assistant" not in prompt
    assert "Redis is..." not in prompt


def test_clean_text():
    """Test text cleaning"""
    # Control characters
    text1 = "Hello\x00World\x1f"
    assert clean_text(text1) == "HelloWorld"

    # Extra whitespace
    text2 = "  Too   many   spaces  "
    assert clean_text(text2) == "Too many spaces"

    # Length limiting
    text3 = "A" * 1000
    assert len(clean_text(text3, max_length=100)) == 100


def test_truncate_for_embedding():
    """Test text truncation"""
    # Short text shouldn't be truncated
    short = "Hello"
    assert truncate_for_embedding(short) == short

    # Long text should be truncated
    long = "word " * 1000  # Very long text
    truncated = truncate_for_embedding(long, max_tokens=256)
    assert len(truncated) < len(long)
    assert "..." in truncated


def test_vector_normalization():
    """Test vector normalization"""
    # Unnormalized vector
    vec = np.array([3.0, 4.0])

    # Normalize
    normalized = normalize_vector(vec)

    # Check L2 norm is 1
    assert np.abs(np.linalg.norm(normalized) - 1.0) < 1e-6

    # Check direction preserved
    assert normalized[0] / normalized[1] == pytest.approx(vec[0] / vec[1])


def test_cosine_similarity():
    """Test cosine similarity computation"""
    # Identical vectors
    vec1 = np.array([1.0, 0.0])
    similarity1 = cosine_similarity(vec1, vec1)
    assert similarity1 == pytest.approx(1.0)

    # Orthogonal vectors
    vec2 = np.array([1.0, 0.0])
    vec3 = np.array([0.0, 1.0])
    similarity2 = cosine_similarity(vec2, vec3)
    assert similarity2 == pytest.approx(0.0, abs=1e-6)

    # Similar vectors
    vec4 = normalize_vector(np.array([1.0, 0.1]))
    vec5 = normalize_vector(np.array([1.0, 0.2]))
    similarity3 = cosine_similarity(vec4, vec5)
    assert 0.9 < similarity3 < 1.0


def test_vector_conversion():
    """Test conversion between numpy and list"""
    # List to vector
    lst = [1.0, 2.0, 3.0]
    vec = list_to_vector(lst)
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (3,)

    # Vector to list
    back_to_list = vector_to_list(vec)
    assert isinstance(back_to_list, list)
    assert back_to_list == lst


@pytest.mark.slow
def test_embedding_model_loading():
    """Test embedding model loading"""
    model = EmbeddingModel(model_name="all-MiniLM-L6-v2")

    assert not model.is_loaded()

    # Load model
    model.load()

    assert model.is_loaded()
    assert model.dimension == 384  # all-MiniLM-L6-v2 has 384 dimensions


@pytest.mark.slow
def test_embedding_generation():
    """Test single embedding generation"""
    model = get_embedding_model()
    model.load()

    text = "What is semantic caching?"

    # Generate embedding
    embedding = model.encode_single(text, normalize=True)

    # Check properties
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (model.dimension,)
    assert np.abs(np.linalg.norm(embedding) - 1.0) < 1e-6  # Normalized


@pytest.mark.slow
def test_batch_embedding():
    """Test batch embedding generation"""
    model = get_embedding_model()
    model.load()

    texts = [
        "What is Redis?",
        "Explain caching",
        "How does DriftCache work?"
    ]

    # Generate embeddings
    embeddings = model.encode(texts, normalize=True)

    # Check properties
    assert embeddings.shape == (3, model.dimension)

    # Check each is normalized
    for emb in embeddings:
        assert np.abs(np.linalg.norm(emb) - 1.0) < 1e-6


@pytest.mark.slow
def test_embedding_similarity():
    """Test that similar texts have high similarity"""
    model = get_embedding_model()
    model.load()

    # Similar texts
    text1 = "What is caching?"
    text2 = "Explain the concept of caching"

    # Different text
    text3 = "How to cook pasta?"

    emb1 = model.encode_single(text1)
    emb2 = model.encode_single(text2)
    emb3 = model.encode_single(text3)

    # Similar texts should have high similarity
    sim_12 = model.similarity(emb1, emb2)
    assert sim_12 > 0.6  # Threshold for "similar"

    # Different texts should have low similarity
    sim_13 = model.similarity(emb1, emb3)
    assert sim_13 < 0.5


@pytest.mark.slow
def test_embedding_service():
    """Test embedding service"""
    service = get_embedding_service()

    text = "Explain Redis simply"

    # Generate embedding
    embedding = service.embed_text(
        text=text,
        model_name="gpt-4",
        user_id="test_user"
    )

    # Check properties
    assert embedding.text == text
    assert embedding.dimension == 384
    assert len(embedding.vector) == 384
    assert embedding.metadata.model_name == "gpt-4"
    assert embedding.metadata.user_id == "test_user"
    assert len(embedding.metadata.prompt_hash) == 64  # SHA256


@pytest.mark.slow
def test_embedding_service_messages():
    """Test embedding from chat messages"""
    service = get_embedding_service()

    messages = [
        Message(role="system", content="You are helpful"),
        Message(role="user", content="What is Redis?"),
    ]

    embedding = service.embed_messages(messages, model_name="test-model")

    # Should extract user message
    assert "Redis" in embedding.text
    assert "helpful" not in embedding.text.lower()


@pytest.mark.slow
def test_embedding_service_batch():
    """Test batch embedding service"""
    service = get_embedding_service()

    texts = [
        "What is caching?",
        "Explain databases",
        "How does Redis work?"
    ]

    batch = service.embed_batch(texts, model_name="test-model")

    assert len(batch) == 3
    assert batch.total_count == 3
    assert batch.model_name == "test-model"

    for i, embedding in enumerate(batch.embeddings):
        assert texts[i] in embedding.text


@pytest.mark.slow
def test_similarity_search():
    """Test finding most similar embeddings"""
    service = get_embedding_service()

    # Create query and candidates
    query_text = "What is caching?"

    candidate_texts = [
        "Explain the concept of caching",  # Very similar
        "How does Redis work?",  # Somewhat similar
        "Recipe for chocolate cake",  # Not similar
    ]

    query_emb = service.embed_text(query_text)
    candidate_embs = [
        service.embed_text(text) for text in candidate_texts
    ]

    # Find most similar
    results = service.find_most_similar(
        query_embedding=query_emb,
        candidate_embeddings=candidate_embs,
        top_k=2
    )

    # Should return 2 results
    assert len(results) == 2

    # First result should be most similar (caching-related)
    best_match, best_score = results[0]
    assert "caching" in best_match.text.lower()
    assert best_score > 0.6

    # Chocolate cake should not be in top 2
    assert not any("cake" in emb.text for emb, score in results)


if __name__ == "__main__":
    print("Running embedding tests...")
    print("Note: Tests marked with @pytest.mark.slow require model download")
    pytest.main([__file__, "-v", "-m", "not slow"])
