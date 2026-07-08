"""V1.5.1 market environment types — dataclass and enumerations.

Replaces the V1.5.0 skeleton strings with structured, semantically-typed
constants that downstream rules and UI code can depend on.

All tokens are plain strings so they serialise cleanly into JSON /
Markdown / Streamlit without extra dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ── Market state tokens ───────────────────────────────────────────────────────
MARKET_ATTACK = "attack"
MARKET_NEUTRAL = "neutral"
MARKET_DEFENSE = "defense"
MARKET_HIGH_RISK = "high_risk"
MARKET_UNKNOWN = "unknown"

MARKET_STATES: tuple[str, ...] = (
    MARKET_ATTACK, MARKET_NEUTRAL, MARKET_DEFENSE,
    MARKET_HIGH_RISK, MARKET_UNKNOWN,
)

# ── Risk level tokens ─────────────────────────────────────────────────────────
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_EXTREME = "extreme"
RISK_UNKNOWN = "unknown"

RISK_LEVELS: tuple[str, ...] = (
    RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_EXTREME, RISK_UNKNOWN,
)


@dataclass
class MarketEnvironment:
    """V1.5.1 structured market environment judgment.

    All fields are stable — downstream consumers (decision card renderer,
    CLI, UI) can depend on every key being present.

    ``indicators`` is a flat dict of computed market-wide metrics (always
    numeric or null-safe). ``reasons`` is a human-readable list of bullet
    points explaining *why* the judgment was reached.
    """

    trade_date: str | None
    market_state: str              # one of MARKET_STATES
    risk_level: str                # one of RISK_LEVELS
    can_open_position: bool
    can_add_position: bool
    chase_high_allowed: bool
    action_hint: str               # short Chinese advice for end users
    indicators: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    version: str = "v1.5.1"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> list[str]:
        """Return a list of validation issues (empty = valid)."""
        issues: list[str] = []
        if self.market_state not in MARKET_STATES:
            issues.append(f"invalid market_state: {self.market_state!r}")
        if self.risk_level not in RISK_LEVELS:
            issues.append(f"invalid risk_level: {self.risk_level!r}")
        return issues


# ── Pre-built unknown snapshots ───────────────────────────────────────────────

def _make_unknown(trade_date: str | None = None) -> MarketEnvironment:
    """Return a safe 'unknown' snapshot for graceful degradation."""
    return MarketEnvironment(
        trade_date=trade_date,
        market_state=MARKET_UNKNOWN,
        risk_level=RISK_UNKNOWN,
        can_open_position=False,
        can_add_position=False,
        chase_high_allowed=False,
        action_hint="数据不足，暂不建议做明确判断。",
        indicators={},
        reasons=["数据不足以支撑市场环境判断"],
        version="v1.5.1",
    )


UNKNOWN_SNAPSHOT = _make_unknown()
