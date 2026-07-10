"""Types for V1.7.2 daily position diagnosis.

Defines enums, dataclasses and presentation helpers.
No database or network I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


# ── Enums ────────────────────────────────────────────────────────────────────


class DiagnosisStatus(str, Enum):
    HEALTHY = "healthy"
    WATCH = "watch"
    CAUTIOUS = "cautious"
    DANGEROUS = "dangerous"
    UNKNOWN = "unknown"


class SuggestedAction(str, Enum):
    CONTINUE_HOLD = "continue_hold"
    LIGHT_HOLD = "light_hold"
    FORBID_ADD = "forbid_add"
    ALLOW_ADD_CONDITIONALLY = "allow_add_conditionally"
    REDUCE_CONDITIONALLY = "reduce_conditionally"
    EXIT_CONDITIONALLY = "exit_conditionally"
    CANCEL_WATCH = "cancel_watch"
    UNKNOWN = "unknown"


class ThesisStatus(str, Enum):
    VALID = "valid"
    WEAKENING = "weakening"
    INVALID = "invalid"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    UNKNOWN = "unknown"


class PositionSizeStatus(str, Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    UNKNOWN = "unknown"


DIAGNOSIS_STATUS_CN: dict[str, str] = {
    "healthy": "健康",
    "watch": "关注",
    "cautious": "谨慎",
    "dangerous": "危险",
    "unknown": "暂无判断",
}

SUGGESTED_ACTION_CN: dict[str, str] = {
    "continue_hold": "继续持有",
    "light_hold": "轻仓持有",
    "forbid_add": "禁止加仓",
    "allow_add_conditionally": "条件允许加仓",
    "reduce_conditionally": "触发减仓条件",
    "exit_conditionally": "触发清仓条件",
    "cancel_watch": "取消关注",
    "unknown": "暂无判断",
}

THESIS_STATUS_CN: dict[str, str] = {
    "valid": "有效",
    "weakening": "弱化",
    "invalid": "失效",
    "manual_review_required": "需人工复核",
    "unknown": "暂无判断",
}

POSITION_SIZE_CN: dict[str, str] = {
    "normal": "正常",
    "elevated": "偏高",
    "high": "过重",
    "unknown": "未知",
}


# ── Component types ──────────────────────────────────────────────────────────


@dataclass
class DiagnosisComponent:
    """A single scored diagnostic dimension."""

    name: str = ""
    score: float = 0.0
    status: str = "unknown"
    weight: float = 0.0
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Result type ──────────────────────────────────────────────────────────────


@dataclass
class PositionDiagnosisResult:
    """Complete diagnosis result for one position on one trade_date."""

    position_id: int = 0
    trade_date: str = ""
    portfolio_name: str = ""
    stock_code: str = ""
    stock_name: str = ""
    sector_name: str = ""

    diagnosis_status: str = "unknown"
    suggested_action: str = "unknown"
    thesis_status: str = "unknown"
    health_score: float = 0.0
    data_coverage_ratio: float = 0.0

    market_support_score: float = 0.0
    sentiment_support_score: float = 0.0
    sector_support_score: float = 0.0
    leader_support_score: float = 0.0
    trend_health_score: float = 0.0
    condition_support_score: float = 0.0
    thesis_score: float = 0.0

    market_component: DiagnosisComponent | None = None
    sentiment_component: DiagnosisComponent | None = None
    sector_component: DiagnosisComponent | None = None
    leader_component: DiagnosisComponent | None = None
    trend_component: DiagnosisComponent | None = None
    condition_component: DiagnosisComponent | None = None
    thesis_component: DiagnosisComponent | None = None

    latest_close: float | None = None
    unrealized_return_pct: float | None = None
    drawdown_20d: float | None = None
    position_pct: float | None = None
    position_size_status: str = "unknown"

    risk_warnings: list[str] = field(default_factory=list)
    observation_conditions: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    data_quality_status: str = "unknown"
    issue_summary: list[str] = field(default_factory=list)
    rule_version: str = "v1.7.2"
    generated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "position_id": self.position_id,
            "trade_date": self.trade_date,
            "portfolio_name": self.portfolio_name,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "sector_name": self.sector_name,
            "diagnosis_status": self.diagnosis_status,
            "suggested_action": self.suggested_action,
            "thesis_status": self.thesis_status,
            "health_score": self.health_score,
            "data_coverage_ratio": self.data_coverage_ratio,
            "market_support_score": self.market_support_score,
            "sentiment_support_score": self.sentiment_support_score,
            "sector_support_score": self.sector_support_score,
            "leader_support_score": self.leader_support_score,
            "trend_health_score": self.trend_health_score,
            "condition_support_score": self.condition_support_score,
            "thesis_score": self.thesis_score,
            "latest_close": self.latest_close,
            "unrealized_return_pct": self.unrealized_return_pct,
            "drawdown_20d": self.drawdown_20d,
            "position_pct": self.position_pct,
            "position_size_status": self.position_size_status,
            "risk_warnings": self.risk_warnings,
            "observation_conditions": self.observation_conditions,
            "invalidation_conditions": self.invalidation_conditions,
            "evidence": self.evidence,
            "data_quality_status": self.data_quality_status,
            "issue_summary": self.issue_summary,
            "rule_version": self.rule_version,
            "generated_at": self.generated_at,
        }
        for key in (
            "market_component", "sentiment_component", "sector_component",
            "leader_component", "trend_component", "condition_component",
            "thesis_component",
        ):
            comp = getattr(self, key, None)
            d[key] = comp.as_dict() if comp else None
        return d


# ── Helper ───────────────────────────────────────────────────────────────────


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to float safely, returning default on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
