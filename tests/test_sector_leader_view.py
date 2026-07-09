"""V1.6.1 sector leader view data helpers tests."""
from __future__ import annotations

from ui.components.sector_leader_view import candidates_to_df, leader_csv_bytes, leader_markdown_bytes


def _result():
    return {
        "trade_date": "2026-07-09",
        "sector_name": "demo",
        "all_candidates": [
            {
                "stock_code": "000001",
                "stock_name": "demo",
                "leader_type": "leader_1",
                "leader_score": 80,
                "relative_strength_score": 90,
                "turnover_score": 70,
                "price_rank_score": 60,
                "pct_chg_5d": 5,
                "risk_flags": [],
                "reason": "top score",
            }
        ],
    }


def test_candidates_to_df_handles_empty():
    assert candidates_to_df(None).empty


def test_candidates_to_df_exports_rows():
    df = candidates_to_df(_result())
    assert list(df["stock_code"]) == ["000001"]


def test_export_bytes():
    assert leader_csv_bytes(_result())
    assert leader_markdown_bytes(_result()).startswith(b"# Sector Leader Report")
