"""
Pytest configuration for DriftCache tests
"""
import pytest

# Collect markers to mark tests that need special setup
def pytest_collection_modifyitems(items):
    """Mark tests that require external services"""
    for item in items:
        # Mark all async tests that use CacheService as needing setup
        if "semantic_caching" in item.nodeid:
            # Let semantic caching tests run - they're the ones we want to test
            pass
        elif any(x in item.nodeid for x in ["embedding", "vectorstore", "faiss", "streaming"]):
            # Temporarily skip these to isolate the issue
            item.add_marker(pytest.mark.integration)
