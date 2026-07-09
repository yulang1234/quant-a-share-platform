"""Markdown report helpers for V1.6.2 opportunity index."""
from __future__ import annotations

from src.opportunity.opportunity_types import OpportunityResult


def build_opportunity_markdown(result: OpportunityResult | dict) -> str:
    data = result.as_dict() if hasattr(result, "as_dict") else dict(result)
    lines = [
        "# Opportunity Index Report",
        "",
        f"- trade_date: {data.get('trade_date', '')}",
        f"- sector_name: {data.get('sector_name', '')}",
        f"- stock_code: {data.get('stock_code', '')}",
        f"- opportunity_score: {data.get('opportunity_score', 0)}",
        f"- opportunity_level: {data.get('opportunity_level', 'unknown')}",
        f"- action_signal: {data.get('action_signal', 'unknown')}",
        "",
        "## Scores",
        f"- market_safety_score: {data.get('market_safety_score', 0)}",
        f"- sentiment_safety_score: {data.get('sentiment_safety_score', 0)}",
        f"- sector_mainline_score: {data.get('sector_mainline_score', 0)}",
        f"- leader_certainty_score: {data.get('leader_certainty_score', 0)}",
        f"- entry_odds_score: {data.get('entry_odds_score', 0)}",
        f"- risk_discount: {data.get('risk_discount', 1)}",
        "",
        "## Risk Notice",
        "- Research aid only. Not investment advice. No order execution.",
    ]
    for title, key in (
        ("Observation Conditions", "observation_conditions"),
        ("Invalidation Conditions", "invalidation_conditions"),
        ("Risk Warnings", "risk_warnings"),
    ):
        items = data.get(key) or []
        if items:
            lines.extend(["", f"## {title}", *[f"- {item}" for item in items]])
    return "\n".join(lines) + "\n"
