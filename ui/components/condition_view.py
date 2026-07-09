"""Streamlit-independent data helpers for V1.6.3 condition view."""
from __future__ import annotations

import pandas as pd

from src.conditions.condition_report import build_condition_markdown
from src.conditions.condition_types import AP_CN, CS, CT


def load_conditions(trade_date: str, sector_name: str, stock_code: str = "") -> dict | None:
    try:
        from src.conditions.condition_engine import build_condition_set
        from src.market.market_environment import build_market_environment
        from src.opportunity.opportunity_index import build_opportunity_index
        from src.sector.sector_mainline import identify_sector_mainline
        from src.sentiment.sentiment_cycle import build_sentiment_cycle

        market = build_market_environment(trade_date).as_dict()
        sentiment = build_sentiment_cycle(trade_date).as_dict()
        sector = identify_sector_mainline(trade_date, sector_name=sector_name).as_dict()
        leader = _load_leader(trade_date, sector_name, stock_code) if stock_code else None
        opportunity = build_opportunity_index(trade_date, sector_name, stock_code).as_dict() if stock_code else None
        return build_condition_set(market, sentiment, sector, leader, opportunity).as_dict()
    except Exception:
        return None


def ctype_cn(value: str) -> str:
    return CT.get(value, value)


def cstatus_cn(value: str) -> str:
    return CS.get(value, value)


def perm_cn(value: str) -> str:
    return AP_CN.get(value, value)


def conditions_to_df(result: dict | None) -> pd.DataFrame:
    rows = []
    for key in (
        "entry_conditions",
        "add_position_conditions",
        "reduce_conditions",
        "exit_conditions",
        "cancel_watch_conditions",
        "invalidation_conditions",
        "risk_conditions",
        "observation_conditions",
    ):
        for item in (result or {}).get(key) or []:
            rows.append(
                {
                    "group": key,
                    "name": item.get("name", ""),
                    "status": item.get("status", ""),
                    "severity": item.get("severity", ""),
                    "blocking": item.get("blocking", False),
                    "reason": item.get("reason", ""),
                }
            )
    return pd.DataFrame(rows)


def condition_csv_bytes(result: dict | None) -> bytes:
    return conditions_to_df(result).to_csv(index=False).encode("utf-8-sig")


def condition_markdown_bytes(result: dict | None) -> bytes:
    if not result:
        return b""
    return build_condition_markdown(result).encode("utf-8")


def _load_leader(trade_date: str, sector_name: str, stock_code: str) -> dict | None:
    try:
        from src.leader.sector_leader import identify_sector_leaders

        result = identify_sector_leaders(trade_date, sector_name)
        for candidate in result.all_candidates:
            if candidate.stock_code == stock_code:
                return candidate.as_dict()
    except Exception:
        return None
    return None
