"""V1.5.0 market-state skeleton — conservative, unknown-by-default.

The current A-share data substrate has **no broad-market index table** and
**no limit-up / limit-down counts**, so a confident market-state verdict
cannot be justified. This module therefore:

* defaults ``market_state`` to ``unknown`` and the three positioning
  switches (``can_open_position`` / ``can_add_position`` /
  ``chase_high_allowed``) to ``unknown``;
* downgrades ``market_state`` to ``weak`` when the data quality verdict is
  ``risky`` / ``not_recommended`` / ``unavailable``;
* never emits ``strong`` or ``neutral``;
* exposes ``evidence`` as read-only rise/fall/flat counts for the latest
  trade date (advance/decline, NOT limit-up/down — there is no persisted
  limit-status column).

No network, no writes, no index fetch. Strictly read-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any

from src.data_quality.quality_dashboard import (
    build_quality_overview,
    OVERALL_RISKY, OVERALL_NOT_RECOMMENDED,
    HEALTH_RISKY, HEALTH_NOT_RECOMMENDED, HEALTH_UNAVAILABLE, HEALTH_UNKNOWN,
)

# ── Enumerations (string tokens) ──────────────────────────────────────────────

MARKET_UNKNOWN = "unknown"
MARKET_WEAK = "weak"
MARKET_NEUTRAL = "neutral"
MARKET_STRONG = "strong"
MARKET_STATES: tuple[str, ...] = (MARKET_UNKNOWN, MARKET_WEAK, MARKET_NEUTRAL, MARKET_STRONG)

RISK_UNKNOWN = "unknown"
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_LEVELS: tuple[str, ...] = (RISK_UNKNOWN, RISK_LOW, RISK_MEDIUM, RISK_HIGH)

BOOL_UNKNOWN = "unknown"
BOOL_TRUE = "true"
BOOL_FALSE = "false"
BOOL_VALUES: tuple[str, ...] = (BOOL_UNKNOWN, BOOL_TRUE, BOOL_FALSE)

# Data-quality verdicts that block any aggressive stance.
_BLOCKING_QUALITY: frozenset[str] = frozenset({
    OVERALL_RISKY, OVERALL_NOT_RECOMMENDED,
    HEALTH_RISKY, HEALTH_NOT_RECOMMENDED, HEALTH_UNAVAILABLE,
})

# action_hint whitelist (only these exact strings are emitted).
_ACTION_HINT_INSUFFICIENT = "数据不足，建议仅观察"
_ACTION_HINT_UNKNOWN = "市场状态不明，暂不提高进攻性"
_ACTION_HINT_RISKY = "风险偏高，避免追高"
_ACTION_HINT_NEUTRAL = "市场中性，等待进一步确认"
_ACTION_HINT_STRONG = "市场偏强，但仍需等待后续版本完善判断"
_ACTION_HINTS: tuple[str, ...] = (
    _ACTION_HINT_INSUFFICIENT, _ACTION_HINT_UNKNOWN, _ACTION_HINT_RISKY,
    _ACTION_HINT_NEUTRAL, _ACTION_HINT_STRONG,
)


@dataclass
class MarketSnapshot:
    """Structured market-state snapshot (V1.5.0 skeleton)."""

    trade_date: str | None
    market_state: str
    risk_level: str
    can_open_position: str   # true / false / unknown
    can_add_position: str
    chase_high_allowed: str
    action_hint: str
    evidence: dict[str, Any] = field(default_factory=dict)
    data_quality_status: str = HEALTH_UNKNOWN
    issue_summary: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_trade_date(explicit: str | None) -> str | None:
    """Pick the latest trade date: explicit arg > stock_daily_raw MAX > today."""
    if explicit:
        return str(explicit)[:10]
    try:
        from ui.components.ui_helpers import safe_fetch_latest_date
        d = safe_fetch_latest_date("stock_daily_raw")
        if d:
            return d
    except Exception:
        pass
    return date.today().isoformat()


def _load_quality_status() -> tuple[str, list[str]]:
    """Return (overall_status, top_issues) from quality_dashboard."""
    try:
        ov = build_quality_overview()
        return (
            str(ov.get("overall_status") or HEALTH_UNKNOWN),
            list(ov.get("top_issues") or []),
        )
    except Exception:
        return HEALTH_UNKNOWN, []


def _read_only_advance_decline(trade_date: str | None) -> dict[str, Any]:
    """Best-effort advance/decline/flat counts for the latest trade date.

    Reads ``stock_daily_raw.pct_change`` (NOT a limit-up flag — only the
    sign of pct_change). Returns ``{}`` on any error / missing date.
    """
    if not trade_date:
        return {}
    try:
        from src.storage.duckdb_repo import query_df
        sql = (
            "SELECT "
            "SUM(CAST(pct_change > 0 AS BIGINT)) AS up_count, "
            "SUM(CAST(pct_change < 0 AS BIGINT)) AS down_count, "
            "SUM(CAST(pct_change = 0 AS BIGINT)) AS flat_count, "
            "COUNT(*) AS total_count "
            "FROM stock_daily_raw WHERE trade_date = ?"
        )
        df = query_df(sql, [trade_date])
        if df is None or df.empty:
            return {}
        row = df.iloc[0]
        return {
            "trade_date": trade_date,
            "up_count": int(row["up_count"]) if row["up_count"] is not None else 0,
            "down_count": int(row["down_count"]) if row["down_count"] is not None else 0,
            "flat_count": int(row["flat_count"]) if row["flat_count"] is not None else 0,
            "total_count": int(row["total_count"]) if row["total_count"] is not None else 0,
            "note": "涨跌家数按 pct_change 正负计，非真实涨停/跌停判定",
        }
    except Exception:
        return {}


# ── Public API ─────────────────────────────────────────────────────────────────

def build_market_snapshot(trade_date: str | None = None) -> MarketSnapshot:
    """Build a conservative market-state snapshot.

    * Resolves ``trade_date`` (explicit > latest persisted > today).
    * Reads the V1.4.10 overall quality verdict; risky / not_recommended
      / unavailable quality verdicts may downgrade ``market_state`` to
      ``weak`` (never ``strong``/``neutral``).
    * With no index / limit-up data, ``market_state`` is ``unknown`` and
      the three positioning switches default to ``unknown``.
    """
    td = _resolve_trade_date(trade_date)
    quality_status, top_issues = _load_quality_status()

    # Conservative: no index data → unknown.
    market_state = MARKET_UNKNOWN
    risk_level = RISK_UNKNOWN

    # Data-quality downgrade: bad quality blocks aggression and adds a
    # risk signal, but still never promotes the state to neutral/strong.
    if quality_status in _BLOCKING_QUALITY:
        market_state = MARKET_WEAK
        risk_level = RISK_HIGH

    can_open = BOOL_UNKNOWN
    can_add = BOOL_UNKNOWN
    chase = BOOL_UNKNOWN

    action_hint = _resolve_action_hint(market_state, quality_status)

    evidence = _read_only_advance_decline(td)

    return MarketSnapshot(
        trade_date=td,
        market_state=market_state,
        risk_level=risk_level,
        can_open_position=can_open,
        can_add_position=can_add,
        chase_high_allowed=chase,
        action_hint=action_hint,
        evidence=evidence,
        data_quality_status=quality_status,
        issue_summary=top_issues,
    )


def evaluate_market_state(snapshot: MarketSnapshot) -> MarketSnapshot:
    """Re-evaluate a snapshot's derived fields.

    Pure function on the snapshot (no extra I/O). Kept for symmetry with
    the spec, so callers that already hold a snapshot can refresh its
    rules-derived outputs without rebuilding the evidence.
    """
    snapshot.action_hint = _resolve_action_hint(
        snapshot.market_state, snapshot.data_quality_status)
    if snapshot.market_state not in MARKET_STATES:
        snapshot.market_state = MARKET_UNKNOWN
    if snapshot.risk_level not in RISK_LEVELS:
        snapshot.risk_level = RISK_UNKNOWN
    if snapshot.can_open_position not in BOOL_VALUES:
        snapshot.can_open_position = BOOL_UNKNOWN
    if snapshot.can_add_position not in BOOL_VALUES:
        snapshot.can_add_position = BOOL_UNKNOWN
    if snapshot.chase_high_allowed not in BOOL_VALUES:
        snapshot.chase_high_allowed = BOOL_UNKNOWN
    return snapshot


def _resolve_action_hint(market_state: str, quality_status: str) -> str:
    """Pick an action_hint from the whitelist."""
    if quality_status in _BLOCKING_QUALITY or market_state == MARKET_WEAK:
        return _ACTION_HINT_RISKY
    # market_state is unknown (no index data) → conservative.
    if market_state == MARKET_UNKNOWN:
        return _ACTION_HINT_UNKNOWN
    if market_state == MARKET_NEUTRAL:
        return _ACTION_HINT_NEUTRAL
    if market_state == MARKET_STRONG:
        return _ACTION_HINT_STRONG
    return _ACTION_HINT_INSUFFICIENT