"""V1.5.2 sentiment indicators — read-only computation from ``stock_daily_raw``.

All indicators are derived from individual stock data already persisted in
DuckDB. No network calls, no new data sources, no writes.

Key design decisions
--------------------
* **Approximate limit-up/down** — no persisted limit-status column exists.
  Use ``pct_change >= 9.8`` / ``pct_change <= -9.8`` as approximation.
  Indicators always include ``approximate_limit_up`` / ``approximate_limit_down``
  flags.
* **Approximate consecutive board** — a stock is on an N-board streak when
  its ``pct_change >= 9.8`` on N consecutive trading days ending on (or
  near) the target date.
* **No intraday data** — ``limit_up_broken_rate`` is always listed in
  ``missing_indicator_names``.
* **Graceful degradation** — when historical window data is insufficient,
  relevant fields are omitted and listed in ``missing_indicator_names``.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from src.storage.duckdb_repo import query_df

logger = logging.getLogger(__name__)

# Number of prior trading days needed for 5d averages.
_PRIOR_DAYS_NEEDED = 8

# Columns we need from stock_daily_raw.
_NEEDED_COLS = [
    "stock_code", "trade_date",
    "close", "amount", "pct_change", "amplitude",
]


def compute_sentiment_indicators(trade_date: str) -> dict[str, Any]:
    """Compute all sentiment-cycle indicators for *trade_date*.

    Returns an empty dict when no data exists for the date.
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

    # ── 2. Prior trading dates ─────────────────────────────────────────
    try:
        prior_dates = _get_prior_trade_dates(td, _PRIOR_DAYS_NEEDED)
    except Exception:
        logger.warning("Failed to get prior trade dates for %s", td, exc_info=True)
        prior_dates = pd.DataFrame()

    if prior_dates.empty:
        return _indicators_single_day(df_today)

    min_date = str(prior_dates.min())[:10]
    try:
        df_hist = _fetch_window(min_date, td)
    except Exception:
        logger.warning("Failed to query historical window for %s", td, exc_info=True)
        return _indicators_single_day(df_today)

    if df_hist is None or df_hist.empty:
        return _indicators_single_day(df_today)

    # ── 3. Compute full indicators ─────────────────────────────────────
    return _compute_full_indicators(df_today, df_hist, td, prior_dates)


# ── Data fetching helpers ────────────────────────────────────────────────────


def _fetch_daily_snapshot(trade_date: str) -> pd.DataFrame:
    cols = ", ".join(_NEEDED_COLS)
    return query_df(
        f"SELECT {cols} FROM stock_daily_raw WHERE trade_date = ?",
        [trade_date],
    )


def _get_prior_trade_dates(
    trade_date: str, limit: int,
) -> pd.DataFrame:
    df = query_df(
        "SELECT DISTINCT trade_date FROM stock_daily_raw "
        "WHERE trade_date < ? ORDER BY trade_date DESC LIMIT ?",
        [trade_date, limit],
    )
    if df is None or df.empty:
        return pd.DataFrame()
    return df["trade_date"]


def _fetch_window(start_date: str, end_date: str) -> pd.DataFrame:
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

    limit_up = int((pct >= 9.8).sum())
    limit_down = int((pct <= -9.8).sum())

    missing = [
        "limit_up_count_3d_avg", "limit_down_count_3d_avg",
        "limit_up_count_5d_avg", "limit_down_count_5d_avg",
        "max_consecutive_limit_up_height", "high_board_stock_count",
        "second_board_count", "third_board_count", "above_third_board_count",
        "previous_limit_up_count", "promoted_count", "promotion_rate",
        "yesterday_limit_up_avg_pct_chg", "yesterday_limit_up_median_pct_chg",
        "yesterday_limit_up_positive_ratio", "yesterday_limit_up_big_loss_count",
        "limit_up_broken_rate",
        "strong_stock_loss_effect", "high_board_negative_count",
        "recent_limit_up_big_loss_count",
    ]

    return {
        "valid_stock_count": n_valid,
        "up_count": up,
        "down_count": down,
        "advance_decline_ratio": round(up / max(down, 1), 4),
        "avg_pct_chg": round(float(pct.mean()), 4) if n_valid else 0.0,
        "median_pct_chg": round(float(pct.median()), 4) if n_valid else 0.0,
        "big_gain_count": int((pct >= 5.0).sum()),
        "big_loss_count": int((pct <= -5.0).sum()),
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "approximate_limit_up": True,
        "approximate_limit_down": True,
        "missing_indicator_names": missing,
        "data_note": "仅有单日数据，多日趋势及连板指标不可用",
    }


# ── Full indicator computation ───────────────────────────────────────────────


