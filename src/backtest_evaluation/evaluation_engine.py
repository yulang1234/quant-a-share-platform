"""Evaluation engine — run metrics on a backtest result. V1.2."""
from __future__ import annotations
from typing import Any
import pandas as pd
from src.backtest_evaluation.performance_metrics import calculate_basic_metrics
from src.backtest_evaluation.drawdown import calculate_drawdown_series, calculate_max_drawdown, calculate_calmar_ratio
from src.backtest_evaluation.period_returns import calculate_monthly_returns, calculate_yearly_returns
from src.storage.duckdb_repo import (
    fetch_backtest_daily_returns, fetch_backtest_equity_curve,
    upsert_backtest_performance_summary, upsert_backtest_drawdown_series,
    upsert_backtest_monthly_return, upsert_backtest_yearly_return,
)


def get_backtest_result_data(backtest_name: str, start_date=None, end_date=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    eq = fetch_backtest_equity_curve(backtest_name, start_date, end_date)
    ret = fetch_backtest_daily_returns(backtest_name, start_date, end_date)
    return eq, ret


def evaluate_backtest(backtest_name: str, start_date=None, end_date=None, risk_free_rate: float = 0.0) -> tuple:
    eq, ret = get_backtest_result_data(backtest_name, start_date, end_date)
    if eq.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    metrics = calculate_basic_metrics(eq, ret, risk_free_rate)
    metrics["max_drawdown"] = calculate_max_drawdown(eq)
    metrics["calmar_ratio"] = calculate_calmar_ratio(metrics.get("annualized_return", 0), metrics["max_drawdown"])
    metrics["backtest_name"] = backtest_name
    metrics["start_date"] = start_date or (eq["trade_date"].min().strftime("%Y-%m-%d") if "trade_date" in eq.columns else None)
    metrics["end_date"] = end_date or (eq["trade_date"].max().strftime("%Y-%m-%d") if "trade_date" in eq.columns else None)
    metrics["risk_free_rate"] = risk_free_rate
    summary = pd.DataFrame([metrics])

    dd = calculate_drawdown_series(eq)
    if not dd.empty: dd["backtest_name"] = backtest_name

    monthly = calculate_monthly_returns(eq)
    if not monthly.empty: monthly["backtest_name"] = backtest_name

    yearly = calculate_yearly_returns(eq)
    if not yearly.empty: yearly["backtest_name"] = backtest_name

    return summary, dd, monthly, yearly


def _prepare_monthly_return_df(monthly_df: pd.DataFrame) -> pd.DataFrame:
    if monthly_df is None or monthly_df.empty:
        return monthly_df
    out = monthly_df.copy()
    if "period_key" in out.columns and "year_month" not in out.columns:
        out["year_month"] = out["period_key"]
    if "period_return" in out.columns and "monthly_return" not in out.columns:
        out["monthly_return"] = out["period_return"]
    return out


def _prepare_yearly_return_df(yearly_df: pd.DataFrame) -> pd.DataFrame:
    if yearly_df is None or yearly_df.empty:
        return yearly_df
    out = yearly_df.copy()
    if "period_key" in out.columns and "year" not in out.columns:
        out["year"] = out["period_key"]
    if "period_return" in out.columns and "yearly_return" not in out.columns:
        out["yearly_return"] = out["period_return"]
    return out


def save_backtest_evaluation(summary_df, drawdown_df, monthly_df, yearly_df) -> dict[str, int]:
    monthly_out = _prepare_monthly_return_df(monthly_df)
    yearly_out = _prepare_yearly_return_df(yearly_df)
    return {
        "performance_rows": upsert_backtest_performance_summary(summary_df) if not summary_df.empty else 0,
        "drawdown_rows": upsert_backtest_drawdown_series(drawdown_df) if not drawdown_df.empty else 0,
        "monthly_rows": upsert_backtest_monthly_return(monthly_out) if not monthly_out.empty else 0,
        "yearly_rows": upsert_backtest_yearly_return(yearly_out) if not yearly_out.empty else 0,
    }


def run_backtest_evaluation(backtest_name: str, start_date=None, end_date=None, risk_free_rate: float = 0.0) -> dict[str, Any]:
    summary, dd, monthly, yearly = evaluate_backtest(backtest_name, start_date, end_date, risk_free_rate)
    if summary.empty:
        return {"backtest_name": backtest_name, "performance_rows": 0, "drawdown_rows": 0, "monthly_rows": 0, "yearly_rows": 0, "status": "skipped (no equity data)"}
    saved = save_backtest_evaluation(summary, dd, monthly, yearly)
    saved["backtest_name"] = backtest_name
    saved["status"] = "success"
    return saved
