"""V1.5.4 sector strength types — dataclasses for strength results and rankings."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ── Strength level tokens ───────────────────────────────────────────────────

STRENGTH_VERY_STRONG = "very_strong"
STRENGTH_STRONG = "strong"
STRENGTH_NEUTRAL = "neutral"
STRENGTH_WEAK = "weak"
STRENGTH_VERY_WEAK = "very_weak"
STRENGTH_UNKNOWN = "unknown"

STRENGTH_LEVELS: tuple[str, ...] = (
    STRENGTH_VERY_STRONG, STRENGTH_STRONG, STRENGTH_NEUTRAL,
    STRENGTH_WEAK, STRENGTH_VERY_WEAK, STRENGTH_UNKNOWN,
)


@dataclass
class SectorStrengthResult:
    """Strength calculation result for a single sector on a given date."""

    trade_date: str
    sector_code: str
    sector_name: str
    sector_type: str
    source: str

    # Constituent stats
    stock_count: int = 0
    valid_stock_count: int = 0

    # Price indicators
    avg_pct_chg: float = 0.0
    median_pct_chg: float = 0.0

    # Multi-period returns
    return_3d: float | None = None
    return_5d: float | None = None
    return_10d: float | None = None
    return_20d: float | None = None

    # Relative strength vs benchmark
    relative_strength_3d: float | None = None
    relative_strength_5d: float | None = None
    relative_strength_10d: float | None = None
    relative_strength_20d: float | None = None

    # Turnover
    turnover_ratio_5d: float | None = None
    turnover_ratio_20d: float | None = None

    # Advance/decline
    up_count: int = 0
    down_count: int = 0
    flat_count: int = 0
    up_ratio: float = 0.0

    # Limit moves (approximate)
    limit_up_count: int = 0
    limit_down_count: int = 0
    big_gain_count: int = 0
    big_loss_count: int = 0

    # Scoring
    strength_score: int = 0
    strength_level: str = STRENGTH_UNKNOWN

    # Meta
    missing_indicator_names: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    version: str = "v1.5.4"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SectorStrengthRanking:
    """Ranked list of sectors by strength."""

    trade_date: str
    sector_type: str | None
    top_n: int
    sectors: list[dict[str, Any]] = field(default_factory=list)
    version: str = "v1.5.4"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AllSectorStrengthResult:
    """Result of calculating strength for all sectors."""

    trade_date: str
    results: list[SectorStrengthResult] = field(default_factory=list)
    sector_count: int = 0
    calculated_count: int = 0
    error_count: int = 0
    errors: list[str] = field(default_factory=list)
    version: str = "v1.5.4"

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date,
            "results": [r.as_dict() for r in self.results],
            "sector_count": self.sector_count,
            "calculated_count": self.calculated_count,
            "error_count": self.error_count,
            "errors": self.errors,
            "version": self.version,
        }
