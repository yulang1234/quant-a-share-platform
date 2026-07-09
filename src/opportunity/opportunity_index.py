"""V1.6.2 opportunity index entry point."""
from __future__ import annotations

import numpy as np

from src.opportunity.opportunity_scoring import compute_opportunity
from src.opportunity.opportunity_types import OpportunityResult


def build_opportunity_index(
    trade_date: str, sector_name: str, stock_code: str = ""
) -> OpportunityResult:
    """Build an opportunity index from existing local modules."""
    td = str(trade_date)[:10]
    market = _safe_market(td)
    sentiment = _safe_sentiment(td)
    sector = _safe_mainline(td, sector_name)
    leader = _safe_leader(td, sector_name, stock_code) if stock_code else None
    entry = _safe_entry(stock_code) if stock_code else None
    risks = {
        "market_risk": "high" if market and market.get("risk_level") in ("high", "extreme") else None,
        "chasing_risk": bool(leader and leader.get("leader_type") == "high_risk_chasing"),
        "data_quality_risk": not all([market, sentiment, sector]),
    }
    result = compute_opportunity(market, sentiment, sector, leader, entry, risks)
    return OpportunityResult(
        trade_date=td,
        sector_name=sector_name,
        stock_code=stock_code,
        opportunity_score=result["opportunity_score"],
        opportunity_level=result["opportunity_level"],
        action_signal=result["action_signal"],
        market_safety_score=result["market_safety_score"],
        sentiment_safety_score=result["sentiment_safety_score"],
        sector_mainline_score=result["sector_mainline_score"],
        leader_certainty_score=result["leader_certainty_score"],
        entry_odds_score=result["entry_odds_score"],
        risk_discount=result["risk_discount"],
        reason=result["reason"],
        risk_warnings=result.get("risk_warnings", []),
        observation_conditions=_build_observation_conditions(result),
        invalidation_conditions=_build_invalidation_conditions(result),
    )


def _safe_market(td: str) -> dict | None:
    try:
        from src.market.market_environment import build_market_environment

        return build_market_environment(td).as_dict()
    except Exception:
        return None


def _safe_sentiment(td: str) -> dict | None:
    try:
        from src.sentiment.sentiment_cycle import build_sentiment_cycle

        return build_sentiment_cycle(td).as_dict()
    except Exception:
        return None


def _safe_mainline(td: str, name: str) -> dict | None:
    try:
        from src.sector.sector_mainline import identify_sector_mainline

        return identify_sector_mainline(td, sector_name=name).as_dict()
    except Exception:
        return None


def _safe_leader(td: str, name: str, code: str) -> dict | None:
    try:
        from src.leader.sector_leader import identify_sector_leaders

        result = identify_sector_leaders(td, name)
        for candidate in result.all_candidates:
            if candidate.stock_code == code:
                return candidate.as_dict()
        return None
    except Exception:
        return None


def _safe_entry(code: str) -> dict | None:
    try:
        from src.storage.duckdb_repo import query_df

        df = query_df(
            "SELECT close, pct_change FROM stock_daily_raw "
            "WHERE stock_code=? ORDER BY trade_date DESC LIMIT 20",
            [code],
        )
        if df is None or df.empty:
            return None
        closes = df["close"].astype(float).values
        pcts = df["pct_change"].dropna().astype(float).values
        peak = float(np.max(closes[:20])) if len(closes) else 0.0
        return {
            "pct_chg_5d": float(np.mean(pcts[:5])) if len(pcts) >= 5 else 0.0,
            "above_ma5": bool(len(closes) >= 5 and closes[0] > np.mean(closes[:5])),
            "above_ma10": bool(len(closes) >= 10 and closes[0] > np.mean(closes[:10])),
            "above_ma20": bool(len(closes) >= 20 and closes[0] > np.mean(closes[:20])),
            "drawdown_20d": float((peak - closes[0]) / peak * 100) if peak > 0 else 0.0,
        }
    except Exception:
        return None


def _build_observation_conditions(result: dict) -> list[str]:
    conditions = []
    if result.get("market_safety_score", 0) < 40:
        conditions.append("wait for market safety improvement")
    if result.get("leader_certainty_score", 0) < 30:
        conditions.append("wait for clearer leader status")
    if result.get("entry_odds_score", 0) < 40:
        conditions.append("wait for better entry setup")
    return conditions or ["continue monitoring sector and candidate"]


def _build_invalidation_conditions(result: dict) -> list[str]:
    conditions = ["leader score deteriorates", "risk discount falls below 0.5"]
    if result.get("sector_mainline_score", 0) >= 50:
        conditions.append("sector mainline status weakens")
    if result.get("market_safety_score", 0) >= 50:
        conditions.append("market turns defensive or high risk")
    return conditions
