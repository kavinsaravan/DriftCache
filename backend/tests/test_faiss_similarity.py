"""
Unit tests for FAISS similarity conversion

Tests the critical bug fix: FAISS IndexFlatL2 returns SQUARED L2 distance,
not L2 distance. The conversion formula is:
    cosine_similarity = 1 - (squared_L2_distance / 2)
"""
import pytest
import numpy as np
from app.vectorstore.faiss_index import FAISSIndex


def test_distance_to_similarity_exact_match():
    """Test that distance 0.0 (identical vectors) gives similarity 1.0"""
    distance = 0.0
    similarity = FAISSIndex.distance_to_similarity(distance)

    assert similarity == 1.0, f"Expected 1.0 for distance=0, got {similarity}"


def test_distance_to_similarity_orthogonal():
    """Test that distance 2.0 (orthogonal normalized vectors) gives similarity 0.0"""
    # For normalized vectors, max L2² distance is 2
    distance = 2.0
    similarity = FAISSIndex.distance_to_similarity(distance)

    assert similarity == 0.0, f"Expected 0.0 for distance=2.0, got {similarity}"


def test_distance_to_similarity_midpoint():
    """Test that distance 1.0 gives similarity 0.5"""
    distance = 1.0
    similarity = FAISSIndex.distance_to_similarity(distance)

    expected = 0.5
    assert abs(similarity - expected) < 0.001, \
        f"Expected {expected} for distance=1.0, got {similarity}"


def test_distance_to_similarity_clamping():
    """Test that negative distances are clamped to 0"""
    distance = -0.5
    similarity = FAISSIndex.distance_to_similarity(distance)

    assert similarity == 1.0, f"Negative distance should clamp to similarity=1.0, got {similarity}"


def test_distance_to_similarity_range():
    """Test various distances in valid range"""
    test_cases = [
        (0.0, 1.0),      # Exact match
        (0.5, 0.75),     # High similarity
        (1.0, 0.5),      # Medium similarity
        (1.5, 0.25),     # Low similarity
        (2.0, 0.0),      # Orthogonal
    ]

    for distance, expected in test_cases:
        similarity = FAISSIndex.distance_to_similarity(distance)
        assert abs(similarity - expected) < 0.001, \
            f"For distance={distance}, expected {expected}, got {similarity}"


def test_faiss_search_with_real_vectors():
    """Integration test: verify FAISS search returns correct similarities"""
    # Create index
    dimension = 384
    index = FAISSIndex(dimension=dimension)

    # Create normalized test vectors
    vec1 = np.random.randn(dimension).astype('float32')
    vec1 = vec1 / np.linalg.norm(vec1)  # Normalize

    vec2 = np.random.randn(dimension).astype('float32')
    vec2 = vec2 / np.linalg.norm(vec2)  # Normalize

    # Add vectors to index
    index.add_vectors(np.array([vec1, vec2]))

    # Search for vec1 (should find itself with similarity=1.0)
    results = index.search(np.array([vec1]), k=1)

    assert len(results) == 1, "Should return 1 result"
    assert results[0]['index'] == 0, "Should find itself at index 0"
    assert results[0]['similarity'] > 0.99, \
        f"Self-similarity should be ~1.0, got {results[0]['similarity']}"


def test_cosine_similarity_matches_numpy():
    """Verify our conversion matches direct cosine similarity calculation"""
    # Create two normalized random vectors
    dimension = 384
    vec1 = np.random.randn(dimension).astype('float32')
    vec1 = vec1 / np.linalg.norm(vec1)

    vec2 = np.random.randn(dimension).astype('float32')
    vec2 = vec2 / np.linalg.norm(vec2)

    # Calculate cosine similarity directly
    cosine_sim = np.dot(vec1, vec2)

    # Calculate L2² distance
    l2_squared = np.sum((vec1 - vec2) ** 2)

    # Convert using our formula
    converted_sim = FAISSIndex.distance_to_similarity(l2_squared)

    # They should match
    assert abs(converted_sim - cosine_sim) < 0.001, \
        f"Converted similarity {converted_sim} doesn't match cosine {cosine_sim}"


# Run with: pytest backend/tests/test_faiss_similarity.py -v
