"""
Test Cost Calculator

Tests for LLM cost calculation and pricing lookups
"""
import pytest
from app.utils.cost_calculator import calculate_cost, get_model_pricing


def test_basic_cost_calculation():
    """Test basic cost calculation for known models"""
    # GPT-4: $30/$60 per 1M tokens
    cost = calculate_cost("gpt-4", 1000, 500)
    assert cost == pytest.approx(0.06, abs=0.001)  # (1000 * 30 + 500 * 60) / 1M

    # GPT-3.5-turbo: $0.50/$1.50 per 1M tokens
    cost = calculate_cost("gpt-3.5-turbo", 1000, 500)
    assert cost == pytest.approx(0.00125, abs=0.00001)  # (1000 * 0.5 + 500 * 1.5) / 1M


def test_dated_model_names():
    """
    Test that dated model names match the correct pricing

    This is a critical test: before the fix, "gpt-4o-mini-2024-07-18"
    matched "gpt-4" instead of "gpt-4o-mini", resulting in 120x inflated costs.
    """
    # gpt-4o-mini: $0.15/$0.60 per 1M tokens
    base_cost = calculate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
    dated_cost = calculate_cost("gpt-4o-mini-2024-07-18", 1_000_000, 1_000_000)

    # Both should have the same cost
    assert base_cost == dated_cost
    assert base_cost == pytest.approx(0.75, abs=0.01)  # $0.15 + $0.60 = $0.75

    # Ensure it didn't match gpt-4 pricing ($90)
    assert base_cost < 1.0, "Should not match expensive gpt-4 pricing"


def test_dated_model_prefix_matching():
    """Test that longest prefix wins for dated models"""
    # gpt-4o-2024-08-06 should match "gpt-4o" not "gpt-4"
    cost_4o = calculate_cost("gpt-4o", 1_000_000, 1_000_000)
    cost_4o_dated = calculate_cost("gpt-4o-2024-08-06", 1_000_000, 1_000_000)
    assert cost_4o == cost_4o_dated

    # gpt-4-turbo-2024-04-09 should match "gpt-4-turbo" not "gpt-4"
    cost_turbo = calculate_cost("gpt-4-turbo", 1_000_000, 1_000_000)
    cost_turbo_dated = calculate_cost("gpt-4-turbo-2024-04-09", 1_000_000, 1_000_000)
    assert cost_turbo == cost_turbo_dated


def test_none_tokens():
    """Test handling of None tokens"""
    # Both None
    assert calculate_cost("gpt-4", None, None) is None

    # One None (should treat as 0)
    cost = calculate_cost("gpt-4", 1000, None)
    assert cost == pytest.approx(0.03, abs=0.001)  # 1000 * 30 / 1M

    cost = calculate_cost("gpt-4", None, 500)
    assert cost == pytest.approx(0.03, abs=0.001)  # 500 * 60 / 1M


def test_unknown_model_fallback():
    """Test fallback to default pricing for unknown models"""
    cost = calculate_cost("unknown-model-xyz", 1000, 500)

    # Should use default pricing ($1/$3 per 1M tokens)
    expected = (1000 * 1.0 + 500 * 3.0) / 1_000_000
    assert cost == pytest.approx(expected, abs=0.00001)


def test_case_insensitive():
    """Test that model names are case-insensitive"""
    cost_lower = calculate_cost("gpt-4", 1000, 500)
    cost_upper = calculate_cost("GPT-4", 1000, 500)
    cost_mixed = calculate_cost("GpT-4", 1000, 500)

    assert cost_lower == cost_upper == cost_mixed


def test_claude_pricing():
    """Test Claude model pricing"""
    # Claude-3-Opus: $15/$75 per 1M tokens
    cost = calculate_cost("claude-3-opus-20240229", 1000, 500)
    expected = (1000 * 15.0 + 500 * 75.0) / 1_000_000
    assert cost == pytest.approx(expected, abs=0.00001)


def test_get_model_pricing():
    """Test get_model_pricing helper function"""
    # Known model
    pricing = get_model_pricing("gpt-4")
    assert pricing == (30.00, 60.00)

    # Dated model (should match base model)
    pricing = get_model_pricing("gpt-4o-mini-2024-07-18")
    assert pricing == (0.15, 0.60)

    # Unknown model
    pricing = get_model_pricing("unknown-model")
    assert pricing is None
