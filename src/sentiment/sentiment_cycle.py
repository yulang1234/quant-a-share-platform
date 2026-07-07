"""V1.5.0 sentiment-cycle skeleton — unknown by default.

The substrate has **no persisted limit-up/limit-down / consecutive-board
/ failed-limit-up / earning-effect data**, so this module returns
``sentiment_cycle = unknown`` with all count fields as ``None`` and emits
only conservative observation text. ``risk_hint`` is restricted to a fixed
whitelist that contains no buy/sell advice.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from src.data_quality.quality_dashboard import (
    build_quality_overview, HEALTH_UNKNOWN,
)

# ── Enumerations ──────────────────────────────────────────────────────────────

SENTIMENT_UNKNOWN = "unknown"
SENTIMENT_ICE = "ice"
SENTIMENT_REPAIR = "repair"
SENTIMENT_RISING = "rising"
SENTIMENT_CLIMAX = "climax"
SENTIMENT_COOLING = "cooling"
SENTIMENT_DECLINING = "declining"
SENTIMENT_MIXED = "mixed"
SENTIMENT_CYCLES: tuple[str, ...] = (
    SENTIMENT_UNKNOWN, SENTIMENT_ICE, SENTIMENT_REPAIR, SENTIMENT_RISING,
    SENTIMENT_CLIMAX, SENTIMENT_COOLING, SENTIMENT_DECLINING, SENTIMENT_MIXED,
)

# risk_hint whitelist (only these exact strings are emitted).
_HINT_INSUFFICIENT = "情绪数据不足，暂不判断周期"
_HINT_WAIT_V152 = "等待 V1.5.2 完善情绪周期指标"
RISK_HINTS: tuple[str, ...] = (_HINT_INSUFFICIENT, _HINT_WAIT_V152)


@dataclass
class SentimentSnapshot:
    """Structured sentiment-cycle snapshot (V1.5.0 skeleton)."""

    trade_date: str | None
    sentiment_cycle: str
    limit_up_count: int | None = None
    limit_down_count: int | None = None
    high_board_height: int | None = None
    failed_limit_up_rate: float | None = None
    earning_effect: str | None = None
    risk_hint: str = _HINT_INSUFFICIENT
    evidence: dict[str, Any] = field(default_factory=dict)
    data_quality_status: str = HEALTH_UNKNOWN
    issue_summary: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_quality_status() -> tuple[str, list[str]]:
    try:
        ov = build_quality_overview()
        return (
            str(ov.get("overall_status") or HEALTH_UNKNOWN),
            list(ov.get("top_issues") or []),
        )
    except Exception:
        return HEALTH_UNKNOWN, []


def _has_limit_up_data() -> bool:
    """Return True only if a persisted limit-up/down column exists.

    The current DuckDB schema has no such column, so this returns False and
    the sentiment cycle stays unknown. Any error → False (graceful).
    """
    try:
        from src.storage.duckdb_repo import query_df
        df = query_df(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'stock_daily_raw' "
            "AND column_name IN ('limit_up','is_limit_up','limit_status',"
            "'zt_flag','limit_up_count')"
        )
        return df is not None and not df.empty
    except Exception:
        return False


# ── Public API ─────────────────────────────────────────────────────────────────

def build_sentiment_snapshot(trade_date: str | None = None) -> SentimentSnapshot:
    """Build a conservative sentiment-cycle snapshot.

    Without persisted limit-up/down data, ``sentiment_cycle`` is ``unknown``
    and all count fields are ``None``.
    """
    quality_status, top_issues = _load_quality_status()
    cycle = SENTIMENT_UNKNOWN
    risk_hint = _HINT_INSUFFICIENT

    if _has_limit_up_data():
        # When (and only when) the column exists in a future version we will
        # compute counts. Today it does not, so we stay unknown — never
        # fabricate numbers, never use random data.
        cycle = SENTIMENT_UNKNOWN
        risk_hint = _HINT_WAIT_V152
    else:
        risk_hint = _HINT_INSUFFICIENT

    return SentimentSnapshot(
        trade_date=trade_date,
        sentiment_cycle=cycle,
        limit_up_count=None,
        limit_down_count=None,
        high_board_height=None,
        failed_limit_up_rate=None,
        earning_effect=None,
        risk_hint=risk_hint,
        evidence={"note": "无涨停/跌停/连板/炸板持久化数据"},
        data_quality_status=quality_status,
        issue_summary=top_issues,
    )


def evaluate_sentiment_cycle(snapshot: SentimentSnapshot) -> SentimentSnapshot:
    """Re-normalise a snapshot's fields (pure on the snapshot)."""
    if snapshot.sentiment_cycle not in SENTIMENT_CYCLES:
        snapshot.sentiment_cycle = SENTIMENT_UNKNOWN
    if snapshot.risk_hint not in RISK_HINTS:
        snapshot.risk_hint = _HINT_INSUFFICIENT
    return snapshot
