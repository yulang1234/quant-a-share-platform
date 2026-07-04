"""
Strategy configuration — default strategies and validation.

V1.0: single_factor / multi_factor TopK strategies.
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_STRATEGIES: list[dict[str, Any]] = [
    {
        "strategy_name": "single_return_20d_top20",
        "strategy_type": "single_factor",
        "factor_name": "return_20d",
        "top_k": 20,
        "description": "20-day return TopK",
        "is_active": True,
    },
    {
        "strategy_name": "single_momentum_20d_top20",
        "strategy_type": "single_factor",
        "factor_name": "momentum_20d",
        "top_k": 20,
        "description": "20-day momentum TopK",
        "is_active": True,
    },
    {
        "strategy_name": "multi_momentum_quality_top20",
        "strategy_type": "multi_factor",
        "factor_weights": json.dumps({"return_20d": 0.3, "momentum_20d": 0.3, "close_ma20_ratio": 0.2, "price_position_60d": 0.2}),
        "top_k": 20,
        "description": "Momentum + quality multi-factor TopK",
        "is_active": True,
    },
    {
        "strategy_name": "low_vol_momentum_top20",
        "strategy_type": "multi_factor",
        "factor_weights": json.dumps({"momentum_20d": 0.4, "volatility_20d": 0.3, "price_position_60d": 0.3}),
        "top_k": 20,
        "description": "Low volatility + momentum TopK",
        "is_active": True,
    },
]


def get_default_strategy(strategy_name: str) -> dict[str, Any] | None:
    for s in DEFAULT_STRATEGIES:
        if s["strategy_name"] == strategy_name:
            return dict(s)
    return None


def list_default_strategies() -> list[str]:
    return [s["strategy_name"] for s in DEFAULT_STRATEGIES]


def validate_strategy_config(config: dict[str, Any]) -> None:
    """Validate a strategy config dict. Raises ValueError on invalid configs."""
    name = config.get("strategy_name")
    if not name:
        raise ValueError("strategy_name is required")
    stype = config.get("strategy_type", "")
    if stype not in ("single_factor", "multi_factor"):
        raise ValueError(f"strategy_type must be single_factor or multi_factor, got '{stype}'")
    top_k = config.get("top_k", 0)
    if not isinstance(top_k, int) or top_k <= 0:
        raise ValueError(f"top_k must be > 0, got {top_k}")
    if stype == "single_factor":
        if not config.get("factor_name"):
            raise ValueError("single_factor strategy requires factor_name")
    if stype == "multi_factor":
        weights = config.get("factor_weights")
        if not weights:
            raise ValueError("multi_factor strategy requires factor_weights")
        if isinstance(weights, str):
            try:
                weights = json.loads(weights)
            except json.JSONDecodeError:
                raise ValueError("factor_weights must be valid JSON")
        if not isinstance(weights, dict) or len(weights) == 0:
            raise ValueError("factor_weights must be a non-empty dict")
