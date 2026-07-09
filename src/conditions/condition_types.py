"""Types for V1.6.3 condition engine."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CT = {
    "entry": "entry condition",
    "add_position": "add-position condition",
    "reduce": "reduce condition",
    "exit": "exit condition",
    "cancel_watch": "cancel-watch condition",
    "invalidation": "invalidation condition",
    "risk": "risk condition",
    "observation": "observation condition",
}

CS = {
    "satisfied": "satisfied",
    "not_satisfied": "not satisfied",
    "partial": "partial",
    "unknown": "unknown",
    "blocked": "blocked",
    "insufficient": "insufficient data",
}

AP_CN = {
    "allow_observe": "allow observe",
    "allow_focus": "allow focus observe",
    "wait_entry": "wait for entry setup",
    "small_trial": "conditional small trial",
    "forbid_chase": "forbid chasing",
    "forbid_add": "forbid add",
    "reduce": "reduce condition active",
    "exit": "exit condition active",
    "cancel": "cancel watch",
    "unknown": "unknown",
}


@dataclass
class ConditionItem:
    ctype: str = ""
    name: str = ""
    status: str = "unknown"
    severity: str = "medium"
    reason: str = ""
    blocking: bool = False
    priority: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConditionSet:
    trade_date: str = ""
    sector_name: str = ""
    stock_code: str = ""
    opportunity_score: float = 0.0
    entry: list[ConditionItem] = field(default_factory=list)
    add_position: list[ConditionItem] = field(default_factory=list)
    reduce: list[ConditionItem] = field(default_factory=list)
    exit: list[ConditionItem] = field(default_factory=list)
    cancel_watch: list[ConditionItem] = field(default_factory=list)
    invalidation: list[ConditionItem] = field(default_factory=list)
    risk: list[ConditionItem] = field(default_factory=list)
    observation: list[ConditionItem] = field(default_factory=list)
    permission: str = "unknown"
    permission_reason: str = ""
    risk_warnings: list[str] = field(default_factory=list)
    version: str = "v1.6.3"

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date,
            "sector_name": self.sector_name,
            "stock_code": self.stock_code,
            "opportunity_score": self.opportunity_score,
            "entry_conditions": [c.as_dict() for c in self.entry],
            "add_position_conditions": [c.as_dict() for c in self.add_position],
            "reduce_conditions": [c.as_dict() for c in self.reduce],
            "exit_conditions": [c.as_dict() for c in self.exit],
            "cancel_watch_conditions": [c.as_dict() for c in self.cancel_watch],
            "invalidation_conditions": [c.as_dict() for c in self.invalidation],
            "risk_conditions": [c.as_dict() for c in self.risk],
            "observation_conditions": [c.as_dict() for c in self.observation],
            "permission": self.permission,
            "permission_reason": self.permission_reason,
            "permission_summary": {
                "permission": self.permission,
                "reason": self.permission_reason,
            },
            "risk_warnings": self.risk_warnings,
            "version": self.version,
        }
