"""V1.5.6 sector diagnosis types — structured diagnosis report."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ── Diagnosis status tokens ─────────────────────────────────────────────────

DIAG_HEALTHY = "healthy"
DIAG_WATCH = "watch"
DIAG_WAIT = "wait"
DIAG_CAUTIOUS = "cautious"
DIAG_HIGH_RISK = "high_risk"
DIAG_COOLING = "cooling"
DIAG_AVOID = "avoid"
DIAG_UNKNOWN = "unknown"

DIAGNOSIS_STATUSES: tuple[str, ...] = (
    DIAG_HEALTHY, DIAG_WATCH, DIAG_WAIT, DIAG_CAUTIOUS,
    DIAG_HIGH_RISK, DIAG_COOLING, DIAG_AVOID, DIAG_UNKNOWN,
)

# ── Fit tokens ──────────────────────────────────────────────────────────────

FIT_GOOD = "good"
FIT_NEUTRAL = "neutral"
FIT_POOR = "poor"
FIT_UNKNOWN = "unknown"

FIT_LEVELS: tuple[str, ...] = (FIT_GOOD, FIT_NEUTRAL, FIT_POOR, FIT_UNKNOWN)

# ── Trend stage tokens ──────────────────────────────────────────────────────

TREND_EMERGING = "emerging"
TREND_STRENGTHENING = "strengthening"
TREND_STRONG = "strong_trend"
TREND_OVERHEAT = "overheat"
TREND_COOLING = "cooling"
TREND_WEAKENING = "weakening"
TREND_UNKNOWN = "unknown"

TREND_STAGES: tuple[str, ...] = (
    TREND_EMERGING, TREND_STRENGTHENING, TREND_STRONG,
    TREND_OVERHEAT, TREND_COOLING, TREND_WEAKENING, TREND_UNKNOWN,
)

# ── Leader structure tokens (placeholder for V1.6.1) ────────────────────────

LEADER_PENDING = "pending_v1.6.1"
LEADER_NOT_AVAILABLE = "not_available"
LEADER_INSUFFICIENT = "insufficient_data"
LEADER_ROUGH = "rough_structure_only"

LEADER_STRUCTURES: tuple[str, ...] = (
    LEADER_PENDING, LEADER_NOT_AVAILABLE, LEADER_INSUFFICIENT, LEADER_ROUGH,
)

# ── Buy point odds tokens ───────────────────────────────────────────────────

ODDS_GOOD = "good"
ODDS_NORMAL = "normal"
ODDS_POOR = "poor"
ODDS_HIGH_RISK = "high_risk"
ODDS_UNKNOWN = "unknown"

ODDS_LEVELS: tuple[str, ...] = (ODDS_GOOD, ODDS_NORMAL, ODDS_POOR, ODDS_HIGH_RISK, ODDS_UNKNOWN)

# ── Suggested action tokens ─────────────────────────────────────────────────

ACTION_OBSERVE = "observe"
ACTION_FOCUS_WATCH = "focus_watch"
ACTION_WAIT_PULLBACK = "wait_pullback"
ACTION_CAUTIOUS_WATCH = "cautious_watch"
ACTION_AVOID_CHASE = "avoid_chase_high"
ACTION_CANCEL_WATCH = "cancel_watch"
ACTION_UNKNOWN = "unknown"

SUGGESTED_ACTIONS: tuple[str, ...] = (
    ACTION_OBSERVE, ACTION_FOCUS_WATCH, ACTION_WAIT_PULLBACK,
    ACTION_CAUTIOUS_WATCH, ACTION_AVOID_CHASE, ACTION_CANCEL_WATCH, ACTION_UNKNOWN,
)


@dataclass
class SectorDiagnosis:
    """V1.5.6 structured sector diagnosis report."""

    trade_date: str
    sector_code: str
    sector_name: str
    sector_type: str

    # Core status
    diagnosis_status: str = DIAG_UNKNOWN

    # V1.5.5 mainline
    mainline_status: str = "unknown"
    mainline_score: int = 0
    mainline_probability: int = 0

    # V1.5.1 / V1.5.2 fit
    market_fit: str = FIT_UNKNOWN
    sentiment_fit: str = FIT_UNKNOWN

    # V1.5.4 strength
    strength_score: int = 0
    strength_level: str = "unknown"
    strength_rank: dict[str, Any] = field(default_factory=dict)

    # Trend
    trend_stage: str = TREND_UNKNOWN

    # Leader (placeholder)
    leader_structure: str = LEADER_PENDING

    # Odds & risk
    buy_point_odds: str = ODDS_UNKNOWN
    risk_level: str = "unknown"

    # Actions
    suggested_action: str = ACTION_UNKNOWN
    action_hint: str = ""
    observation_conditions: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)

    # Meta
    risk_flags: list[str] = field(default_factory=list)
    missing_indicator_names: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    version: str = "v1.5.6"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
