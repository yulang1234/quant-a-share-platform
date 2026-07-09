"""V1.6.1 leader report tests."""
from __future__ import annotations

from src.leader.leader_report import build_leader_markdown
from src.leader.leader_types import LeaderCandidate, SectorLeaderResult


def test_build_leader_markdown():
    result = SectorLeaderResult(
        trade_date="2026-07-09",
        sector_name="demo",
        leader_1=LeaderCandidate("000001", "demo stock", leader_score=80),
    )
    markdown = build_leader_markdown(result)
    assert "Sector Leader Report" in markdown
    assert "No order execution" in markdown
