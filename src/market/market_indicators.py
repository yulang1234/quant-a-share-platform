"""V1.5.1 market indicators — read-only computation from ``stock_daily_raw``.

All indicators are derived from individual stock data already persisted in
DuckDB.  No network calls, no new data sources, no writes.

Key design decisions
--------------------
* **No index table** — the project has never stored broad-market index data.
  We aggregate all valid stocks in ``stock_daily_raw`` on each trade date
  (equal-weighted composite).  The output is explicitly scoped to the
  **valid sample universe**, NOT the full A-share market.
* **No limit-up / limit-down flag** — we use ``pct_change >= 9.8`` /
  ``pct_change <= -9.8`` as a rough approximation.  The indicator keys are
  ``approximate_limit_up_count`` / ``approximate_limit_down_count``.
* **Graceful degradation** — when historical window data is insufficient
  for MA / turnover / volatility indicators, those fields are omitted and
  listed in ``missing_indicator_names``.  The caller treats this as
  partial-data judgment, not a crash.

Indicator dictionary keys
--------------------------
Sample scope
    sample_stock_count          total rows in today's query (may include noisy)
    valid_stock_count           stocks with usable pct_change (excludes NaN)

Price
    avg_pct_chg                 mean pct_change across valid stocks
    median_pct_chg              median pct_change
    return_5d                   5-trading-day composite return
    return_20d                  20-trading-day composite return

Advance / decline
    up_count                    count of stocks with pct_change > 0
    down_count                  count of stocks with pct_change < 0
    flat_count                  count of stocks with pct_change == 0
    advance_decline_ratio       up_count / max(down_count, 1)

Approximate limit moves
    approximate_limit_up_count  count of pct_change >= 9.8
    approximate_limit_down_count count of pct_change <= -9.8

Turnover
    total_turnover_yuan         sum of amount (in yuan)
    turnover_ratio_5d           today / 5-day avg (omitted if window < 5)
    turnover_ratio_20d          today / 20-day avg (omitted if window < 20)

Moving-average breadth (omitted if window < required)
    pct_above_ma5               % of stocks where close > own MA5
    pct_above_ma10              % of stocks where close > own MA10
    pct_above_ma20              % of stocks where close > own MA20

Composite MA position (omitted if window < required)
    composite_close_above_ma5   bool, composite close vs composite MA5
    composite_close_above_ma10  bool
    composite_close_above_ma20  bool

Volatility / amplitude
    composite_amplitude_mean    mean of individual stock amplitudes
    composite_volatility_5d     std of composite daily returns (5 days)
    composite_volatility_20d    std of composite daily returns (20 days)

Graceful degradation
    missing_indicator_names     list of indicator keys that could not be
                                computed due to insufficient data window
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from src.storage.duckdb_repo import query_df

logger = logging.getLogger(__name__)

# Number of prior trading days needed for MA20 / volatility_20d.
_PRIOR_DAYS_NEEDED = 20

# Columns we need from stock_daily_raw.
_NEEDED_COLS = [
    "stock_code", "trade_date",
    "close", "amount", "pct_change", "amplitude",
]


def compute_market_indicators(trade_date: str) -> dict[str, Any]:
    """Compute all market-wide indicators for *trade_date*.

    Returns an empty dict when no data exists for the date (caller is
    expected to treat this as "unknown").
    """
    td = str(trade_date)[:10]

    # ── 1. Today's snapshot ─────────────────────────────────────────────
    try:
        df_today = _fetch_daily_snapshot(td)
    except Exception:
        logger.warning("Failed to query today's data for %s", td, exc_info=True)
        return {}

    if df_today is None or df_today.empty:
        logger.info("No stock_daily_raw data for %s", td)
        return {}

    # ── 2. Prior trading dates (20-day window) ─────────────────────────
    try:
        prior_dates = _get_prior_trade_dates(td, _PRIOR_DAYS_NEEDED)
    except Exception:
        logger.warning("Failed to get prior trade dates for %s", td, exc_info=True)
        prior_dates = pd.DataFrame()

    if prior_dates.empty:
        # Only today's data — compute what we can.
        return _indicators_single_day(df_today)

    # ── 3. Historical window data ──────────────────────────────────────
    min_date = str(prior_dates.min())[:10]
    try:
        df_hist = _fetch_window(min_date, td)
    except Exception:
        logger.warning("Failed to query historical window for %s", td, exc_info=True)
        return _indicators_single_day(df_today)

    if df_hist is None or df_hist.empty:
        return _indicators_single_day(df_today)

    # ── 4. Compute full indicators ─────────────────────────────────────
    return _compute_full_indicators(df_today, df_hist, td)


# ── Data fetching helpers ────────────────────────────────────────────────────


def _fetch_daily_snapshot(trade_date: str) -> pd.DataFrame:
    """Return all rows from stock_daily_raw for *trade_date*."""
    cols = ", ".join(_NEEDED_COLS)
    return query_df(
        f"SELECT {cols} FROM stock_daily_raw WHERE trade_date = ?",
        [trade_date],
    )


def _get_prior_trade_dates(
    trade_date: str, limit: int,
) -> pd.DataFrame:
    """Return up to *limit* trade dates strictly before *trade_date*."""
    df = query_df(
        "SELECT DISTINCT trade_date FROM stock_daily_raw "
        "WHERE trade_date < ? ORDER BY trade_date DESC LIMIT ?",
        [trade_date, limit],
    )
    if df is None or df.empty:
        return pd.DataFrame()
    return df["trade_date"]


def _fetch_window(start_date: str, end_date: str) -> pd.DataFrame:
    """Return all rows in [start_date, end_date] needed for indicators."""
    cols = ", ".join(_NEEDED_COLS)
    return query_df(
        f"SELECT {cols} FROM stock_daily_raw "
        "WHERE trade_date >= ? AND trade_date <= ? "
        "ORDER BY stock_code, trade_date",
        [start_date, end_date],
    )


# ── Single-day fallback ──────────────────────────────────────────────────────


def _indicators_single_day(df: pd.DataFrame) -> dict[str, Any]:
    """Compute what we can from just one day's data."""
    n_sample = len(df)
    pct = df["pct_change"].dropna()
    n_valid = len(pct)
    up = int((pct > 0).sum())
    down = int((pct < 0).sum())
    flat = int((pct == 0).sum())

    # All MA / volatility / turnover-ratio indicators require a multi-day
    # window — list them as missing.
    missing = [
        "pct_above_ma5", "pct_above_ma10", "pct_above_ma20",
        "composite_close_above_ma5", "composite_close_above_ma10",
        "composite_close_above_ma20",
        "turnover_ratio_5d", "turnover_ratio_20d",
        "return_5d", "return_20d",
        "composite_volatility_5d", "composite_volatility_20d",
    ]

    return {
        "sample_stock_count": n_sample,
        "valid_stock_count": n_valid,
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "advance_decline_ratio": round(up / max(down, 1), 4),
        "avg_pct_chg": round(float(pct.mean()), 4) if n_valid else 0.0,
        "median_pct_chg": round(float(pct.median()), 4) if n_valid else 0.0,
        "approximate_limit_up_count": int((pct >= 9.8).sum()),
        "approximate_limit_down_count": int((pct <= -9.8).sum()),
        "total_turnover_yuan": _safe_sum(df["amount"]),
        "composite_amplitude_mean": _safe_mean(df["amplitude"]),
        "missing_indicator_names": missing,
        "data_note": "仅有单日数据，均线及波动率指标不可用",
    }


