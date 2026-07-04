"""Drawdown calculation. V1.2."""
from __future__ import annotations
import numpy as np
import pandas as pd


def calculate_drawdown_series(equity_df: pd.DataFrame) -> pd.DataFrame:
    if equity_df is None or equity_df.empty:
        return pd.DataFrame(columns=["trade_date", "equity", "running_max_equity", "drawdown"])
    eq = equity_df.sort_values("trade_date").copy()
    eq["running_max_equity"] = eq["equity"].cummax()
    eq["drawdown"] = eq["equity"] / eq["running_max_equity"] - 1
    return eq[["trade_date", "equity", "running_max_equity", "drawdown"]]


def calculate_max_drawdown(equity_df: pd.DataFrame) -> float:
    dd = calculate_drawdown_series(equity_df)
    if dd.empty: return float("nan")
    return dd["drawdown"].min()


def calculate_calmar_ratio(annualized_return: float, max_drawdown: float) -> float:
    if max_drawdown is None or max_drawdown == 0 or np.isnan(max_drawdown):
        return float("nan")
    return annualized_return / abs(max_drawdown)
