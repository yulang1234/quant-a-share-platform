"""Types for V1.6.2 opportunity index."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

LEVELS = ("very_high", "high", "medium", "low", "avoid", "unknown")
LEVEL_CN = {
    "very_high": "very high",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "avoid": "avoid",
    "unknown": "unknown",
}

ACTIONS = (
    "observe",
    "focus_observe",
    "wait_for_entry",
    "small_trial",
    "forbid_chasing",
    "cancel_watch",
    "unknown",
)
ACTION_CN = {
    "observe": "observe",
    "focus_observe": "focus observe",
    "wait_for_entry": "wait for entry setup",
    "small_trial": "conditional small trial",
    "forbid_chasing": "forbid chasing",
    "cancel_watch": "cancel watch",
    "unknown": "unknown",
}


@dataclass
class OpportunityResult:
    trade_date: str
    sector_name: str
    stock_code: str = ""
    stock_name: str = ""
    opportunity_score: float = 0.0
    opportunity_level: str = "unknown"
    action_signal: str = "unknown"
    market_safety_score: float = 0.0
    sentiment_safety_score: float = 0.0
    sector_mainline_score: float = 0.0
    leader_certainty_score: float = 0.0
    entry_odds_score: float = 0.0
    risk_discount: float = 1.0
    reason: str = ""
    risk_warnings: list[str] = field(default_factory=list)
    observation_conditions: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)
    version: str = "v1.6.2"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
