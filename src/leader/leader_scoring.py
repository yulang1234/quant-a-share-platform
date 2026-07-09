"""V1.6.1 sector leader scoring.

The module is pure and local-only. It does not fetch data, write state, or emit
any execution instruction.
"""
from __future__ import annotations

from typing import Any

WEIGHTS = {
    "relative_strength": 0.25,
    "turnover": 0.15,
    "price_rank": 0.15,
    "resilience": 0.15,
    "startup": 0.10,
    "trend_structure": 0.10,
    "continuity": 0.10,
}


def compute_leader_score(features: dict[str, Any]) -> dict[str, Any]:
    """Return all sub-scores and a final 0-100 leader score."""
    scores = {
        "relative_strength_score": _rel_strength(features),
        "turnover_score": _turnover(features),
        "price_rank_score": _price_rank(features),
        "resilience_score": _resilience(features),
        "startup_score": _startup(features),
        "trend_structure_score": _trend(features),
        "continuity_score": _continuity(features),
    }
    total = (
        scores["relative_strength_score"] * WEIGHTS["relative_strength"]
        + scores["turnover_score"] * WEIGHTS["turnover"]
        + scores["price_rank_score"] * WEIGHTS["price_rank"]
        + scores["resilience_score"] * WEIGHTS["resilience"]
        + scores["startup_score"] * WEIGHTS["startup"]
        + scores["trend_structure_score"] * WEIGHTS["trend_structure"]
        + scores["continuity_score"] * WEIGHTS["continuity"]
    )
    scores["leader_score"] = round(_clamp(total), 1)
    return scores


def _rel_strength(f: dict[str, Any]) -> float:
    pct_5d = _num(f.get("pct_chg_5d"))
    sector_5d = _num(f.get("sector_avg_5d"))
    return _clamp((pct_5d - sector_5d + 5) / 10 * 100)


def _turnover(f: dict[str, Any]) -> float:
    return _rank_score(f.get("turnover_rank_in_sector"), f.get("sector_stock_count"))


def _price_rank(f: dict[str, Any]) -> float:
    return _rank_score(f.get("price_rank_in_sector"), f.get("sector_stock_count"))


def _resilience(f: dict[str, Any]) -> float:
    drawdown = abs(_num(f.get("drawdown_20d")))
    return 80.0 if drawdown == 0 else _clamp(100 - drawdown * 5)


def _startup(f: dict[str, Any]) -> float:
    return {"early": 90.0, "sync": 65.0, "lag": 30.0, "unknown": 40.0}.get(
        str(f.get("startup_timing", "unknown")), 40.0
    )


def _trend(f: dict[str, Any]) -> float:
    above = sum(1 for k in ("above_ma5", "above_ma10", "above_ma20") if f.get(k))
    return {3: 90.0, 2: 70.0, 1: 45.0, 0: 20.0}[above]


def _continuity(f: dict[str, Any]) -> float:
    return _clamp(_num(f.get("up_days_recent")) / 5 * 100)


def _rank_score(rank: Any, total: Any) -> float:
    total_n = max(int(_num(total, 1)), 1)
    rank_n = int(_num(rank, total_n))
    return _clamp((1 - (rank_n - 1) / total_n) * 100)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))