# ── Full indicator computation ───────────────────────────────────────────────


def _compute_full_indicators(
    df_today: pd.DataFrame, df_hist: pd.DataFrame, trade_date: str,
) -> dict[str, Any]:
    """Compute all indicators using today + historical window data."""
    missing: list[str] = []

    # --- A. Single-day aggregates (from today) ---
    n_sample = len(df_today)
    pct = df_today["pct_change"].dropna()
    n_valid = len(pct)
    up = int((pct > 0).sum())
    down = int((pct < 0).sum())
    flat = int((pct == 0).sum())

    indicators: dict[str, Any] = {
        "sample_stock_count": n_sample,
        "valid_stock_count": n_valid,
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "advance_decline_ratio": round(up / max(down, 1), 4),
        "avg_pct_chg": round(float(pct.mean()), 4) if n_valid else 0.0,
        "median_pct_chg": round(float(pct.median()), 4) if n_valid else 0.0,
        "approximate_limit_up_count": int((pct >= 9.8).sum()),
        "approximate_limit_down_count": int((pct <= -9.8).sum()),
        "total_turnover_yuan": _safe_sum(df_today["amount"]),
    }

    # --- B. Per-stock MA breadth ---
    _add_ma_breadth(indicators, df_hist, trade_date, missing)

    # --- C. Composite (market-average) close and its MAs ---
    _add_composite_ma_position(indicators, df_hist, trade_date, missing)

    # --- D. Turnover ratios ---
    _add_turnover_ratios(indicators, df_hist, trade_date, missing)

    # --- E. Composite multi-day returns & volatility ---
    _add_composite_returns_volatility(indicators, df_hist, missing)

    # --- F. Amplitude ---
    indicators["composite_amplitude_mean"] = _safe_mean(df_today["amplitude"])

    # --- G. Missing indicators ---
    indicators["missing_indicator_names"] = missing

    return indicators


