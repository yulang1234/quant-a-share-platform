from __future__ import annotations


def test_sentiment_unknown_without_limit_data(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.sentiment.sentiment_cycle.build_quality_overview",
        lambda: {"overall_status": "unknown", "top_issues": []},
    )
    monkeypatch.setattr("src.sentiment.sentiment_cycle._has_limit_up_data", lambda: False)
    from src.sentiment.sentiment_cycle import build_sentiment_snapshot

    snap = build_sentiment_snapshot("2026-07-07")
    assert snap.sentiment_cycle == "unknown"
    assert snap.limit_up_count is None
    assert snap.limit_down_count is None
    assert "数据" in snap.risk_hint
