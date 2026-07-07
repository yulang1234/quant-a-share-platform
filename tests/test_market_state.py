from __future__ import annotations


def test_market_snapshot_unknown_by_default(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.market.market_state.build_quality_overview",
        lambda: {"overall_status": "unknown", "top_issues": []},
    )
    from src.market.market_state import build_market_snapshot

    snap = build_market_snapshot("2026-07-07")
    assert snap.market_state == "unknown"
    assert snap.can_open_position == "unknown"
    assert snap.can_add_position == "unknown"
    assert snap.chase_high_allowed == "unknown"
    assert "追高" not in snap.action_hint or "避免追高" in snap.action_hint


def test_bad_quality_blocks_strong(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.market.market_state.build_quality_overview",
        lambda: {"overall_status": "risky", "top_issues": ["质量风险"]},
    )
    from src.market.market_state import build_market_snapshot

    snap = build_market_snapshot("2026-07-07")
    assert snap.market_state != "strong"
    assert snap.risk_level == "high"
    assert snap.chase_high_allowed == "unknown"
