"""
Backtest engine — orchestrates the full V1.1 pipeline.

V1.1: selection → positions → returns → equity curve.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.backtest.backtest_config import create_default_backtest_config, validate_backtest_config
from src.backtest.equity_curve import calculate_equity_curve
from src.backtest.position_builder import (
    build_equal_weight_positions,
    expand_positions_to_daily,
    get_rebalance_dates,
    get_strategy_selection_data,
)
from src.backtest.return_calculator import calculate_portfolio_daily_returns, calculate_stock_returns, get_price_data
from src.storage.duckdb_repo import (
    upsert_backtest_config,
    upsert_backtest_daily_returns,
    upsert_backtest_equity_curve,
    upsert_backtest_positions,
)

logger = logging.getLogger(__name__)


def run_basic_backtest(
    backtest_name: str | None = None,
    strategy_name: str = "",
    start_date: str | None = None,
    end_date: str | None = None,
    initial_cash: float = 1_000_000,
    top_k: int = 20,
    rebalance_frequency: str = "monthly",
    limit: int | None = None,
    universe_name: str = "core_500",
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "backtest_name": backtest_name or f"{strategy_name}_bt",
        "strategy_name": strategy_name,
        "start_date": start_date,
        "end_date": end_date,
        "initial_cash": initial_cash,
        "top_k": top_k,
        "rebalance_frequency": rebalance_frequency,
    }
    validate_backtest_config(config)

    # 1. Selection data
    sel = get_strategy_selection_data(strategy_name, start_date, end_date, top_k, limit)
    if sel.empty:
        upsert_backtest_config(pd.DataFrame([config]))
        return {"backtest_name": config["backtest_name"], "strategy_name": strategy_name, "selection_rows": 0, "position_rows": 0, "daily_return_rows": 0, "equity_rows": 0, "status": "skipped (no selections)"}

    # 2. Rebalance dates
    rd = get_rebalance_dates(sel, rebalance_frequency)
    if not rd:
        upsert_backtest_config(pd.DataFrame([config]))
        return {"backtest_name": config["backtest_name"], "strategy_name": strategy_name, "selection_rows": len(sel), "position_rows": 0, "daily_return_rows": 0, "equity_rows": 0, "status": "skipped (no rebalance dates)"}

    # 3. Positions
    pos = build_equal_weight_positions(sel, rd, top_k)
    if pos.empty:
        upsert_backtest_config(pd.DataFrame([config]))
        return {"backtest_name": config["backtest_name"], "strategy_name": strategy_name, "selection_rows": len(sel), "position_rows": 0, "daily_return_rows": 0, "equity_rows": 0, "status": "skipped (no positions)"}

    # 4. Price data
    codes = pos["stock_code"].unique().tolist()
    price = get_price_data(codes, start_date, end_date)
    if price.empty:
        upsert_backtest_config(pd.DataFrame([config]))
        return {"backtest_name": config["backtest_name"], "strategy_name": strategy_name, "selection_rows": len(sel), "position_rows": len(pos), "daily_return_rows": 0, "equity_rows": 0, "status": "skipped (no price data)"}

    # 5. Expand to daily
    daily_pos = expand_positions_to_daily(pos, price)
    if daily_pos.empty:
        upsert_backtest_config(pd.DataFrame([config]))
        return {"backtest_name": config["backtest_name"], "strategy_name": strategy_name, "selection_rows": len(sel), "position_rows": len(pos), "daily_return_rows": 0, "equity_rows": 0, "status": "skipped (no daily positions)"}

    # 6. Stock returns
    stock_ret = calculate_stock_returns(price)

    # 7. Portfolio returns
    port_ret = calculate_portfolio_daily_returns(daily_pos, stock_ret)

    # 8. Equity curve
    eq = calculate_equity_curve(port_ret, initial_cash)

    # 9. Save
    bn = config["backtest_name"]
    pos["backtest_name"] = bn; pos["strategy_name"] = strategy_name; pos["universe_name"] = universe_name
    daily_pos["backtest_name"] = bn; daily_pos["strategy_name"] = strategy_name; daily_pos["universe_name"] = universe_name
    port_ret["backtest_name"] = bn; port_ret["universe_name"] = universe_name
    eq["backtest_name"] = bn; eq["universe_name"] = universe_name

    upsert_backtest_config(pd.DataFrame([config]))
    p_rows = upsert_backtest_positions(daily_pos)
    d_rows = upsert_backtest_daily_returns(port_ret)
    e_rows = upsert_backtest_equity_curve(eq)

    return {"backtest_name": bn, "strategy_name": strategy_name, "selection_rows": len(sel), "position_rows": p_rows, "daily_return_rows": d_rows, "equity_rows": e_rows, "status": "success"}
