"""Markdown report helpers for V1.6.1 leader identification."""
from __future__ import annotations

from src.leader.leader_types import SectorLeaderResult


def build_leader_markdown(result: SectorLeaderResult | dict) -> str:
    data = result.as_dict() if hasattr(result, "as_dict") else dict(result)
    lines = [
        "# Sector Leader Report",
        "",
        f"- trade_date: {data.get('trade_date', '')}",
        f"- sector_name: {data.get('sector_name', '')}",
        f"- version: {data.get('version', 'v1.6.1')}",
        "",
        "## Summary",
        f"- leader_1: {_name(data.get('leader_1'))}",
        f"- leader_2: {_name(data.get('leader_2'))}",
        f"- candidates: {len(data.get('all_candidates') or [])}",
        "",
        "## Risk Notice",
        "- Research aid only. Not investment advice. No order execution.",
    ]
    issues = data.get("issue_summary") or []
    if issues:
        lines.extend(["", "## Issues", *[f"- {item}" for item in issues]])
    return "\n".join(lines) + "\n"


def _name(item: dict | None) -> str:
    if not item:
        return "none"
    return f"{item.get('stock_code', '')} {item.get('stock_name', '')}".strip()
