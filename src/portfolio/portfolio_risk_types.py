"""Types for V1.7.3 portfolio-level risk control.

Risk scores are 0-100 where higher = more risk. No trading execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class PortfolioRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class PortfolioPermission(str, Enum):
    NORMAL = "normal"
    WATCH = "watch"
    FREEZE_NEW_POSITIONS = "freeze_new_positions"
    FREEZE_ADDITIONS = "freeze_additions"
    REDUCE_EXPOSURE_CONDITIONALLY = "reduce_exposure_conditionally"
    MANUAL_REVIEW = "manual_review"
    UNKNOWN = "unknown"


RISK_LEVEL_CN: dict[str, str] = {
    "low": "低风险", "medium": "中等风险", "high": "高风险",
    "critical": "严重风险", "unknown": "暂无判断",
}

PERMISSION_CN: dict[str, str] = {
    "normal": "正常", "watch": "观察", "freeze_new_positions": "暂停新增持仓",
    "freeze_additions": "暂停扩大仓位", "reduce_exposure_conditionally": "建议降低风险暴露",
    "manual_review": "需人工复核", "unknown": "暂无判断",
}


@dataclass
class RiskDimension:
    name: str = ""
    risk_score: float = 0.0
    risk_level: str = "unknown"
    weight: float = 0.0
    current_value: str = ""
    threshold: str = ""
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SectorExposure:
    sector_name: str
    position_count: int
    total_position_pct: float
    concentration_level: str


@dataclass
class CorrelationPair:
    stock_a: str
    stock_b: str
    correlation: float
    shared_sectors: list[str] = field(default_factory=list)
    risk_level: str = ""


@dataclass
class PortfolioRiskResult:
    trade_date: str = ""
    portfolio_name: str = "default"
    is_simulated: bool = True
    portfolio_risk_score: float = 0.0
    portfolio_risk_level: str = "unknown"
    portfolio_permission: str = "unknown"

    position_count: int = 0
    sector_count: int = 0
    total_position_pct: float = 0.0
    cash_pct: float | None = None
    max_single_position_pct: float = 0.0
    max_single_position_code: str = ""
    max_sector_position_pct: float = 0.0
    max_sector_name: str = ""
    top3_position_pct: float = 0.0
    crowded_sector_count: int = 0
    high_correlation_pair_count: int = 0
    average_pairwise_correlation: float | None = None
    max_pairwise_correlation: float | None = None
    portfolio_drawdown_20d: float | None = None
    portfolio_drawdown_60d: float | None = None
    consecutive_loss_days: int = 0
    dangerous_position_count: int = 0
    cautious_position_count: int = 0
    unknown_position_count: int = 0
    market_state: str = "unknown"
    sentiment_cycle: str = "unknown"

    risk_dimensions: list[RiskDimension] = field(default_factory=list)
    sector_exposures: list[SectorExposure] = field(default_factory=list)
    correlation_pairs: list[CorrelationPair] = field(default_factory=list)

    data_coverage_ratio: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    observation_conditions: list[str] = field(default_factory=list)
    risk_release_conditions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    issue_summary: list[str] = field(default_factory=list)
    data_quality_status: str = "unknown"
    rule_version: str = "v1.7.3"
    generated_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "trade_date": self.trade_date,
            "portfolio_name": self.portfolio_name,
            "is_simulated": self.is_simulated,
            "portfolio_risk_score": self.portfolio_risk_score,
            "portfolio_risk_level": self.portfolio_risk_level,
            "portfolio_permission": self.portfolio_permission,
            "position_count": self.position_count,
            "sector_count": self.sector_count,
            "total_position_pct": self.total_position_pct,
            "cash_pct": self.cash_pct,
            "max_single_position_pct": self.max_single_position_pct,
            "max_single_position_code": self.max_single_position_code,
            "max_sector_position_pct": self.max_sector_position_pct,
            "max_sector_name": self.max_sector_name,
            "top3_position_pct": self.top3_position_pct,
            "crowded_sector_count": self.crowded_sector_count,
            "high_correlation_pair_count": self.high_correlation_pair_count,
            "average_pairwise_correlation": self.average_pairwise_correlation,
            "max_pairwise_correlation": self.max_pairwise_correlation,
            "portfolio_drawdown_20d": self.portfolio_drawdown_20d,
            "portfolio_drawdown_60d": self.portfolio_drawdown_60d,
            "consecutive_loss_days": self.consecutive_loss_days,
            "dangerous_position_count": self.dangerous_position_count,
            "cautious_position_count": self.cautious_position_count,
            "unknown_position_count": self.unknown_position_count,
            "market_state": self.market_state,
            "sentiment_cycle": self.sentiment_cycle,
            "risk_dimensions": [rd.as_dict() for rd in self.risk_dimensions],
            "sector_exposures": [asdict(se) for se in self.sector_exposures],
            "correlation_pairs": [asdict(cp) for cp in self.correlation_pairs],
            "data_coverage_ratio": self.data_coverage_ratio,
            "risk_flags": self.risk_flags,
            "recommendations": self.recommendations,
            "observation_conditions": self.observation_conditions,
            "risk_release_conditions": self.risk_release_conditions,
            "evidence": self.evidence,
            "issue_summary": self.issue_summary,
            "data_quality_status": self.data_quality_status,
            "rule_version": self.rule_version,
            "generated_at": self.generated_at,
        }
        return d


def clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, float(value or 0))), 1)
