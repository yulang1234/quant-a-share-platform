"""V1.5.0 Daily Decision Streamlit data-prep helpers.

No Streamlit import, no writes, no network calls, no trading/backfill
execution. These helpers only build display data and Markdown bytes.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.decision.daily_decision_card import build_daily_decision_card
from src.report.daily_decision_report import render_daily_decision_markdown


STATUS_CN = {
    "unknown": "未知",
    "defensive": "防守",
    "neutral": "中性",
    "aggressive": "进攻",
    "weak": "偏弱",
    "strong": "偏强",
    "low": "低",
    "medium": "中",
    "high": "高",
    "healthy": "健康",
    "usable_with_gaps": "可用但有缺口",
    "risky": "风险较高",
    "not_recommended": "不建议分析",
    "unavailable": "不可用",
}


def status_to_cn(status: str | None) -> str:
    if status is None:
        return "未知"
    return STATUS_CN.get(status, status)


def load_daily_decision_card(trade_date: str | None = None) -> dict[str, Any]:
    """Load a structured daily decision card as a dict."""
    try:
        return build_daily_decision_card(trade_date).as_dict()
    except Exception as exc:
        return {
            "trade_date": trade_date,
            "overall_bias": "unknown",
            "market_state": "unknown",
            "sentiment_cycle": "unknown",
            "risk_level": "unknown",
            "strong_sectors": [],
            "risk_warnings": ["决策卡生成失败，今日仅做观察"],
            "suggested_actions": ["数据不足，今日仅做观察"],
            "observation_conditions": [],
            "invalidation_conditions": [],
            "data_quality_status": "unknown",
            "generated_at": "",
            "issue_summary": [f"daily_decision_card 读取失败: {type(exc).__name__}"],
            "market_snapshot": {},
            "sentiment_snapshot": {},
            "sector_snapshot": {},
        }


def overview_metrics(card: dict[str, Any]) -> dict[str, Any]:
    """Small KPI dict for the UI."""
    card = card or {}
    return {
        "trade_date": card.get("trade_date") or "unknown",
        "overall_bias": card.get("overall_bias") or "unknown",
        "overall_bias_cn": status_to_cn(card.get("overall_bias")),
        "market_state": card.get("market_state") or "unknown",
        "market_state_cn": status_to_cn(card.get("market_state")),
        "sentiment_cycle": card.get("sentiment_cycle") or "unknown",
        "sentiment_cycle_cn": status_to_cn(card.get("sentiment_cycle")),
        "risk_level": card.get("risk_level") or "unknown",
        "risk_level_cn": status_to_cn(card.get("risk_level")),
        "data_quality_status": card.get("data_quality_status") or "unknown",
        "data_quality_status_cn": status_to_cn(card.get("data_quality_status")),
        "strong_sector_count": len(card.get("strong_sectors") or []),
        "generated_at": card.get("generated_at") or "",
    }


def sectors_to_df(card: dict[str, Any]) -> pd.DataFrame:
    rows = list((card or {}).get("strong_sectors") or [])
    cols = [
        "rank", "sector_name", "sector_type", "strength_score",
        "change_pct", "turnover_amount", "up_stock_count",
        "down_stock_count", "limit_up_count", "issue_summary",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    return df[[c for c in cols if c in df.columns]]


def render_card_markdown(card: dict[str, Any]) -> str:
    return render_daily_decision_markdown(card)


def to_markdown_bytes(card: dict[str, Any]) -> bytes:
    return render_card_markdown(card).encode("utf-8-sig")
