"""V1.5.2 sentiment cycle — orchestrator and CLI entry point.

Wires together:
1. :mod:`src.sentiment.sentiment_indicators` — data → indicators
2. :mod:`src.rules.sentiment_cycle_rules` — indicators → judgment
3. :mod:`src.sentiment.sentiment_types` — wraps result in ``SentimentCycle``

Also retains V1.5.0 ``SentimentSnapshot`` and ``build_sentiment_snapshot()``
for backward compatibility with existing ``daily_decision_card.py``.

Usage
-----
As a library::

    from src.sentiment.sentiment_cycle import build_sentiment_cycle
    cycle = build_sentiment_cycle("2026-07-08")
    print(cycle.action_hint)

As a CLI::

    python -m src.sentiment.sentiment_cycle --date 2026-07-08
    python -m src.sentiment.sentiment_cycle --date 2026-07-08 --json
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any

from src.sentiment.sentiment_types import (
    SentimentCycle, SENTIMENT_UNKNOWN, RISK_UNKNOWN,
    UNKNOWN_SENTIMENT_CYCLE,
)
from src.sentiment.sentiment_indicators import compute_sentiment_indicators
from src.rules.sentiment_cycle_rules import judge_sentiment_cycle

VERSION = "v1.5.2"

# ══════════════════════════════════════════════════════════════════════════════
# V1.5.0 backward-compatible types (keep existing imports working)
# ══════════════════════════════════════════════════════════════════════════════

# Old sentiment tokens (V1.5.0 sentinel values)
SENTIMENT_UNKNOWN_OLD = "unknown"
SENTIMENT_ICE = "ice"
SENTIMENT_REPAIR_OLD = "repair"
SENTIMENT_RISING = "rising"
SENTIMENT_CLIMAX_OLD = "climax"
SENTIMENT_COOLING_OLD = "cooling"
SENTIMENT_DECLINING = "declining"
SENTIMENT_MIXED = "mixed"
SENTIMENT_CYCLES_OLD: tuple[str, ...] = (
    SENTIMENT_UNKNOWN_OLD, SENTIMENT_ICE, SENTIMENT_REPAIR_OLD, SENTIMENT_RISING,
    SENTIMENT_CLIMAX_OLD, SENTIMENT_COOLING_OLD, SENTIMENT_DECLINING, SENTIMENT_MIXED,
)

_HINT_INSUFFICIENT = "情绪数据不足，暂不判断周期"
_HINT_WAIT_V152 = "等待 V1.5.2 完善情绪周期指标"
RISK_HINTS: tuple[str, ...] = (_HINT_INSUFFICIENT, _HINT_WAIT_V152)


@dataclass
class SentimentSnapshot:
    """Structured sentiment-cycle snapshot (V1.5.0 — kept for backward compat)."""

    trade_date: str | None
    sentiment_cycle: str
    limit_up_count: int | None = None
    limit_down_count: int | None = None
    high_board_height: int | None = None
    failed_limit_up_rate: float | None = None
    earning_effect: str | None = None
    risk_hint: str = _HINT_INSUFFICIENT
    evidence: dict[str, Any] = field(default_factory=dict)
    data_quality_status: str = "unknown"
    issue_summary: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ══════════════════════════════════════════════════════════════════════════════
# V1.5.2 public API
# ══════════════════════════════════════════════════════════════════════════════


def build_sentiment_cycle(trade_date: str | None = None) -> SentimentCycle:
    """Build a full sentiment-cycle judgment for *trade_date*.

    * Resolves ``trade_date`` (explicit > latest persisted > today).
    * Computes sentiment indicators from ``stock_daily_raw``.
    * Passes indicators through the rule engine.
    * Wraps the result in a ``SentimentCycle`` dataclass.

    When data is insufficient the result defaults to ``unknown`` with all
    action flags set to ``False``.
    """
    td = _resolve_trade_date(trade_date)

    # 1. Compute indicators
    indicators = compute_sentiment_indicators(td)

    # 2. Apply rules
    if not indicators or not indicators.get("valid_stock_count"):
        return UNKNOWN_SENTIMENT_CYCLE

    judgment = judge_sentiment_cycle(indicators)

    # 3. Build output
    missing = indicators.get("missing_indicator_names") or []

    return SentimentCycle(
        trade_date=td,
        sentiment_cycle=judgment["sentiment_cycle"],
        sentiment_score=judgment["sentiment_score"],
        risk_level=judgment["risk_level"],
        can_try_position=judgment["can_try_position"],
        can_attack=judgment["can_attack"],
        relay_risk_level=judgment["relay_risk_level"],
        chase_high_allowed=judgment["chase_high_allowed"],
        action_hint=judgment["action_hint"],
        indicators=indicators,
        reasons=judgment["reasons"],
        missing_indicator_names=missing,
        version=VERSION,
    )


# ══════════════════════════════════════════════════════════════════════════════
# V1.5.0 backward-compatible API (keep existing callers working)
# ══════════════════════════════════════════════════════════════════════════════


def build_sentiment_snapshot(trade_date: str | None = None) -> SentimentSnapshot:
    """Build a V1.5.0-compatible sentiment snapshot.

    Uses V1.5.2 indicators and rules under the hood, then maps the result
    back to the old ``SentimentSnapshot`` format for backward compatibility.
    """
    td = _resolve_trade_date(trade_date)

    # Build V1.5.2 cycle first
    try:
        cycle = build_sentiment_cycle(td)
    except Exception:
        return SentimentSnapshot(
            trade_date=td,
            sentiment_cycle=SENTIMENT_UNKNOWN_OLD,
            risk_hint=_HINT_INSUFFICIENT,
            evidence={"note": "V1.5.2 情绪周期构建失败"},
            data_quality_status="unknown",
        )

    # Map V1.5.2 → V1.5.0
    old_cycle = _map_cycle_to_old(cycle.sentiment_cycle)
    risk_hint = _map_risk_hint(cycle)

    evidence = {
        "limit_up_count": cycle.indicators.get("limit_up_count"),
        "limit_down_count": cycle.indicators.get("limit_down_count"),
        "max_consecutive_board": cycle.indicators.get("max_consecutive_limit_up_height"),
        "promotion_rate": cycle.indicators.get("promotion_rate"),
        "sentiment_score": cycle.sentiment_score,
        "note": "由 V1.5.2 情绪周期指标自动生成",
    }

    return SentimentSnapshot(
        trade_date=td,
        sentiment_cycle=old_cycle,
        limit_up_count=cycle.indicators.get("limit_up_count"),
        limit_down_count=cycle.indicators.get("limit_down_count"),
        high_board_height=cycle.indicators.get("max_consecutive_limit_up_height"),
        failed_limit_up_rate=None,
        earning_effect=_map_earning_effect(cycle),
        risk_hint=risk_hint,
        evidence=evidence,
        data_quality_status="unknown",
        issue_summary=cycle.missing_indicator_names,
    )


def evaluate_sentiment_cycle(snapshot: SentimentSnapshot) -> SentimentSnapshot:
    """Re-normalise a snapshot's fields (pure on the snapshot).

    Kept for backward compatibility with V1.5.0 callers.
    """
    if snapshot.sentiment_cycle not in SENTIMENT_CYCLES_OLD:
        snapshot.sentiment_cycle = SENTIMENT_UNKNOWN_OLD
    if snapshot.risk_hint not in RISK_HINTS:
        snapshot.risk_hint = _HINT_INSUFFICIENT
    return snapshot


# ── Mapping helpers ──────────────────────────────────────────────────────────


def _map_cycle_to_old(new_cycle: str) -> str:
    """Map V1.5.2 cycle → V1.5.0 cycle token."""
    mapping: dict[str, str] = {
        "ice_point": "ice",
        "repair": "repair",
        "warming": "rising",
        "climax": "climax",
        "cooling": "cooling",
        "retreat": "declining",
        "chaotic": "mixed",
        "unknown": "unknown",
    }
    return mapping.get(new_cycle, "unknown")


def _map_risk_hint(cycle: SentimentCycle) -> str:
    """Generate a V1.5.0-compatible risk_hint from V1.5.2 cycle."""
    if cycle.sentiment_cycle == "unknown":
        return _HINT_INSUFFICIENT
    return cycle.action_hint


def _map_earning_effect(cycle: SentimentCycle) -> str | None:
    """Map V1.5.2 strong_stock_loss_effect to earning_effect string."""
    loss = cycle.indicators.get("strong_stock_loss_effect")
    if loss is True:
        return "negative"
    elif loss is False:
        return "positive"
    return None


# ── Trade date resolution ───────────────────────────────────────────────────


def _resolve_trade_date(explicit: str | None) -> str:
    """Pick the trade date: explicit arg > latest in DB > today."""
    if explicit:
        return str(explicit)[:10]
    try:
        from src.storage.duckdb_repo import query_df
        df = query_df(
            "SELECT MAX(trade_date) AS max_date FROM stock_daily_raw"
        )
        if df is not None and not df.empty:
            val = df.iloc[0]["max_date"]
            if val is not None:
                return str(val)[:10]
    except Exception:
        pass
    return date.today().isoformat()


# ── Backward compat: _has_limit_up_data (used by V1.5.0 tests) ─────────────


def _has_limit_up_data() -> bool:
    """Return True if limit-up data column exists. (V1.5.0 compat)"""
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


# ── Backward compat: build_quality_overview (used by V1.5.0 tests) ────────


def build_quality_overview() -> dict[str, Any]:
    """Stub for V1.5.0 test compatibility."""
    return {"overall_status": "unknown", "top_issues": []}


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point: python -m src.sentiment.sentiment_cycle."""
    import argparse

    parser = argparse.ArgumentParser(
        description="V1.5.2 市场情绪周期判断",
    )
    parser.add_argument(
        "--date", dest="trade_date", default=None,
        help="交易日期 YYYY-MM-DD (默认：最新数据日期)",
    )
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="以 JSON 格式输出",
    )
    args = parser.parse_args()

    cycle = build_sentiment_cycle(args.trade_date)

    if args.json:
        print(json.dumps(cycle.as_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        _print_readable(cycle)


def _print_readable(cycle: SentimentCycle) -> None:
    """Pretty-print the sentiment cycle for terminal consumption."""
    cycle_labels: dict[str, str] = {
        "ice_point": "冰点",
        "repair": "修复",
        "warming": "升温",
        "climax": "高潮",
        "cooling": "降温",
        "retreat": "退潮",
        "chaotic": "混沌",
        "unknown": "未知",
    }
    risk_labels: dict[str, str] = {
        "low": "低",
        "medium": "中",
        "high": "高",
        "extreme": "极高",
        "unknown": "未知",
    }

    print(f"交易日期: {cycle.trade_date}")
    print(f"情绪周期: {cycle_labels.get(cycle.sentiment_cycle, cycle.sentiment_cycle)}")
    print(f"情绪评分: {cycle.sentiment_score}/100")
    print(f"风险等级: {risk_labels.get(cycle.risk_level, cycle.risk_level)}")
    print(f"接力风险: {risk_labels.get(cycle.relay_risk_level, cycle.relay_risk_level)}")
    print(f"允许试错: {'是' if cycle.can_try_position else '否'}")
    print(f"允许进攻: {'是' if cycle.can_attack else '否'}")
    print(f"允许追高: {'是' if cycle.chase_high_allowed else '否'}")
    print(f"操作建议: {cycle.action_hint}")
    print(f"版本: {cycle.version}")
    print()
    print("判断理由:")
    for i, r in enumerate(cycle.reasons, 1):
        print(f"  {i}. {r}")
    print()
    if cycle.missing_indicator_names:
        print("缺失指标:")
        for name in cycle.missing_indicator_names:
            print(f"  - {name}")
    print()
    if cycle.indicators:
        print("关键情绪指标:")
        keys = [
            "limit_up_count", "limit_down_count",
            "max_consecutive_limit_up_height",
            "promotion_rate", "yesterday_limit_up_avg_pct_chg",
            "advance_decline_ratio",
            "strong_stock_loss_effect",
        ]
        for k in keys:
            v = cycle.indicators.get(k)
            if v is not None:
                label = _sentiment_indicator_label(k)
                print(f"  {label}: {v}")


def _sentiment_indicator_label(key: str) -> str:
    """Return a Chinese label for a known sentiment indicator key."""
    labels: dict[str, str] = {
        "limit_up_count": "涨停家数(近似)",
        "limit_down_count": "跌停家数(近似)",
        "limit_up_count_3d_avg": "3日均涨停",
        "limit_down_count_3d_avg": "3日均跌停",
        "limit_up_count_5d_avg": "5日均涨停",
        "limit_down_count_5d_avg": "5日均跌停",
        "valid_stock_count": "有效样本数",
        "up_count": "上涨家数",
        "down_count": "下跌家数",
        "advance_decline_ratio": "涨跌家数比",
        "avg_pct_chg": "平均涨跌幅(%)",
        "median_pct_chg": "中位数涨跌幅(%)",
        "big_gain_count": "大涨家数(>=5%)",
        "big_loss_count": "大跌家数(<=-5%)",
        "max_consecutive_limit_up_height": "最高连板高度(近似)",
        "high_board_stock_count": "高位连板股数",
        "second_board_count": "2连板家数",
        "third_board_count": "3连板家数",
        "above_third_board_count": "3连板以上家数",
        "promotion_rate": "晋级率(近似)",
        "promoted_count": "晋级家数",
        "previous_limit_up_count": "昨日涨停家数",
        "yesterday_limit_up_avg_pct_chg": "昨日涨停股今日均涨幅(%)",
        "yesterday_limit_up_median_pct_chg": "昨日涨停股今日中位涨幅(%)",
        "yesterday_limit_up_positive_ratio": "昨日涨停股今日收红比例",
        "yesterday_limit_up_big_loss_count": "昨日涨停股今日大亏家数",
        "strong_stock_loss_effect": "强势股亏钱效应",
        "strong_stock_big_loss_count": "强势股大亏家数",
        "high_board_negative_count": "高位股转跌家数",
        "recent_limit_up_big_loss_count": "近期涨停股大亏家数",
    }
    return labels.get(key, key)


if __name__ == "__main__":
    main()