def _add_ma_breadth(
    indicators: dict[str, Any], df_hist: pd.DataFrame,
    trade_date: str, missing: list[str],
) -> None:
    """Compute % of stocks where close > own MA5 / MA10 / MA20."""
    ma_keys = ["pct_above_ma5", "pct_above_ma10", "pct_above_ma20"]
    try:
        df = df_hist.copy()
        df = df.sort_values(["stock_code", "trade_date"])

        grouped = df.groupby("stock_code")
        df["ma5"] = grouped["close"].transform(
            lambda x: x.rolling(5, min_periods=5).mean()
        )
        df["ma10"] = grouped["close"].transform(
            lambda x: x.rolling(10, min_periods=10).mean()
        )
        df["ma20"] = grouped["close"].transform(
            lambda x: x.rolling(20, min_periods=20).mean()
        )

        today = df[df["trade_date"] == pd.to_datetime(trade_date).date()]
        if today.empty:
            missing.extend(ma_keys)
            return

        valid = today.dropna(subset=["close", "ma5", "ma10", "ma20"])
        total = len(valid)
        if total == 0:
            missing.extend(ma_keys)
            return

        indicators["pct_above_ma5"] = round(
            float((valid["close"] > valid["ma5"]).sum()) / total * 100, 2,
        )
        indicators["pct_above_ma10"] = round(
            float((valid["close"] > valid["ma10"]).sum()) / total * 100, 2,
        )
        indicators["pct_above_ma20"] = round(
            float((valid["close"] > valid["ma20"]).sum()) / total * 100, 2,
        )
    except Exception:
        logger.warning("MA breadth computation failed", exc_info=True)
        missing.extend(ma_keys)


def _add_composite_ma_position(
    indicators: dict[str, Any], df_hist: pd.DataFrame,
    trade_date: str, missing: list[str],
) -> None:
    """Compute composite (market-average) close and its MAs.

    'Composite close' = average close of all stocks on each date.
    """
    ma_pos_keys = [
        "composite_close_above_ma5", "composite_close_above_ma10",
        "composite_close_above_ma20",
    ]
    try:
        daily = df_hist.groupby("trade_date")["close"].mean().reset_index()
        daily = daily.sort_values("trade_date")
        daily.columns = ["trade_date", "composite_close"]

        daily["composite_ma5"] = daily["composite_close"].rolling(5, min_periods=5).mean()
        daily["composite_ma10"] = daily["composite_close"].rolling(10, min_periods=10).mean()
        daily["composite_ma20"] = daily["composite_close"].rolling(20, min_periods=20).mean()

        td = pd.to_datetime(trade_date).date()
        row = daily[daily["trade_date"] == td]
        if row.empty:
            missing.extend(ma_pos_keys)
            return

        cc = row.iloc[0]["composite_close"]
        ma5 = row.iloc[0]["composite_ma5"]
        ma10 = row.iloc[0]["composite_ma10"]
        ma20 = row.iloc[0]["composite_ma20"]

        if pd.notna(ma5):
            indicators["composite_close_above_ma5"] = bool(cc > ma5)
        else:
            missing.append("composite_close_above_ma5")

        if pd.notna(ma10):
            indicators["composite_close_above_ma10"] = bool(cc > ma10)
        else:
            missing.append("composite_close_above_ma10")

        if pd.notna(ma20):
            indicators["composite_close_above_ma20"] = bool(cc > ma20)
        else:
            missing.append("composite_close_above_ma20")
    except Exception:
        logger.warning("Composite MA computation failed", exc_info=True)
        missing.extend(ma_pos_keys)


