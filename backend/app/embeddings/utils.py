"""
Embedding Utilities

Helper functions for text processing, normalization, and embedding operations
"""
import re
import hashlib
from typing import List, Optional
import numpy as np

from app.models.schemas import Message


def extract_prompt_from_messages(messages: List[Message]) -> str:
    """
    Extract the meaningful user prompt from chat messages

    Focuses on user messages, excludes system prompts

    Args:
        messages: List of chat messages

    Returns:
        Combined user prompt as a single string
    """
    user_messages = []

    for msg in messages:
        if msg.role == "user":
            user_messages.append(msg.content)

    # Combine all user messages
    combined = " ".join(user_messages)
    return combined


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent embedding

    Steps:
    1. Convert to lowercase
    2. Remove extra whitespace
    3. Strip leading/trailing whitespace
    4. Remove special characters (optional, can be tuned)

    Args:
        text: Raw text

    Returns:
        Normalized text
    """
    # Convert to lowercase
    text = text.lower()

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def create_prompt_hash(text: str) -> str:
    """
    Create a deterministic hash of text for cache keys

    Args:
        text: Text to hash

    Returns:
        SHA256 hash as hex string
    """
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    """
    L2-normalize a vector for cosine similarity

    After normalization: ||vector|| = 1
    Cosine similarity becomes simple dot product

    Args:
        vector: Unnormalized vector

    Returns:
        Normalized vector
    """
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors

    Assumes vectors are already normalized

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Similarity score [0, 1]
    """
    # For normalized vectors, cosine similarity = dot product
    similarity = float(np.dot(vec1, vec2))

    # Clamp to [0, 1] to handle floating point errors
    return max(0.0, min(1.0, similarity))


def batch_cosine_similarity(
    query_vector: np.ndarray,
    candidate_vectors: np.ndarray
) -> np.ndarray:
    """
    Compute cosine similarity between one query and multiple candidates

    Args:
        query_vector: Query vector [dimension]
        candidate_vectors: Candidate vectors [n_candidates, dimension]

    Returns:
        Similarity scores [n_candidates]
    """
    # Matrix multiplication for efficiency
    similarities = np.dot(candidate_vectors, query_vector)

    # Clamp to [0, 1]
    similarities = np.clip(similarities, 0.0, 1.0)

    return similarities


def clean_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Clean text by removing unwanted characters and limiting length

    Args:
        text: Raw text
        max_length: Maximum length (characters)

    Returns:
        Cleaned text
    """
    # Remove null bytes and other control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Strip
    text = text.strip()

    # Limit length if specified
    if max_length and len(text) > max_length:
        text = text[:max_length]

    return text


def truncate_for_embedding(
    text: str,
    max_tokens: int = 256,
    chars_per_token: int = 4
) -> str:
    """
    Truncate text to fit within embedding model limits

    Most sentence-transformers models have a token limit (e.g., 256-512 tokens)

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens allowed
        chars_per_token: Rough estimate of characters per token

    Returns:
        Truncated text
    """
    max_chars = max_tokens * chars_per_token

    if len(text) <= max_chars:
        return text

    # Truncate and add indicator
    return text[:max_chars] + "..."


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """
    Extract keywords from text (simple approach)

    This is useful for metadata and additional filtering

    Args:
        text: Text to extract keywords from
        top_n: Number of keywords to extract

    Returns:
        List of keywords
    """
    # Simple approach: split into words, remove stopwords, count frequency
    # This is a naive implementation - could be improved with NLP libraries

    # Common stopwords
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'be', 'been',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we',
        'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how'
    }

    # Normalize and split
    words = normalize_text(text).split()

    # Filter stopwords and short words
    keywords = [
        word for word in words
        if word not in stopwords and len(word) > 2
    ]

    # Count frequency
    from collections import Counter
    word_counts = Counter(keywords)

    # Get top N
    top_keywords = [word for word, count in word_counts.most_common(top_n)]

    return top_keywords


def vector_to_list(vector: np.ndarray) -> List[float]:
    """
    Convert numpy array to list of floats

    Useful for JSON serialization

    Args:
        vector: Numpy array

    Returns:
        List of floats
    """
    return vector.tolist()


def list_to_vector(lst: List[float]) -> np.ndarray:
    """
    Convert list of floats to numpy array

    Args:
        lst: List of floats

    Returns:
        Numpy array
    """
    return np.array(lst, dtype=np.float32)


def estimate_embedding_size(dimension: int) -> str:
    """
    Estimate memory size of an embedding

    Args:
        dimension: Vector dimension

    Returns:
        Human-readable size string
    """
    # Each float is 4 bytes (float32)
    bytes_per_embedding = dimension * 4

    if bytes_per_embedding < 1024:
        return f"{bytes_per_embedding} bytes"
    elif bytes_per_embedding < 1024 * 1024:
        return f"{bytes_per_embedding / 1024:.1f} KB"
    else:
        return f"{bytes_per_embedding / (1024 * 1024):.1f} MB"
