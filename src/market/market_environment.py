"""V1.5.1 market environment — orchestrator and CLI entry point.

Wires together:
1. :mod:`src.market.market_indicators` — data → indicators
2. :mod:`src.rules.market_environment_rules` — indicators → judgment
3. :mod:`src.market.market_types` — wraps result in ``MarketEnvironment``

Usage
-----
As a library::

    from src.market.market_environment import build_market_environment
    env = build_market_environment("2026-07-08")
    print(env.action_hint)

As a CLI::

    python -m src.market.market_environment --date 2026-07-08
    python -m src.market.market_environment --date 2026-07-08 --json
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from src.market.market_types import (
    MarketEnvironment, MARKET_UNKNOWN, RISK_UNKNOWN,
    _make_unknown,
)
from src.market.market_indicators import compute_market_indicators
from src.rules.market_environment_rules import judge_market_environment

VERSION = "v1.5.1"


def build_market_environment(trade_date: str | None = None) -> MarketEnvironment:
    """Build a full market-environment judgment for *trade_date*.

    * Resolves ``trade_date`` (explicit > latest persisted > today).
    * Computes market-wide indicators from ``stock_daily_raw``.
    * Passes indicators through the rule engine.
    * Wraps the result in a ``MarketEnvironment`` dataclass.

    When data is insufficient the result defaults to ``unknown`` with
    ``can_open_position = can_add_position = chase_high_allowed = False``.
    """
    td = _resolve_trade_date(trade_date)

    # 1. Compute indicators
    indicators = compute_market_indicators(td)

    # 2. Apply rules
    if not indicators or not indicators.get("valid_stock_count"):
        return _make_unknown(td)

    judgment = judge_market_environment(indicators)

    # 3. Build output
    return MarketEnvironment(
        trade_date=td,
        market_state=judgment["market_state"],
        risk_level=judgment["risk_level"],
        can_open_position=judgment["can_open_position"],
        can_add_position=judgment["can_add_position"],
        chase_high_allowed=judgment["chase_high_allowed"],
        action_hint=judgment["action_hint"],
        indicators=indicators,
        reasons=judgment["reasons"],
        version=VERSION,
    )


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


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point: python -m src.market.market_environment."""
    import argparse

    parser = argparse.ArgumentParser(
        description="V1.5.1 市场环境判断",
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

    env = build_market_environment(args.trade_date)

    if args.json:
        print(json.dumps(env.as_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        _print_readable(env)


def _print_readable(env: MarketEnvironment) -> None:
    """Pretty-print the market environment for terminal consumption."""
    state_labels: dict[str, str] = {
        "attack": "进攻",
        "neutral": "中性",
        "defense": "防守",
        "high_risk": "高风险",
        "unknown": "未知",
    }
    risk_labels: dict[str, str] = {
        "low": "低",
        "medium": "中",
        "high": "高",
        "extreme": "极高",
        "unknown": "未知",
    }

    print(f"交易日期: {env.trade_date}")
    print(f"市场状态: {state_labels.get(env.market_state, env.market_state)}")
    print(f"风险等级: {risk_labels.get(env.risk_level, env.risk_level)}")
    print(f"允许开仓: {'是' if env.can_open_position else '否'}")
    print(f"允许加仓: {'是' if env.can_add_position else '否'}")
    print(f"允许追高: {'是' if env.chase_high_allowed else '否'}")
    print(f"操作建议: {env.action_hint}")
    print(f"版本: {env.version}")
    print()
    print("判断理由:")
    for i, r in enumerate(env.reasons, 1):
        print(f"  {i}. {r}")
    print()
    if env.indicators:
        print("关键指标:")
        keys = [
            "avg_pct_chg", "advance_decline_ratio",
            "approximate_limit_up_count", "approximate_limit_down_count",
            "pct_above_ma5", "pct_above_ma20",
            "turnover_ratio_5d", "turnover_ratio_20d",
        ]
        for k in keys:
            v = env.indicators.get(k)
            if v is not None:
                label = _indicator_label(k)
                print(f"  {label}: {v}")


def _indicator_label(key: str) -> str:
    """Return a Chinese label for a known indicator key."""
    labels: dict[str, str] = {
        "avg_pct_chg": "样本平均涨跌幅(%)",
        "median_pct_chg": "样本中位数涨跌幅(%)",
        "advance_decline_ratio": "涨跌家数比",
        "approximate_limit_up_count": "近似涨停家数",
        "approximate_limit_down_count": "近似跌停家数",
        "sample_stock_count": "样本总数",
        "valid_stock_count": "有效样本数",
        "total_turnover_yuan": "样本成交额(元)",
        "turnover_ratio_5d": "成交额/5日均值",
        "turnover_ratio_20d": "成交额/20日均值",
        "pct_above_ma5": "站上5日均线占比(%)",
        "pct_above_ma10": "站上10日均线占比(%)",
        "pct_above_ma20": "站上20日均线占比(%)",
        "return_5d": "5日样本涨跌幅(%)",
        "return_20d": "20日样本涨跌幅(%)",
        "composite_volatility_5d": "5日波动率(%)",
        "composite_volatility_20d": "20日波动率(%)",
    }
    return labels.get(key, key)


if __name__ == "__main__":
    main()
