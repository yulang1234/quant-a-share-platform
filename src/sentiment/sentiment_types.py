"""V1.5.2 sentiment cycle types — dataclass and enumerations.

Mirrors the V1.5.1 ``src.market.market_types`` pattern: stable string tokens
and a structured dataclass that downstream consumers can depend on.

All tokens are plain strings so they serialise cleanly into JSON /
Markdown / Streamlit without extra dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ── Sentiment cycle tokens ────────────────────────────────────────────────────

SENTIMENT_ICE_POINT = "ice_point"
SENTIMENT_REPAIR = "repair"
SENTIMENT_WARMING = "warming"
SENTIMENT_CLIMAX = "climax"
SENTIMENT_COOLING = "cooling"
SENTIMENT_RETREAT = "retreat"
SENTIMENT_CHAOTIC = "chaotic"
SENTIMENT_UNKNOWN = "unknown"

SENTIMENT_CYCLES: tuple[str, ...] = (
    SENTIMENT_ICE_POINT,
    SENTIMENT_REPAIR,
    SENTIMENT_WARMING,
    SENTIMENT_CLIMAX,
    SENTIMENT_COOLING,
    SENTIMENT_RETREAT,
    SENTIMENT_CHAOTIC,
    SENTIMENT_UNKNOWN,
)

# ── Risk level tokens (reuse from market, but local to avoid cross-dependency) ─

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_EXTREME = "extreme"
RISK_UNKNOWN = "unknown"

RISK_LEVELS: tuple[str, ...] = (
    RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_EXTREME, RISK_UNKNOWN,
)


@dataclass
class SentimentCycle:
    """V1.5.2 structured sentiment cycle judgment.

    All fields are stable — downstream consumers (decision card, CLI, UI)
    can depend on every key being present.

    ``indicators`` is a flat dict of computed sentiment metrics.
    ``reasons`` is a human-readable list explaining *why* the judgment.
    """

    trade_date: str | None
    sentiment_cycle: str               # one of SENTIMENT_CYCLES
    sentiment_score: int               # 0-100
    risk_level: str                    # one of RISK_LEVELS
    can_try_position: bool
    can_attack: bool
    relay_risk_level: str              # one of RISK_LEVELS
    chase_high_allowed: bool
    action_hint: str                   # short Chinese advice for end users
    indicators: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    missing_indicator_names: list[str] = field(default_factory=list)
    version: str = "v1.5.2"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> list[str]:
        """Return a list of validation issues (empty = valid)."""
        issues: list[str] = []
        if self.sentiment_cycle not in SENTIMENT_CYCLES:
            issues.append(f"invalid sentiment_cycle: {self.sentiment_cycle!r}")
        if self.risk_level not in RISK_LEVELS:
            issues.append(f"invalid risk_level: {self.risk_level!r}")
        if self.relay_risk_level not in RISK_LEVELS:
            issues.append(f"invalid relay_risk_level: {self.relay_risk_level!r}")
        if not (0 <= self.sentiment_score <= 100):
            issues.append(
                f"sentiment_score out of range [0,100]: {self.sentiment_score}"
            )
        return issues


# ── Pre-built unknown snapshot ────────────────────────────────────────────────


def _make_unknown(trade_date: str | None = None) -> SentimentCycle:
    """Return a safe 'unknown' snapshot for graceful degradation."""
    return SentimentCycle(
        trade_date=trade_date,
        sentiment_cycle=SENTIMENT_UNKNOWN,
        sentiment_score=0,
        risk_level=RISK_UNKNOWN,
        can_try_position=False,
        can_attack=False,
        relay_risk_level=RISK_UNKNOWN,
        chase_high_allowed=False,
        action_hint="数据不足，暂不建议对情绪周期做明确判断。",
        indicators={},
        reasons=["数据不足以支撑情绪周期判断"],
        missing_indicator_names=[],
        version="v1.5.2",
    )


UNKNOWN_SENTIMENT_CYCLE = _make_unknown()
