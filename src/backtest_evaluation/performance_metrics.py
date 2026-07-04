"""Performance metrics for backtest evaluation. V1.2."""
from __future__ import annotations
import numpy as np
import pandas as pd


def _sorted_equity(equity_df: pd.DataFrame) -> pd.DataFrame:
    if equity_df is None or equity_df.empty or "equity" not in equity_df.columns:
        return pd.DataFrame()
    return equity_df.sort_values("trade_date")


def calculate_total_return(equity_df: pd.DataFrame) -> float:
    eq = _sorted_equity(equity_df)
    if eq.empty: return float("nan")
    start, end = eq["equity"].iloc[0], eq["equity"].iloc[-1]
    if start is None or start == 0 or np.isnan(start): return float("nan")
    return end / start - 1


def calculate_annualized_return(equity_df: pd.DataFrame, trading_days_per_year: int = 252) -> float:
    eq = _sorted_equity(equity_df)
    if eq.empty: return float("nan")
    days = len(eq)
    if days <= 1: return float("nan")
    total = calculate_total_return(equity_df)
    if np.isnan(total): return float("nan")
    return (1 + total) ** (trading_days_per_year / days) - 1


def calculate_annualized_volatility(daily_return_df: pd.DataFrame, trading_days_per_year: int = 252) -> float:
    if daily_return_df is None or daily_return_df.empty: return float("nan")
    rets = daily_return_df["portfolio_return"].dropna()
    if len(rets) < 2: return float("nan")
    return rets.std(ddof=0) * np.sqrt(trading_days_per_year)


def calculate_sharpe_ratio(daily_return_df: pd.DataFrame, risk_free_rate: float = 0.0, trading_days_per_year: int = 252) -> float:
    if daily_return_df is None or daily_return_df.empty: return float("nan")
    rets = daily_return_df["portfolio_return"].dropna()
    if len(rets) < 2: return float("nan")
    excess = rets - risk_free_rate / trading_days_per_year
    std = excess.std(ddof=0)
    if std == 0 or np.isnan(std): return float("nan")
    return excess.mean() / std * np.sqrt(trading_days_per_year)


def calculate_win_rate(daily_return_df: pd.DataFrame) -> float:
    if daily_return_df is None or daily_return_df.empty: return float("nan")
    rets = daily_return_df["portfolio_return"].dropna()
    if len(rets) == 0: return float("nan")
    return (rets > 0).mean()


def calculate_basic_metrics(equity_df: pd.DataFrame, daily_return_df: pd.DataFrame, risk_free_rate: float = 0.0) -> dict:
    eq = _sorted_equity(equity_df)
    rets = daily_return_df["portfolio_return"].dropna() if daily_return_df is not None and not daily_return_df.empty else pd.Series(dtype=float)
    return {
        "initial_equity": eq["equity"].iloc[0] if not eq.empty else None,
        "final_equity": eq["equity"].iloc[-1] if not eq.empty else None,
        "total_return": calculate_total_return(equity_df),
        "annualized_return": calculate_annualized_return(equity_df),
        "annualized_volatility": calculate_annualized_volatility(daily_return_df),
        "sharpe_ratio": calculate_sharpe_ratio(daily_return_df, risk_free_rate),
        "win_rate": calculate_win_rate(daily_return_df),
        "avg_daily_return": rets.mean() if len(rets) > 0 else None,
        "best_daily_return": rets.max() if len(rets) > 0 else None,
        "worst_daily_return": rets.min() if len(rets) > 0 else None,
        "trading_days": len(rets),
    }
