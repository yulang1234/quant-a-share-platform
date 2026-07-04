"""Score model configuration — defaults and validation. V1.3."""
from __future__ import annotations
import json
from typing import Any

DEFAULT_SCORE_MODELS: list[dict[str, Any]] = [
    {"model_name": "momentum_quality_score", "factor_weights": json.dumps({"return_20d": 0.25, "momentum_20d": 0.25, "close_ma20_ratio": 0.20, "price_position_60d": 0.15, "volatility_20d": 0.15}), "score_method": "percentile_rank_weighted_sum", "description": "Momentum + quality multi-factor score", "is_active": True},
    {"model_name": "trend_volume_score", "factor_weights": json.dumps({"close_ma20_ratio": 0.25, "close_ma60_ratio": 0.25, "volume_ratio_5_20": 0.25, "price_position_60d": 0.25}), "score_method": "percentile_rank_weighted_sum", "description": "Trend + volume score", "is_active": True},
    {"model_name": "low_vol_stable_score", "factor_weights": json.dumps({"volatility_20d": 0.35, "volatility_60d": 0.25, "return_20d": 0.20, "price_position_60d": 0.20}), "score_method": "percentile_rank_weighted_sum", "description": "Low volatility stable score", "is_active": True},
]

VALID_METHODS = {"percentile_rank_weighted_sum", "direction_value_weighted_sum"}


def get_default_score_model(model_name: str) -> dict[str, Any] | None:
    for m in DEFAULT_SCORE_MODELS:
        if m["model_name"] == model_name:
            return dict(m)
    return None


def list_default_score_models() -> list[str]:
    return [m["model_name"] for m in DEFAULT_SCORE_MODELS]


def normalize_factor_weights(factor_weights: dict[str, float]) -> dict[str, float]:
    if not factor_weights: raise ValueError("factor_weights is empty")
    for k, v in factor_weights.items():
        if v < 0: raise ValueError(f"Negative weight for '{k}': {v}")
    total = sum(factor_weights.values())
    if total == 0: raise ValueError("Sum of factor_weights is zero")
    return {k: v / total for k, v in factor_weights.items()}


def validate_score_model_config(config: dict[str, Any]) -> None:
    if not config.get("model_name"): raise ValueError("model_name is required")
    w = config.get("factor_weights")
    if not w: raise ValueError("factor_weights is required")
    if isinstance(w, str):
        try: w = json.loads(w)
        except json.JSONDecodeError: raise ValueError("factor_weights must be valid JSON")
    if not isinstance(w, dict) or len(w) == 0: raise ValueError("factor_weights must be a non-empty dict")
    total = 0.0
    for k, v in w.items():
        if not isinstance(v, (int, float)): raise ValueError(f"Weight for '{k}' must be a number, got {type(v).__name__}")
        if v < 0: raise ValueError(f"Negative weight for '{k}': {v}")
        total += v
    if total == 0: raise ValueError("Sum of factor_weights must be > 0")
    sm = config.get("score_method", "percentile_rank_weighted_sum")
    if sm not in VALID_METHODS: raise ValueError(f"score_method must be one of {VALID_METHODS}, got '{sm}'")
