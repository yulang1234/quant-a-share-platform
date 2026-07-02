"""
Stock filters — screen out unwanted stocks before processing.

Filters are designed to be composable: each one takes a DataFrame and
returns a filtered copy.  Missing columns are handled gracefully so that
pipelines can be run incrementally.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def filter_st_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """Remove stocks whose names suggest ST / *ST / SST status.

    Expects a ``stock_name`` column.  If absent the DataFrame is returned
    unchanged with a warning.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``stock_name``.

    Returns
    -------
    pd.DataFrame
    """
    if "stock_name" not in df.columns:
        logger.warning("filter_st_stocks skipped: no 'stock_name' column.")
        return df

    pattern = r"^(?:\*ST|ST|SST)"
    before = len(df)
    result = df[~df["stock_name"].str.contains(pattern, na=False)].copy()
    removed = before - len(result)
    if removed:
        logger.info("filter_st_stocks removed %d ST stocks.", removed)
    return result


def filter_new_stocks(
    df: pd.DataFrame,
    list_date_col: str = "list_date",
    min_days: int = 180,
) -> pd.DataFrame:
    """Remove stocks listed for fewer than ``min_days``.

    Parameters
    ----------
    df : pd.DataFrame
        Should contain ``list_date_col`` (date or datetime).
    list_date_col : str
        Column name for the listing date.
    min_days : int
        Minimum number of days since listing.

    Returns
    -------
    pd.DataFrame
        The original DataFrame if the required column is absent.
    """
    if list_date_col not in df.columns:
        logger.warning(
            "filter_new_stocks skipped: column '%s' not found.", list_date_col
        )
        return df

    from datetime import datetime

    df = df.copy()
    df[list_date_col] = pd.to_datetime(df[list_date_col], errors="coerce")
    cutoff = datetime.now()
    df["_days_since_listing"] = (cutoff - df[list_date_col]).dt.days
    before = len(df)
    result = df[df["_days_since_listing"] >= min_days].drop(columns=["_days_since_listing"])
    removed = before - len(result)
    if removed:
        logger.info("filter_new_stocks removed %d new stocks.", removed)
    return result


def filter_low_liquidity(
    df: pd.DataFrame,
    amount_col: str = "amount_mean_20",
    min_amount: float = 100_000_000,  # 1 亿
) -> pd.DataFrame:
    """Remove stocks with low 20-day average trading amount.

    Parameters
    ----------
    df : pd.DataFrame
        Should contain ``amount_col``.
    amount_col : str
    min_amount : float
        Minimum average amount in yuan.

    Returns
    -------
    pd.DataFrame
    """
    if amount_col not in df.columns:
        logger.warning(
            "filter_low_liquidity skipped: column '%s' not found.", amount_col
        )
        return df

    before = len(df)
    result = df[df[amount_col] >= min_amount].copy()
    removed = before - len(result)
    if removed:
        logger.info("filter_low_liquidity removed %d low-liquidity stocks.", removed)
    return result


def filter_suspended_stocks(
    df: pd.DataFrame,
    status_col: str = "status",
) -> pd.DataFrame:
    """Remove stocks whose trading status indicates a suspension.

    Parameters
    ----------
    df : pd.DataFrame
        Should contain ``status_col``.
    status_col : str

    Returns
    -------
    pd.DataFrame
    """
    if status_col not in df.columns:
        logger.warning(
            "filter_suspended_stocks skipped: column '%s' not found.", status_col
        )
        return df

    suspended_keywords = ["suspended", "停牌", "暂停上市", "终止上市"]
    before = len(df)
    mask = df[status_col].astype(str).str.lower().str.contains(
        "|".join(suspended_keywords), na=False
    )
    result = df[~mask].copy()
    removed = before - len(result)
    if removed:
        logger.info("filter_suspended_stocks removed %d suspended stocks.", removed)
    return result


def apply_basic_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience: apply the four basic filters in sequence.

    Each filter is applied only if the required column exists — the
    pipeline never raises for missing columns.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame
    """
    result = df.copy()
    for filt in (filter_st_stocks, filter_new_stocks,
                 filter_low_liquidity, filter_suspended_stocks):
        result = filt(result)
    return result
