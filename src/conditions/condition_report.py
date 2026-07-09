"""Markdown report helpers for V1.6.3 condition engine."""
from __future__ import annotations

from src.conditions.condition_types import ConditionSet


def build_condition_markdown(condition_set: ConditionSet | dict) -> str:
    data = condition_set.as_dict() if hasattr(condition_set, "as_dict") else dict(condition_set)
    lines = [
        "# Condition Engine Report",
        "",
        f"- trade_date: {data.get('trade_date', '')}",
        f"- sector_name: {data.get('sector_name', '')}",
        f"- stock_code: {data.get('stock_code', '')}",
        f"- permission: {data.get('permission', 'unknown')}",
        f"- permission_reason: {data.get('permission_reason', '')}",
        "",
        "## Risk Notice",
        "- Research aid only. No automatic execution. Not investment advice.",
    ]
    for title, key in (
        ("Entry Conditions", "entry_conditions"),
        ("Add Conditions", "add_position_conditions"),
        ("Reduce Conditions", "reduce_conditions"),
        ("Exit Conditions", "exit_conditions"),
        ("Cancel Watch Conditions", "cancel_watch_conditions"),
        ("Invalidation Conditions", "invalidation_conditions"),
        ("Risk Conditions", "risk_conditions"),
        ("Observation Conditions", "observation_conditions"),
    ):
        items = data.get(key) or []
        lines.extend(["", f"## {title}"])
        if not items:
            lines.append("- none")
        else:
            lines.extend([f"- {item.get('name', '')}: {item.get('status', '')}" for item in items])
    return "\n".join(lines) + "\n"