def _compute_full_indicators(
    df_today: pd.DataFrame,
    df_hist: pd.DataFrame,
    trade_date: str,
    prior_dates: pd.DataFrame,
) -> dict[str, Any]:
    """Compute all sentiment indicators using today + historical data."""
    missing: list[str] = []
    td_dt = pd.to_datetime(trade_date).date()

    # Normalise trade_date column to date for consistent comparison
    df_hist = df_hist.copy()
    df_hist["trade_date"] = pd.to_datetime(df_hist["trade_date"]).dt.date
    df_today = df_today.copy()
    df_today["trade_date"] = pd.to_datetime(df_today["trade_date"]).dt.date

    # Sort prior dates ascending for consecutive-board analysis
    prior_sorted = sorted(pd.to_datetime(prior_dates).dt.date.tolist())
    all_dates = prior_sorted + [td_dt]

    # --- A. Today's basic stats ---
    pct_today = df_today["pct_change"].dropna()
    n_valid = len(pct_today)

    up = int((pct_today > 0).sum())
    down = int((pct_today < 0).sum())

    limit_up_today = int((pct_today >= 9.8).sum())
    limit_down_today = int((pct_today <= -9.8).sum())

    indicators: dict[str, Any] = {
        "valid_stock_count": n_valid,
        "up_count": up,
        "down_count": down,
        "advance_decline_ratio": round(up / max(down, 1), 4),
        "avg_pct_chg": round(float(pct_today.mean()), 4) if n_valid else 0.0,
        "median_pct_chg": round(float(pct_today.median()), 4) if n_valid else 0.0,
        "big_gain_count": int((pct_today >= 5.0).sum()),
        "big_loss_count": int((pct_today <= -5.0).sum()),
        "limit_up_count": limit_up_today,
        "limit_down_count": limit_down_today,
        "approximate_limit_up": True,
        "approximate_limit_down": True,
    }

    # --- B. Multi-day limit up/down averages ---
    _add_multi_day_limit_avgs(indicators, df_hist, all_dates, missing)

    # --- C. Consecutive board analysis ---
    _add_consecutive_board(indicators, df_hist, all_dates, td_dt, missing)

    # --- D. Yesterday limit-up performance & promotion rate ---
    _add_yesterday_limit_up_stats(indicators, df_hist, all_dates, td_dt, missing)

    # --- E. Broken board rate (always missing) ---
    missing.append("limit_up_broken_rate")

    # --- F. Strong stock loss effect ---
    _add_strong_stock_loss_effect(indicators, df_hist, all_dates, td_dt, missing)

    # --- G. Missing indicators ---
    indicators["missing_indicator_names"] = missing

    return indicators


# ── Sub-computations ──────────────────────────────────────────────────────────


def _add_multi_day_limit_avgs(
    indicators: dict[str, Any],
    df_hist: pd.DataFrame,
    all_dates: list,
    missing: list[str],
) -> None:
    """Compute 3d / 5d average limit up/down counts."""
    try:
        daily = df_hist.groupby("trade_date")["pct_change"].apply(list).reset_index()
        daily["limit_up"] = daily["pct_change"].apply(
            lambda xs: sum(1 for x in xs if x is not None and not (
                isinstance(x, float) and np.isnan(x)
            ) and x >= 9.8)
        )
        daily["limit_down"] = daily["pct_change"].apply(
            lambda xs: sum(1 for x in xs if x is not None and not (
                isinstance(x, float) and np.isnan(x)
            ) and x <= -9.8)
        )
        daily = daily.sort_values("trade_date")

        lu_series = daily["limit_up"].values
        ld_series = daily["limit_down"].values

        if len(lu_series) >= 3:
            indicators["limit_up_count_3d_avg"] = round(float(np.mean(lu_series[-3:])), 1)
            indicators["limit_down_count_3d_avg"] = round(float(np.mean(ld_series[-3:])), 1)
        else:
            missing.extend(["limit_up_count_3d_avg", "limit_down_count_3d_avg"])

        if len(lu_series) >= 5:
            indicators["limit_up_count_5d_avg"] = round(float(np.mean(lu_series[-5:])), 1)
            indicators["limit_down_count_5d_avg"] = round(float(np.mean(ld_series[-5:])), 1)
        else:
            missing.extend(["limit_up_count_5d_avg", "limit_down_count_5d_avg"])
    except Exception:
        logger.warning("Multi-day limit avg computation failed", exc_info=True)
        missing.extend([
            "limit_up_count_3d_avg", "limit_down_count_3d_avg",
            "limit_up_count_5d_avg", "limit_down_count_5d_avg",
        ])


