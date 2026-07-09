"""V1.6.3 condition report tests."""
from __future__ import annotations

from src.conditions.condition_engine import build_condition_set
from src.conditions.condition_report import build_condition_markdown


def test_build_condition_markdown():
    condition_set = build_condition_set(
        {"market_state": "attack"},
        {"sentiment_cycle": "warming"},
        {"mainline_status": "confirmed_mainline"},
        {"leader_type": "leader_1"},
        {"opportunity_score": 80},
    )
    markdown = build_condition_markdown(condition_set)
    assert "Condition Engine Report" in markdown
    assert "No automatic execution" in markdown
