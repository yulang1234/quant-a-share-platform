"""V1.6.1 sector leader identification tests."""
from __future__ import annotations

from src.leader.leader_types import LeaderCandidate
from src.leader.sector_leader import _classify_leaders, identify_sector_leaders


def _candidate(code: str, score: float, pct_5d: float = 5, continuity: float = 80, startup: float = 65):
    return LeaderCandidate(
        stock_code=code,
        stock_name=code,
        leader_score=score,
        pct_chg_5d=pct_5d,
        continuity_score=continuity,
        startup_score=startup,
    )


def test_classifies_leader_1_and_leader_2():
    result = _classify_leaders([_candidate("000001", 80), _candidate("000002", 70)], "2026-07-09", "demo")
    assert result.leader_1.stock_code == "000001"
    assert result.leader_2.stock_code == "000002"


def test_classifies_high_risk_chasing():
    result = _classify_leaders([_candidate("000001", 80, pct_5d=20)], "2026-07-09", "demo")
    assert result.high_risk_chasing


def test_classifies_pseudo_leader():
    result = _classify_leaders([_candidate("000001", 55, pct_5d=8, continuity=10)], "2026-07-09", "demo")
    assert result.pseudo_leaders


def test_insufficient_data_degrades_gracefully():
    result = identify_sector_leaders("2026-07-09", "missing-sector")
    assert result.sector_status == "unknown"
    assert result.issue_summary