def _add_consecutive_board(
    indicators: dict[str, Any],
    df_hist: pd.DataFrame,
    all_dates: list,
    td_dt,
    missing: list[str],
) -> None:
    """Compute max consecutive limit-up height and board counts.

    A stock is on an N-board streak when its pct_change >= 9.8 on
    N consecutive trading days ending on (or near) the target date.
    """
    try:
        df = df_hist.sort_values(["stock_code", "trade_date"])
        df["is_limit_up"] = df["pct_change"] >= 9.8

        # For each stock, find the current consecutive limit-up streak
        # ending on the target date.
        max_height = 0
        board_counts: dict[int, int] = {}  # streak_length -> count

        for code, group in df.groupby("stock_code"):
            group = group.sort_values("trade_date")
            is_lu = group["is_limit_up"].values
            dates = group["trade_date"].values

            # Calculate consecutive limit-up streak ending at target date
            streak = 0
            for i in range(len(dates) - 1, -1, -1):
                if dates[i] > td_dt:
                    continue
                if is_lu[i]:
                    # Check if this date continues the streak
                    if streak == 0 and dates[i] == td_dt:
                        streak = 1
                    elif streak > 0 and i > 0:
                        # Check if the previous row is the prior trading day
                        prev_date = dates[i - 1]
                        expected_prev = _find_prior_date(all_dates, dates[i])
                        if is_lu[i - 1] and prev_date == expected_prev:
                            streak += 1
                            continue
                        # Not continuous, stop
                        break
                break

            if streak > max_height:
                max_height = streak
            if streak >= 2:
                board_counts[streak] = board_counts.get(streak, 0) + 1

        indicators["max_consecutive_limit_up_height"] = max_height
        indicators["high_board_stock_count"] = sum(
            v for k, v in board_counts.items() if k >= 3
        )
        indicators["second_board_count"] = board_counts.get(2, 0)
        indicators["third_board_count"] = board_counts.get(3, 0)
        indicators["above_third_board_count"] = sum(
            v for k, v in board_counts.items() if k > 3
        )
        indicators["approximate_consecutive_board"] = True
    except Exception:
        logger.warning("Consecutive board computation failed", exc_info=True)
        missing.extend([
            "max_consecutive_limit_up_height", "high_board_stock_count",
            "second_board_count", "third_board_count", "above_third_board_count",
        ])


def _add_yesterday_limit_up_stats(
    indicators: dict[str, Any],
    df_hist: pd.DataFrame,
    all_dates: list,
    td_dt,
    missing: list[str],
) -> None:
    """Compute yesterday's limit-up stock performance and promotion rate."""
    try:
        if len(all_dates) < 2:
            missing.extend([
                "previous_limit_up_count", "promoted_count", "promotion_rate",
                "yesterday_limit_up_avg_pct_chg",
                "yesterday_limit_up_median_pct_chg",
                "yesterday_limit_up_positive_ratio",
                "yesterday_limit_up_big_loss_count",
            ])
            return

        yesterday = all_dates[-2]

        df_yesterday = df_hist[df_hist["trade_date"] == yesterday]
        df_today = df_hist[df_hist["trade_date"] == td_dt]

        # Stocks that were limit-up yesterday
        yesterday_lu = df_yesterday[
            df_yesterday["pct_change"] >= 9.8
        ]["stock_code"].unique()
        previous_lu_count = len(yesterday_lu)

        indicators["previous_limit_up_count"] = previous_lu_count
        indicators["approximate_previous_limit_up"] = True

        if previous_lu_count == 0:
            indicators["promoted_count"] = 0
            indicators["promotion_rate"] = 0.0
            indicators["yesterday_limit_up_avg_pct_chg"] = 0.0
            indicators["yesterday_limit_up_median_pct_chg"] = 0.0
            indicators["yesterday_limit_up_positive_ratio"] = 0.0
            indicators["yesterday_limit_up_big_loss_count"] = 0
            indicators["approximate_promotion_rate"] = True
            return

        # Today's performance of yesterday's limit-up stocks
        today_perf = df_today[df_today["stock_code"].isin(yesterday_lu)]
        if today_perf.empty:
            # None of yesterday's limit-up stocks traded today (unlikely but safe)
            indicators["promoted_count"] = 0
            indicators["promotion_rate"] = 0.0
            indicators["yesterday_limit_up_avg_pct_chg"] = 0.0
            indicators["yesterday_limit_up_median_pct_chg"] = 0.0
            indicators["yesterday_limit_up_positive_ratio"] = 0.0
            indicators["yesterday_limit_up_big_loss_count"] = 0
            indicators["approximate_promotion_rate"] = True
            return

        pct = today_perf["pct_change"].dropna()

        # Promotion: stock was limit-up yesterday AND limit-up today
        promoted = int((pct >= 9.8).sum())

        indicators["promoted_count"] = promoted
        indicators["promotion_rate"] = round(promoted / previous_lu_count, 4) if previous_lu_count > 0 else 0.0
        indicators["approximate_promotion_rate"] = True

        if len(pct) > 0:
            indicators["yesterday_limit_up_avg_pct_chg"] = round(float(pct.mean()), 4)
            indicators["yesterday_limit_up_median_pct_chg"] = round(float(pct.median()), 4)
            indicators["yesterday_limit_up_positive_ratio"] = round(
                float((pct > 0).sum()) / len(pct), 4
            )
            indicators["yesterday_limit_up_big_loss_count"] = int((pct <= -5.0).sum())
        else:
            indicators["yesterday_limit_up_avg_pct_chg"] = 0.0
            indicators["yesterday_limit_up_median_pct_chg"] = 0.0
            indicators["yesterday_limit_up_positive_ratio"] = 0.0
            indicators["yesterday_limit_up_big_loss_count"] = 0
    except Exception:
        logger.warning("Yesterday limit-up stats computation failed", exc_info=True)
        missing.extend([
            "previous_limit_up_count", "promoted_count", "promotion_rate",
            "yesterday_limit_up_avg_pct_chg", "yesterday_limit_up_median_pct_chg",
            "yesterday_limit_up_positive_ratio", "yesterday_limit_up_big_loss_count",
        ])


