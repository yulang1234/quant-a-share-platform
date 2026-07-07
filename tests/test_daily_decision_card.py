from __future__ import annotations


def test_daily_decision_card_generates_unknown(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.market.market_state.build_quality_overview",
        lambda: {"overall_status": "unknown", "top_issues": []},
    )
    monkeypatch.setattr(
        "src.sentiment.sentiment_cycle.build_quality_overview",
        lambda: {"overall_status": "unknown", "top_issues": []},
    )
    monkeypatch.setattr(
        "src.sector.sector_snapshot.build_quality_overview",
        lambda: {"overall_status": "unknown", "top_issues": []},
    )
    from src.decision.daily_decision_card import build_daily_decision_card

    card = build_daily_decision_card("2026-07-07")
    data = card.as_dict()
    assert data["generated_at"]
    assert data["market_state"] in ("unknown", "weak")
    assert data["sentiment_cycle"] == "unknown"
    assert isinstance(data["strong_sectors"], list)
    assert data["overall_bias"] != "aggressive"
