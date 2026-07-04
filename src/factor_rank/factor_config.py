"""
Factor configuration — direction, category, description for each V0.7 factor.

Unknown factors default to ``direction = "neutral"``.
"""

from __future__ import annotations

FACTOR_CONFIG: dict[str, dict[str, str]] = {
    # ── Positive factors (higher is better) ──
    "return_5d":             {"direction": "positive", "category": "return"},
    "return_10d":            {"direction": "positive", "category": "return"},
    "return_20d":            {"direction": "positive", "category": "return"},
    "return_60d":            {"direction": "positive", "category": "return"},
    "momentum_5d":           {"direction": "positive", "category": "momentum"},
    "momentum_10d":          {"direction": "positive", "category": "momentum"},
    "momentum_20d":          {"direction": "positive", "category": "momentum"},
    "momentum_60d":          {"direction": "positive", "category": "momentum"},
    "close_ma5_ratio":       {"direction": "positive", "category": "ma"},
    "close_ma10_ratio":      {"direction": "positive", "category": "ma"},
    "close_ma20_ratio":      {"direction": "positive", "category": "ma"},
    "close_ma60_ratio":      {"direction": "positive", "category": "ma"},
    "close_ma120_ratio":     {"direction": "positive", "category": "ma"},
    "volume_ratio_5_20":     {"direction": "positive", "category": "volume"},
    "volume_ratio_20_60":    {"direction": "positive", "category": "volume"},
    "price_position_20d":    {"direction": "positive", "category": "price_position"},
    "price_position_60d":    {"direction": "positive", "category": "price_position"},

    # ── Negative factors (lower is better) ──
    "volatility_5d":         {"direction": "negative", "category": "volatility"},
    "volatility_10d":        {"direction": "negative", "category": "volatility"},
    "volatility_20d":        {"direction": "negative", "category": "volatility"},
    "volatility_60d":        {"direction": "negative", "category": "volatility"},

    # ── Neutral / observation factors ──
    "return_1d":             {"direction": "neutral", "category": "return"},
    "ma5":                   {"direction": "neutral", "category": "ma"},
    "ma10":                  {"direction": "neutral", "category": "ma"},
    "ma20":                  {"direction": "neutral", "category": "ma"},
    "ma60":                  {"direction": "neutral", "category": "ma"},
    "ma120":                 {"direction": "neutral", "category": "ma"},
    "volume_ma5":            {"direction": "neutral", "category": "volume"},
    "volume_ma20":           {"direction": "neutral", "category": "volume"},
    "volume_ma60":           {"direction": "neutral", "category": "volume"},
    "amount_ma5":            {"direction": "neutral", "category": "amount"},
    "amount_ma20":           {"direction": "neutral", "category": "amount"},
    "amount_ma60":           {"direction": "neutral", "category": "amount"},
    "turnover_ma5":          {"direction": "neutral", "category": "turnover"},
    "turnover_ma20":         {"direction": "neutral", "category": "turnover"},
    "turnover_ma60":         {"direction": "neutral", "category": "turnover"},
    "turnover_ratio_5_20":   {"direction": "neutral", "category": "turnover"},
    "high_20d":              {"direction": "neutral", "category": "price_position"},
    "low_20d":               {"direction": "neutral", "category": "price_position"},
    "high_60d":              {"direction": "neutral", "category": "price_position"},
    "low_60d":               {"direction": "neutral", "category": "price_position"},
}


def get_factor_config(factor_name: str) -> dict[str, str]:
    """Return config dict for *factor_name*, defaulting to neutral."""
    return FACTOR_CONFIG.get(factor_name, {"direction": "neutral", "category": "unknown"})


def get_factor_direction(factor_name: str) -> str:
    """Return ``"positive"``, ``"negative"``, or ``"neutral"``."""
    return get_factor_config(factor_name)["direction"]


def list_supported_factors() -> list[str]:
    """Return all factor names known to the config."""
    return sorted(FACTOR_CONFIG.keys())