def _add_strong_stock_loss_effect(
    indicators: dict[str, Any],
    df_hist: pd.DataFrame,
    all_dates: list,
    td_dt,
    missing: list[str],
) -> None:
    """Compute strong-stock loss-effect indicators.

    Key checks:
    - High-board stocks (>= 3 consecutive limit-ups) with negative returns today
    - Yesterday's limit-up stocks with big losses today (<= -5%)
    - Top recent gainers showing poor next-day returns
    """
    try:
        df_today = df_hist[df_hist["trade_date"] == td_dt]
        max_height = indicators.get("max_consecutive_limit_up_height", 0)

        if max_height < 3 or df_today.empty:
            indicators["strong_stock_loss_effect"] = False
            indicators["strong_stock_big_loss_count"] = 0
            indicators["high_board_negative_count"] = 0
            indicators["recent_limit_up_big_loss_count"] = 0
            return

        # Find high-board stocks (>= 3 consecutive limit-ups)
        df = df_hist.sort_values(["stock_code", "trade_date"])
        high_board_codes: set[str] = set()

        for code, group in df.groupby("stock_code"):
            group = group.sort_values("trade_date")
            is_lu = group["pct_change"].values
            dates = group["trade_date"].values

            streak = 0
            for i in range(len(dates) - 1, -1, -1):
                if dates[i] > td_dt:
                    continue
                if is_lu[i]:
                    if streak == 0 and dates[i] == td_dt:
                        streak = 1
                    elif streak > 0 and i > 0:
                        if is_lu[i - 1]:
                            streak += 1
                            continue
                    break
                break

            if streak >= 3:
                high_board_codes.add(code)

        if high_board_codes:
            hb_today = df_today[df_today["stock_code"].isin(high_board_codes)]
            hb_pct = hb_today["pct_change"].dropna()

            indicators["high_board_negative_count"] = int((hb_pct < 0).sum()) if len(hb_pct) > 0 else 0
            indicators["strong_stock_big_loss_count"] = int((hb_pct <= -5.0).sum()) if len(hb_pct) > 0 else 0

            # Strong stock loss effect: high-board stocks have significant losses
            indicators["strong_stock_loss_effect"] = (
                indicators["high_board_negative_count"] > len(hb_pct) * 0.4
                or indicators["strong_stock_big_loss_count"] > 0
            ) if len(hb_pct) > 0 else False
        else:
            indicators["strong_stock_loss_effect"] = False
            indicators["strong_stock_big_loss_count"] = 0
            indicators["high_board_negative_count"] = 0

        # Recent limit-up big loss: yesterday's limit-up stocks with big loss today
        indicators["recent_limit_up_big_loss_count"] = indicators.get(
            "yesterday_limit_up_big_loss_count", 0
        )

    except Exception:
        logger.warning("Strong stock loss effect computation failed", exc_info=True)
        missing.extend([
            "strong_stock_loss_effect", "strong_stock_big_loss_count",
            "high_board_negative_count", "recent_limit_up_big_loss_count",
        ])


# ── Helpers ──────────────────────────────────────────────────────────────────


def _find_prior_date(all_dates: list, current) -> any:
    """Find the trading date immediately before *current* in *all_dates*."""
    sorted_dates = sorted(all_dates)
    for i, d in enumerate(sorted_dates):
        if d == current and i > 0:
            return sorted_dates[i - 1]
    return None
