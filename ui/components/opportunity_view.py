"""Streamlit-independent data helpers for V1.6.2 opportunity view."""
from __future__ import annotations

import pandas as pd

from src.opportunity.opportunity_report import build_opportunity_markdown
from src.opportunity.opportunity_types import ACTION_CN, LEVEL_CN


def load_opportunity(trade_date: str, sector_name: str, stock_code: str = "") -> dict | None:
    try:
        from src.opportunity.opportunity_index import build_opportunity_index

        return build_opportunity_index(trade_date, sector_name, stock_code).as_dict()
    except Exception:
        return None


def level_cn(level: str) -> str:
    return LEVEL_CN.get(level, level)


def action_cn(action: str) -> str:
    return ACTION_CN.get(action, action)


def opportunity_score_df(result: dict | None) -> pd.DataFrame:
    result = result or {}
    rows = [
        ("market_safety_score", result.get("market_safety_score", 0)),
        ("sentiment_safety_score", result.get("sentiment_safety_score", 0)),
        ("sector_mainline_score", result.get("sector_mainline_score", 0)),
        ("leader_certainty_score", result.get("leader_certainty_score", 0)),
        ("entry_odds_score", result.get("entry_odds_score", 0)),
        ("risk_discount", result.get("risk_discount", 1)),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def opportunity_csv_bytes(result: dict | None) -> bytes:
    return opportunity_score_df(result).to_csv(index=False).encode("utf-8-sig")


def opportunity_markdown_bytes(result: dict | None) -> bytes:
    if not result:
        return b""
    return build_opportunity_markdown(result).encode("utf-8")
