"""
Cost Calculator

Calculates estimated costs for LLM API calls based on token usage and model pricing.

Pricing data as of January 2025 (USD per 1M tokens)
"""
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# Pricing table (USD per 1M tokens)
# Format: {model_name: (input_price, output_price)}
MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # OpenAI GPT-4 models
    "gpt-4": (30.00, 60.00),
    "gpt-4-32k": (60.00, 120.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4-turbo-preview": (10.00, 30.00),
    "gpt-4o": (5.00, 15.00),
    "gpt-4o-mini": (0.15, 0.60),

    # OpenAI GPT-3.5 models
    "gpt-3.5-turbo": (0.50, 1.50),
    "gpt-3.5-turbo-16k": (3.00, 4.00),

    # Anthropic Claude models
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-sonnet-20240229": (3.00, 15.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "claude-3-5-sonnet-20240620": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (1.00, 5.00),

    # Gemini models
    "gemini-pro": (0.50, 1.50),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),

    # Default fallback (conservative estimate)
    "default": (1.00, 3.00),
}


def calculate_cost(
    model: str,
    input_tokens: Optional[int],
    output_tokens: Optional[int]
) -> Optional[float]:
    """
    Calculate estimated cost for an LLM API call

    Args:
        model: Model name (e.g., "gpt-4", "claude-3-opus")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in USD, or None if tokens not available
    """
    if input_tokens is None and output_tokens is None:
        return None

    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0

    # Look up pricing (case-insensitive, handle model variants)
    model_lower = model.lower()
    pricing = None

    # Try exact match first
    if model_lower in MODEL_PRICING:
        pricing = MODEL_PRICING[model_lower]
    else:
        # Try prefix match (e.g., "gpt-4-0613" matches "gpt-4")
        # IMPORTANT: Check longest prefixes first to avoid "gpt-4o-mini-2024" matching "gpt-4"
        for model_key in sorted(MODEL_PRICING.keys(), key=len, reverse=True):
            if model_lower.startswith(model_key):
                pricing = MODEL_PRICING[model_key]
                break

    # Fallback to default pricing
    if pricing is None:
        logger.warning(f"Unknown model pricing for '{model}', using default rates")
        pricing = MODEL_PRICING["default"]

    input_price_per_million, output_price_per_million = pricing

    # Calculate cost (pricing is per 1M tokens)
    input_cost = (input_tokens / 1_000_000) * input_price_per_million
    output_cost = (output_tokens / 1_000_000) * output_price_per_million
    total_cost = input_cost + output_cost

    logger.debug(
        f"Cost calculation: {model} | "
        f"input={input_tokens} tokens (${input_cost:.6f}) + "
        f"output={output_tokens} tokens (${output_cost:.6f}) = "
        f"${total_cost:.6f}"
    )

    return total_cost


def get_model_pricing(model: str) -> Optional[Tuple[float, float]]:
    """
    Get pricing for a specific model

    Args:
        model: Model name

    Returns:
        Tuple of (input_price_per_million, output_price_per_million) or None
    """
    model_lower = model.lower()

    # Try exact match
    if model_lower in MODEL_PRICING:
        return MODEL_PRICING[model_lower]

    # Try prefix match (longest first)
    for model_key in sorted(MODEL_PRICING.keys(), key=len, reverse=True):
        if model_lower.startswith(model_key):
            return MODEL_PRICING[model_key]

    return None


def estimate_savings(
    cache_hits: int,
    average_input_tokens: float,
    average_output_tokens: float,
    model: str
) -> float:
    """
    Estimate cost savings from cache hits

    Args:
        cache_hits: Number of cache hits
        average_input_tokens: Average input tokens per request
        average_output_tokens: Average output tokens per request
        model: Model name

    Returns:
        Estimated savings in USD
    """
    cost_per_hit = calculate_cost(
        model,
        int(average_input_tokens),
        int(average_output_tokens)
    )

    if cost_per_hit is None:
        return 0.0

    total_savings = cache_hits * cost_per_hit
    return total_savings
