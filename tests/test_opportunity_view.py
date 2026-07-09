"""V1.6.2 opportunity view data helpers tests."""
from __future__ import annotations

from ui.components.opportunity_view import opportunity_csv_bytes, opportunity_markdown_bytes, opportunity_score_df


def _result():
    return {
        "trade_date": "2026-07-09",
        "sector_name": "demo",
        "opportunity_score": 60,
        "opportunity_level": "medium",
        "action_signal": "observe",
        "market_safety_score": 60,
        "sentiment_safety_score": 60,
        "sector_mainline_score": 60,
        "leader_certainty_score": 60,
        "entry_odds_score": 60,
        "risk_discount": 1,
    }


def test_opportunity_score_df_handles_empty():
    df = opportunity_score_df(None)
    assert set(df.columns) == {"metric", "value"}


def test_export_bytes():
    assert opportunity_csv_bytes(_result())
    assert opportunity_markdown_bytes(_result()).startswith(b"# Opportunity Index Report")
