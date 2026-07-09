"""V1.5.4 sector strength rules — pure scoring functions.

All weights are centralised as module-level constants for easy adjustment
(V2.3 rule-version management).
"""
from __future__ import annotations

from typing import Any

# ── Scoring weights (sum = 100%) ────────────────────────────────────────────

WEIGHT_RETURN_3D = 0.20
WEIGHT_RETURN_5D = 0.20
WEIGHT_RETURN_10D = 0.15
WEIGHT_RETURN_20D = 0.10
WEIGHT_RELATIVE_STRENGTH = 0.15
WEIGHT_UP_RATIO = 0.10
WEIGHT_TURNOVER = 0.05
WEIGHT_LIMIT_UP = 0.05

# ── Strength level thresholds ───────────────────────────────────────────────

THRESHOLD_VERY_STRONG = 80
THRESHOLD_STRONG = 65
THRESHOLD_NEUTRAL = 45
THRESHOLD_WEAK = 30


def compute_strength_score(indicators: dict[str, Any]) -> tuple[int, str, list[str]]:
    """Compute 0-100 strength score and level from sector indicators.

    Args:
        indicators: dict with keys like return_3d, return_5d, up_ratio, etc.

    Returns:
        (score, level, reasons)
    """
    missing = indicators.get("missing_indicator_names") or []
    reasons: list[str] = []
    total_weight = 0.0
    score = 0.0

    # --- 3-day return (0-20) ---
    r3 = indicators.get("return_3d")
    if r3 is not None and "return_3d" not in missing:
        w = WEIGHT_RETURN_3D
        sub = _score_from_return(r3, 100)
        score += sub * w
        total_weight += w
        if r3 > 2:
            reasons.append(f"3日收益率 {r3:.1f}%，短期强势")
        elif r3 < -2:
            reasons.append(f"3日收益率 {r3:.1f}%，短期偏弱")

    # --- 5-day return (0-20) ---
    r5 = indicators.get("return_5d")
    if r5 is not None and "return_5d" not in missing:
        w = WEIGHT_RETURN_5D
        sub = _score_from_return(r5, 100)
        score += sub * w
        total_weight += w
        if r5 > 3:
            reasons.append(f"5日收益率 {r5:.1f}%，中期趋势向好")
        elif r5 < -3:
            reasons.append(f"5日收益率 {r5:.1f}%，中期偏弱")

    # --- 10-day return (0-15) ---
    r10 = indicators.get("return_10d")
    if r10 is not None and "return_10d" not in missing:
        w = WEIGHT_RETURN_10D
        sub = _score_from_return(r10, 100)
        score += sub * w
        total_weight += w

    # --- 20-day return (0-10) ---
    r20 = indicators.get("return_20d")
    if r20 is not None and "return_20d" not in missing:
        w = WEIGHT_RETURN_20D
        sub = _score_from_return(r20, 100)
        score += sub * w
        total_weight += w

    # --- Relative strength (0-15) ---
    # Use the best available relative strength
    rel = indicators.get("relative_strength_5d") or indicators.get("relative_strength_3d")
    if rel is not None:
        w = WEIGHT_RELATIVE_STRENGTH
        sub = _score_from_return(rel, 100)
        score += sub * w
        total_weight += w
        if rel > 2:
            reasons.append("相对基准指数明显跑赢")
        elif rel < -2:
            reasons.append("相对基准指数明显跑输")

    # --- Up ratio (0-10) ---
    up_ratio = indicators.get("up_ratio")
    if up_ratio is not None:
        w = WEIGHT_UP_RATIO
        sub = up_ratio * 100  # 0-100
        score += sub * w
        total_weight += w
        if up_ratio >= 0.7:
            reasons.append(f"上涨家数占比 {up_ratio:.0%}，板块内多数个股上涨")
        elif up_ratio <= 0.3:
            reasons.append(f"上涨家数占比 {up_ratio:.0%}，板块内多数个股下跌")

    # --- Turnover (0-5) ---
    t20 = indicators.get("turnover_ratio_20d")
    if t20 is not None and "turnover_ratio_20d" not in missing:
        w = WEIGHT_TURNOVER
        sub = _score_from_turnover(t20)
        score += sub * w
        total_weight += w
        if t20 >= 1.3:
            reasons.append(f"成交额较20日均值放大至 {t20:.1f} 倍，资金关注度提升")
        elif t20 <= 0.7:
            reasons.append("成交额明显萎缩，交投清淡")

    # --- Limit up count (0-5) ---
    limit_up = indicators.get("limit_up_count", 0)
    w = WEIGHT_LIMIT_UP
    if limit_up >= 10:
        sub = 100.0
        reasons.append(f"板块内涨停 {limit_up} 家，短线情绪极强")
    elif limit_up >= 5:
        sub = 75.0
        reasons.append(f"板块内涨停 {limit_up} 家，有一定赚钱效应")
    elif limit_up >= 2:
        sub = 50.0
    elif limit_up >= 1:
        sub = 30.0
    else:
        sub = 0.0
    score += sub * w
    total_weight += w

    # Normalise by total weight used
    if total_weight > 0:
        score = score / total_weight
    else:
        score = 0.0

    final_score = max(0, min(100, int(round(score))))
    level = _score_to_level(final_score, indicators)

    if not reasons:
        reasons.append("板块强度指标综合评估")

    return final_score, level, reasons


