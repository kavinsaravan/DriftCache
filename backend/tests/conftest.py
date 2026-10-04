"""
Pytest configuration for DriftCache tests
"""
import pytest

# Tests are marked explicitly with @pytest.mark.slow when they need special setup
# No automatic marking based on file names - all tests run in CI by default
