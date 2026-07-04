"""
Backtest configuration — validation and defaults.

V1.1: basic config with rebalance frequency.
"""

from __future__ import annotations

from typing import Any

FREQUENCIES = {"daily", "weekly", "monthly"}


def validate_backtest_config(config: dict[str, Any]) -> None:
    if not config.get("backtest_name"):
        raise ValueError("backtest_name is required")
    if not config.get("strategy_name"):
        raise ValueError("strategy_name is required")
    ic = config.get("initial_cash", 0)
    if ic <= 0:
        raise ValueError(f"initial_cash must be > 0, got {ic}")
    tk = config.get("top_k", 0)
    if tk <= 0:
        raise ValueError(f"top_k must be > 0, got {tk}")
    freq = config.get("rebalance_frequency", "")
    if freq not in FREQUENCIES:
        raise ValueError(f"rebalance_frequency must be one of {FREQUENCIES}, got '{freq}'")
    sd = config.get("start_date")
    ed = config.get("end_date")
    if sd and ed and sd > ed:
        raise ValueError(f"start_date ({sd}) must be <= end_date ({ed})")


def create_default_backtest_config(
    strategy_name: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    return {
        "backtest_name": f"{strategy_name}_bt",
        "strategy_name": strategy_name,
        "start_date": start_date,
        "end_date": end_date,
        "initial_cash": 1_000_000,
        "top_k": 20,
        "rebalance_frequency": "monthly",
        "price_type": "qfq_close",
    }
