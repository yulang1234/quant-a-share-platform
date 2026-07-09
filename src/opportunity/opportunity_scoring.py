"""V1.6.2 opportunity scoring.

The output is an observation state. It is not an order instruction and never
performs network, backfill, or execution work.
"""
from __future__ import annotations

from typing import Any

WEIGHTS = {"market": 0.2, "sentiment": 0.2, "sector": 0.2, "leader": 0.2, "entry": 0.2}


def market_safety(market: dict | None) -> tuple[float, str]:
    if not market:
        return 30.0, "market data insufficient"
    state = market.get("market_state", "unknown")
    risk = market.get("risk_level", "unknown")
    if state == "attack":
        return (85.0 if risk == "low" else 75.0), "market is constructive"
    if state == "neutral":
        return 60.0, "market is neutral"
    if state == "defense":
        return 35.0, "market is defensive"
    if state == "high_risk":
        return 15.0, "market risk is high"
    return 30.0, "market state unknown"


def sentiment_safety(sentiment: dict | None) -> tuple[float, str]:
    if not sentiment:
        return 30.0, "sentiment data insufficient"
    cycle = sentiment.get("sentiment_cycle", "unknown")
    mapping = {
        "warming": (80.0, "sentiment warming"),
        "repair": (70.0, "sentiment repairing"),
        "climax": (55.0, "sentiment hot"),
        "chaotic": (40.0, "sentiment chaotic"),
        "cooling": (20.0, "sentiment cooling"),
        "retreat": (20.0, "sentiment retreating"),
        "ice_point": (15.0, "sentiment weak"),
    }
    return mapping.get(cycle, (30.0, "sentiment unknown"))


def sector_mainline_score(sector: dict | None) -> tuple[float, str]:
    if not sector:
        return 30.0, "sector data insufficient"
    status = sector.get("mainline_status", "unknown")
    prob = _clamp(sector.get("mainline_probability", 30))
    if status == "confirmed_mainline":
        return min(95.0, prob + 10), "sector mainline confirmed"
    if status == "potential_mainline":
        return min(75.0, prob + 5), "sector mainline potential"
    if status == "one_day_theme":
        return 30.0, "sector is one-day theme"
    if status == "cooling_sector":
        return 25.0, "sector cooling"
    if status == "high_risk_sector":
        return 15.0, "sector risk is high"
    return max(prob, 20.0), "sector mainline unknown"


def leader_certainty(leader: dict | None) -> tuple[float, str]:
    if not leader:
        return 25.0, "leader data insufficient"
    leader_type = leader.get("leader_type", "unknown")
    score = _clamp(leader.get("leader_score", 30))
    if leader_type == "leader_1":
        return min(95.0, score), "No.1 leader"
    if leader_type == "leader_2":
        return min(80.0, score), "No.2 leader"
    if leader_type == "make_up_candidate":
        return min(65.0, max(0.0, score - 5)), "catch-up candidate"
    if leader_type == "pseudo_leader":
        return 25.0, "pseudo leader risk"
    if leader_type == "high_risk_chasing":
        return 10.0, "high-risk chasing"
    return min(40.0, max(0.0, score - 10)), "leader type unknown"


def entry_odds(entry: dict | None) -> tuple[float, str]:
    if not entry:
        return 35.0, "entry data insufficient"
    pct = _num(entry.get("pct_chg_5d"))
    above = sum(1 for k in ("above_ma5", "above_ma10", "above_ma20") if entry.get(k))
    drawdown = abs(_num(entry.get("drawdown_20d")))
    if pct > 20:
        return 25.0, "short-term gain is high"
    if drawdown > 15:
        return 20.0, "drawdown is wide"
    if above >= 2 and pct > 0 and drawdown < 10:
        return 70.0, "trend is constructive"
    return 45.0, "entry odds neutral"


def risk_discount(risks: dict | None) -> tuple[float, list[str]]:
    if not risks:
        return 1.0, []
    discount = 1.0
    warnings: list[str] = []
    if risks.get("market_risk") == "high":
        discount *= 0.70
        warnings.append("market risk is high")
    if risks.get("sentiment_risk") == "high":
        discount *= 0.75
        warnings.append("sentiment risk is high")
    if risks.get("chasing_risk"):
        discount *= 0.60
        warnings.append("chasing risk")
    if risks.get("data_quality_risk"):
        discount *= 0.80
        warnings.append("data quality risk")
    return round(max(0.0, min(1.0, discount)), 2), warnings


def compute_opportunity(
    market: dict | None,
    sentiment: dict | None,
    sector: dict | None,
    leader: dict | None,
    entry: dict | None,
    risks: dict | None = None,
) -> dict[str, Any]:
    ms, market_reason = market_safety(market)
    ss, sentiment_reason = sentiment_safety(sentiment)
    sector_score, sector_reason = sector_mainline_score(sector)
    leader_score, leader_reason = leader_certainty(leader)
    entry_score, entry_reason = entry_odds(entry)
    rd, risk_warnings = risk_discount(risks)

    base = (
        ms * WEIGHTS["market"]
        + ss * WEIGHTS["sentiment"]
        + sector_score * WEIGHTS["sector"]
        + leader_score * WEIGHTS["leader"]
        + entry_score * WEIGHTS["entry"]
    )
    score = round(_clamp(base * rd), 1)
    level = _level(score)
    action = _action(level, entry_score, bool(risk_warnings))
    reason = (
        f"market={ms:.0f}; sentiment={ss:.0f}; sector={sector_score:.0f}; "
        f"leader={leader_score:.0f}; entry={entry_score:.0f}; discount={rd:.2f}"
    )
    return {
        "opportunity_score": score,
        "opportunity_level": level,
        "action_signal": action,
        "market_safety_score": ms,
        "sentiment_safety_score": ss,
        "sector_mainline_score": sector_score,
        "leader_certainty_score": leader_score,
        "entry_odds_score": entry_score,
        "risk_discount": rd,
        "reason": reason,
        "reason_details": [market_reason, sentiment_reason, sector_reason, leader_reason, entry_reason],
        "risk_warnings": risk_warnings,
    }


def _level(score: float) -> str:
    if score >= 80:
        return "very_high"
    if score >= 65:
        return "high"
    if score >= 45:
        return "medium"
    if score >= 25:
        return "low"
    if score > 0:
        return "avoid"
    return "unknown"


def _action(level: str, entry_score: float, has_risk: bool) -> str:
    if has_risk and level in ("very_high", "high"):
        return "focus_observe"
    if level in ("very_high", "high"):
        return "small_trial" if entry_score >= 60 else "focus_observe"
    if level == "medium":
        return "wait_for_entry" if entry_score < 50 else "observe"
    if level == "low":
        return "observe"
    if level == "avoid":
        return "cancel_watch"
    return "unknown"


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: Any) -> float:
    return max(0.0, min(100.0, _num(value)))
