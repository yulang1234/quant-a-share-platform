from __future__ import annotations


def test_view_helpers_no_crash(monkeypatch) -> None:
    monkeypatch.setattr(
        "ui.components.daily_decision_view.build_daily_decision_card",
        lambda trade_date=None: type("Card", (), {
            "as_dict": lambda self: {
                "trade_date": trade_date,
                "overall_bias": "defensive",
                "market_state": "unknown",
                "sentiment_cycle": "unknown",
                "risk_level": "unknown",
                "strong_sectors": [],
                "risk_warnings": [],
                "suggested_actions": ["数据不足，今日仅做观察"],
                "observation_conditions": [],
                "invalidation_conditions": [],
                "data_quality_status": "unknown",
                "generated_at": "2026-07-07T00:00:00",
                "issue_summary": [],
            }
        })(),
    )
    from ui.components.daily_decision_view import (
        load_daily_decision_card, overview_metrics, sectors_to_df,
        to_markdown_bytes, status_to_cn,
    )

    card = load_daily_decision_card("2026-07-07")
    metrics = overview_metrics(card)
    assert metrics["overall_bias_cn"] == "防守"
    assert sectors_to_df(card).empty
    assert to_markdown_bytes(card).startswith(b"\xef\xbb\xbf")
    assert status_to_cn(None) == "未知"
