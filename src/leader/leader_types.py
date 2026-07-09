"""Types for V1.6.1 sector leader identification."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

LEADER_1 = "leader_1"
LEADER_2 = "leader_2"
MAKE_UP = "make_up_candidate"
PSEUDO = "pseudo_leader"
HIGH_RISK = "high_risk_chasing"
NORMAL = "normal"
UNKNOWN = "unknown"

LEADER_TYPES: tuple[str, ...] = (
    LEADER_1,
    LEADER_2,
    MAKE_UP,
    PSEUDO,
    HIGH_RISK,
    NORMAL,
    UNKNOWN,
)

LEADER_CN = {
    LEADER_1: "No.1 leader",
    LEADER_2: "No.2 leader",
    MAKE_UP: "catch-up candidate",
    PSEUDO: "pseudo leader",
    HIGH_RISK: "high-risk chasing",
    NORMAL: "normal",
    UNKNOWN: "unknown",
}


@dataclass
class LeaderCandidate:
    stock_code: str
    stock_name: str
    leader_type: str = UNKNOWN
    leader_score: float = 0.0
    relative_strength_score: float = 0.0
    turnover_score: float = 0.0
    price_rank_score: float = 0.0
    resilience_score: float = 0.0
    startup_score: float = 0.0
    trend_structure_score: float = 0.0
    continuity_score: float = 0.0
    pct_chg_5d: float = 0.0
    pct_chg_10d: float = 0.0
    turnover_amount: float = 0.0
    turnover_rank: int = 0
    trend_structure: str = ""
    risk_flags: list[str] = field(default_factory=list)
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SectorLeaderResult:
    trade_date: str
    sector_name: str
    sector_code: str = ""
    sector_status: str = UNKNOWN
    leader_1: LeaderCandidate | None = None
    leader_2: LeaderCandidate | None = None
    make_up_candidates: list[LeaderCandidate] = field(default_factory=list)
    pseudo_leaders: list[LeaderCandidate] = field(default_factory=list)
    high_risk_chasing: list[LeaderCandidate] = field(default_factory=list)
    all_candidates: list[LeaderCandidate] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)
    issue_summary: list[str] = field(default_factory=list)
    generated_at: str = ""
    version: str = "v1.6.1"

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date,
            "sector_name": self.sector_name,
            "sector_code": self.sector_code,
            "sector_status": self.sector_status,
            "leader_1": self.leader_1.as_dict() if self.leader_1 else None,
            "leader_2": self.leader_2.as_dict() if self.leader_2 else None,
            "make_up_candidates": [c.as_dict() for c in self.make_up_candidates],
            "pseudo_leaders": [c.as_dict() for c in self.pseudo_leaders],
            "high_risk_chasing": [c.as_dict() for c in self.high_risk_chasing],
            "all_candidates": [c.as_dict() for c in self.all_candidates],
            "risk_warnings": self.risk_warnings,
            "issue_summary": self.issue_summary,
            "generated_at": self.generated_at,
            "version": self.version,
        }
