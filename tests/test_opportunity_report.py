"""V1.6.2 opportunity report tests."""
from __future__ import annotations

from src.opportunity.opportunity_report import build_opportunity_markdown
from src.opportunity.opportunity_types import OpportunityResult


def test_build_opportunity_markdown():
    result = OpportunityResult(
        trade_date="2026-07-09",
        sector_name="demo",
        opportunity_score=60,
        risk_discount=0.8,
        observation_conditions=["observe"],
        invalidation_conditions=["invalid"],
    )
    markdown = build_opportunity_markdown(result)
    assert "Opportunity Index Report" in markdown
    assert "No order execution" in markdown
