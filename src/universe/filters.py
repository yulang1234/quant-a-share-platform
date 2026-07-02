"""
Stock filters — screen out unwanted stocks before processing.

Common filters include: ST / *ST stocks, recent IPOs, low-liquidity stocks,
and suspended stocks.

V0.1: all filters are pass-through stubs.
"""

import pandas as pd


def filter_st_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """Remove stocks whose names contain ``ST`` or ``*ST``.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a ``stock_name`` column.

    Returns
    -------
    pd.DataFrame

    TODO(V0.2): implement real ST detection.
    """
    return df  # stub


def filter_new_stocks(df: pd.DataFrame, min_trade_days: int = 60) -> pd.DataFrame:
    """Remove stocks that have been listed for fewer than ``min_trade_days``.

    Parameters
    ----------
    df : pd.DataFrame
    min_trade_days : int
        Minimum number of trading days since listing.

    Returns
    -------
    pd.DataFrame

    TODO(V0.2): implement based on listing_date from stock_basic.
    """
    return df  # stub


def filter_low_liquidity(df: pd.DataFrame) -> pd.DataFrame:
    """Remove stocks whose average daily volume is below a threshold.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame

    TODO(V0.2): implement with configurable threshold.
    """
    return df  # stub


def filter_suspended_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """Remove stocks that are currently suspended from trading.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    pd.DataFrame

    TODO(V0.2): implement by checking recent volume == 0.
    """
    return df  # stub
