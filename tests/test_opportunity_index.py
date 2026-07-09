"""V1.6.2 opportunity index tests."""
from __future__ import annotations

from src.opportunity.opportunity_index import build_opportunity_index


def test_build_opportunity_index_degrades_without_data():
    result = build_opportunity_index("2026-07-09", "missing-sector")
    assert 0 <= result.opportunity_score <= 100
    assert 0 <= result.risk_discount <= 1
    assert result.observation_conditions
    assert result.invalidation_conditions
