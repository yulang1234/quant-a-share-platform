"""V1.5.5 sector mainline types — dataclasses for mainline identification."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ── Mainline status tokens ──────────────────────────────────────────────────

MAINLINE_CONFIRMED = "confirmed_mainline"
MAINLINE_POTENTIAL = "potential_mainline"
MAINLINE_ONE_DAY = "one_day_theme"
MAINLINE_COOLING = "cooling_sector"
MAINLINE_HIGH_RISK = "high_risk_sector"
MAINLINE_NEUTRAL = "neutral"
MAINLINE_UNKNOWN = "unknown"

MAINLINE_STATUSES: tuple[str, ...] = (
    MAINLINE_CONFIRMED, MAINLINE_POTENTIAL, MAINLINE_ONE_DAY,
    MAINLINE_COOLING, MAINLINE_HIGH_RISK, MAINLINE_NEUTRAL, MAINLINE_UNKNOWN,
)

# ── Confidence tokens ───────────────────────────────────────────────────────

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

CONFIDENCE_LEVELS: tuple[str, ...] = (CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW)

# ── Risk flag tokens ────────────────────────────────────────────────────────

RISK_OVERHEAT = "overheat"
RISK_ONE_DAY_SPIKE = "one_day_spike"
RISK_RANK_DROP = "rank_drop"
RISK_TURNOVER_ABNORMAL = "turnover_abnormal"
RISK_BREADTH_WEAK = "breadth_weak"
RISK_BIG_LOSS_RISING = "big_loss_rising"
RISK_DATA_INSUFFICIENT = "data_insufficient"
RISK_PERSISTENCE_INSUFFICIENT = "persistence_insufficient"

RISK_FLAGS: tuple[str, ...] = (
    RISK_OVERHEAT, RISK_ONE_DAY_SPIKE, RISK_RANK_DROP,
    RISK_TURNOVER_ABNORMAL, RISK_BREADTH_WEAK,
    RISK_BIG_LOSS_RISING, RISK_DATA_INSUFFICIENT,
    RISK_PERSISTENCE_INSUFFICIENT,
)


@dataclass
class SectorMainlineResult:
    """Mainline identification result for a single sector."""

    trade_date: str
    sector_code: str
    sector_name: str
    sector_type: str

    mainline_status: str = MAINLINE_UNKNOWN
    mainline_score: int = 0
    confidence: str = CONFIDENCE_LOW

    # Key metrics
    rank_overall: int = 0
    strength_score: int = 0
    strength_level: str = "unknown"
    persistence_days: int = 0
    rank_stability_score: int = 0
    relative_strength_score: int = 0
    turnover_confirmation: bool = False
    breadth_confirmation: bool = False
    limit_up_confirmation: bool = False

    risk_flags: list[str] = field(default_factory=list)
    missing_indicator_names: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    version: str = "v1.5.5"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MainlineSnapshot:
    """Daily mainline snapshot aggregating all sectors."""

    trade_date: str
    has_clear_mainline: bool = False
    confirmed_mainlines: list[dict[str, Any]] = field(default_factory=list)
    potential_mainlines: list[dict[str, Any]] = field(default_factory=list)
    one_day_themes: list[dict[str, Any]] = field(default_factory=list)
    cooling_sectors: list[dict[str, Any]] = field(default_factory=list)
    high_risk_sectors: list[dict[str, Any]] = field(default_factory=list)
    market_mainline_summary: str = ""
    version: str = "v1.5.5"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AllMainlineResult:
    """Result of identifying mainlines for all sectors."""

    trade_date: str
    results: list[SectorMainlineResult] = field(default_factory=list)
    sector_count: int = 0
    version: str = "v1.5.5"

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date,
            "results": [r.as_dict() for r in self.results],
            "sector_count": self.sector_count,
            "version": self.version,
        }
