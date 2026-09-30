"""Token-cost estimate and the hard cap that refuses a run before it starts.

Input tokens are estimated as ``ceil(characters / 4)``, at least 1. Output
tokens for the estimate are a fixed allowance of 256. Actual spend uses the
token counts returned by the call. Prices are USD per million tokens.
"""

from __future__ import annotations

import math

from mm.config import PricesConfig, TokenPrice

ASSUMED_OUTPUT_TOKENS = 256


class BudgetExceededError(Exception):
    """The estimated cost is above ``budget.max_usd``."""


def estimate_input_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def price_for(prices: PricesConfig, model_id: str) -> TokenPrice:
    for price in prices.prices:
        if price.model_id == model_id:
            return price
    message = f"No price in prices.yaml for model {model_id}"
    raise BudgetExceededError(message)


def call_cost(input_tokens: int, output_tokens: int, price: TokenPrice) -> float:
    input_cost = input_tokens * price.usd_per_million_input_tokens
    output_cost = output_tokens * price.usd_per_million_output_tokens
    return (input_cost + output_cost) / 1_000_000


def estimate_call_cost(full_prompt: str, price: TokenPrice) -> float:
    return call_cost(estimate_input_tokens(full_prompt), ASSUMED_OUTPUT_TOKENS, price)


def require_within_budget(estimated_usd: float, max_usd: float) -> None:
    """Refuse to start when the estimate is strictly above the cap."""
    if estimated_usd > max_usd:
        message = f"Estimated cost ${estimated_usd:.6f} exceeds budget.max_usd ${max_usd:.6f}"
        raise BudgetExceededError(message)