def _score_from_return(ret: float, max_score: float = 100) -> float:
    """Map a return value to a 0-max_score sub-score."""
    # Simple linear mapping: +5% → max, -5% → 0
    clamped = max(-5.0, min(5.0, ret))
    return (clamped + 5.0) / 10.0 * max_score


def _score_from_turnover(ratio: float) -> float:
    """Map turnover ratio to 0-100 sub-score."""
    if ratio >= 1.5:
        return 100.0
    elif ratio >= 1.2:
        return 80.0
    elif ratio >= 1.0:
        return 60.0
    elif ratio >= 0.8:
        return 40.0
    elif ratio >= 0.5:
        return 20.0
    else:
        return 0.0


def _score_to_level(score: int, indicators: dict[str, Any]) -> str:
    """Convert numeric score to strength level string."""
    valid = indicators.get("valid_stock_count", 0)
    if valid == 0 or not indicators:
        return "unknown"

    if score >= THRESHOLD_VERY_STRONG:
        return "very_strong"
    elif score >= THRESHOLD_STRONG:
        return "strong"
    elif score >= THRESHOLD_NEUTRAL:
        return "neutral"
    elif score >= THRESHOLD_WEAK:
        return "weak"
    else:
        return "very_weak"


def compute_benchmark_returns(
    all_pct_changes: dict[str, list[float]],
    dates: list[str],
) -> dict[str, float | None]:
    """Compute equal-weighted benchmark returns from all stocks.

    Args:
        all_pct_changes: {trade_date: [pct_change values for all stocks]}
        dates: sorted list of all trading dates.

    Returns:
        {return_3d, return_5d, return_10d, return_20d} or None if insufficient.
    """
    if not all_pct_changes or len(dates) < 2:
        return {"return_3d": None, "return_5d": None,
                "return_10d": None, "return_20d": None}

    result: dict[str, float | None] = {}
    for label, n_days in [("3d", 3), ("5d", 5), ("10d", 10), ("20d", 20)]:
        result[f"return_{label}"] = _benchmark_return(all_pct_changes, dates, n_days)
    return result


def _benchmark_return(
    all_pct: dict[str, list[float]], dates: list[str], n_days: int,
) -> float | None:
    """Calculate n-day compound return for the equal-weighted market."""
    if len(dates) < n_days:
        return None

    recent_dates = dates[-n_days:]
    compound = 1.0
    for d in recent_dates:
        vals = all_pct.get(d, [])
        if not vals:
            return None
        avg_pct = sum(vals) / len(vals)
        compound *= (1.0 + avg_pct / 100.0)
    return round((compound - 1.0) * 100, 4)