def _add_turnover_ratios(
    indicators: dict[str, Any], df_hist: pd.DataFrame,
    trade_date: str, missing: list[str],
) -> None:
    """Compute today's turnover relative to 5-day / 20-day averages."""
    ratio_keys = ["turnover_ratio_5d", "turnover_ratio_20d"]
    try:
        daily_amount = df_hist.groupby("trade_date")["amount"].sum().reset_index()
        daily_amount = daily_amount.sort_values("trade_date")
        daily_amount.columns = ["trade_date", "daily_amount"]

        daily_amount["amount_ma5"] = (
            daily_amount["daily_amount"].rolling(5, min_periods=5).mean()
        )
        daily_amount["amount_ma20"] = (
            daily_amount["daily_amount"].rolling(20, min_periods=20).mean()
        )

        td = pd.to_datetime(trade_date).date()
        row = daily_amount[daily_amount["trade_date"] == td]
        if row.empty:
            missing.extend(ratio_keys)
            return

        today_amt = row.iloc[0]["daily_amount"]
        ma5 = row.iloc[0]["amount_ma5"]
        ma20 = row.iloc[0]["amount_ma20"]

        if pd.notna(ma5) and ma5 > 0:
            indicators["turnover_ratio_5d"] = round(float(today_amt / ma5), 4)
        else:
            missing.append("turnover_ratio_5d")

        if pd.notna(ma20) and ma20 > 0:
            indicators["turnover_ratio_20d"] = round(float(today_amt / ma20), 4)
        else:
            missing.append("turnover_ratio_20d")
    except Exception:
        logger.warning("Turnover ratio computation failed", exc_info=True)
        missing.extend(ratio_keys)


def _add_composite_returns_volatility(
    indicators: dict[str, Any], df_hist: pd.DataFrame, missing: list[str],
) -> None:
    """Compute 5-day / 20-day composite returns and volatility."""
    ret_keys = ["return_5d", "return_20d"]
    vol_keys = ["composite_volatility_5d", "composite_volatility_20d"]
    try:
        daily = df_hist.groupby("trade_date")["close"].mean().reset_index()
        daily = daily.sort_values("trade_date")
        daily.columns = ["trade_date", "composite_close"]
        daily["daily_return"] = daily["composite_close"].pct_change()

        # 5-day return
        if len(daily) >= 5:
            ret_5d = (
                daily["composite_close"].iloc[-1]
                / daily["composite_close"].iloc[-5] - 1
            )
            indicators["return_5d"] = round(float(ret_5d) * 100, 4)
            vol_5d = daily["daily_return"].iloc[-5:].std()
            indicators["composite_volatility_5d"] = round(float(vol_5d) * 100, 4)
        else:
            missing.extend(ret_keys[:1] + vol_keys[:1])

        # 20-day return
        if len(daily) >= 20:
            ret_20d = (
                daily["composite_close"].iloc[-1]
                / daily["composite_close"].iloc[-20] - 1
            )
            indicators["return_20d"] = round(float(ret_20d) * 100, 4)
            vol_20d = daily["daily_return"].iloc[-20:].std()
            indicators["composite_volatility_20d"] = round(float(vol_20d) * 100, 4)
        else:
            missing.extend(ret_keys[1:] + vol_keys[1:])
    except Exception:
        logger.warning("Composite returns/volatility computation failed", exc_info=True)
        missing.extend(ret_keys + vol_keys)


# ── Safe numeric helpers ─────────────────────────────────────────────────────


def _safe_sum(series: pd.Series) -> float:
    """Return sum, or 0.0 on empty / all-NaN."""
    s = series.dropna()
    if s.empty:
        return 0.0
    return round(float(s.sum()), 2)


def _safe_mean(series: pd.Series) -> float | None:
    """Return mean, or None on empty."""
    s = series.dropna()
    if s.empty:
        return None
    return round(float(s.mean()), 4)
