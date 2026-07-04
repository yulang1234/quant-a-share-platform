"""Period returns — monthly and yearly. V1.2."""
from __future__ import annotations
import pandas as pd


def calculate_period_returns(equity_df: pd.DataFrame, period: str = "monthly") -> pd.DataFrame:
    if period not in ("monthly", "yearly"):
        raise ValueError(f"period must be monthly or yearly, got '{period}'")
    if equity_df is None or equity_df.empty:
        return pd.DataFrame(columns=["period_key", "period_return", "start_equity", "end_equity", "trading_days"])

    eq = equity_df.sort_values("trade_date").copy()
    eq["trade_date"] = pd.to_datetime(eq["trade_date"])
    if period == "monthly":
        eq["period_key"] = eq["trade_date"].dt.strftime("%Y-%m")
    else:
        eq["period_key"] = eq["trade_date"].dt.strftime("%Y")

    rows = []
    for pk, grp in eq.groupby("period_key"):
        grp = grp.sort_values("trade_date")
        start_e = grp["equity"].iloc[0]
        end_e = grp["equity"].iloc[-1]
        rows.append({
            "period_key": pk,
            "period_return": end_e / start_e - 1 if start_e and start_e != 0 else None,
            "start_equity": start_e,
            "end_equity": end_e,
            "trading_days": len(grp),
        })
    if not rows:
        return pd.DataFrame(columns=["period_key", "period_return", "start_equity", "end_equity", "trading_days"])
    return pd.DataFrame(rows)


def calculate_monthly_returns(equity_df: pd.DataFrame) -> pd.DataFrame:
    return calculate_period_returns(equity_df, "monthly")


def calculate_yearly_returns(equity_df: pd.DataFrame) -> pd.DataFrame:
    return calculate_period_returns(equity_df, "yearly")
