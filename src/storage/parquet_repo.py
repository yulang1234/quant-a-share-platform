"""
Parquet repository — lightweight read / write helper for partitioned Parquet files.

In later versions this will support partitioned writes by date and stock code.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import get_parquet_root


def save_df(df: pd.DataFrame, rel_path: str | Path) -> Path:
    """Write a DataFrame to a Parquet file under the project's parquet root.

    Parameters
    ----------
    df : pd.DataFrame
        Data to persist.
    rel_path : str or Path
        Relative path beneath ``PARQUET_ROOT``, e.g. ``"ods/stock_basic.parquet"``.

    Returns
    -------
    Path
        Absolute path of the written file.
    """
    full = get_parquet_root() / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(full, index=False)
    return full


def read_df(rel_path: str | Path) -> pd.DataFrame:
    """Read a Parquet file into a DataFrame.

    Parameters
    ----------
    rel_path : str or Path
        Relative path beneath ``PARQUET_ROOT``.

    Returns
    -------
    pd.DataFrame
    """
    full = get_parquet_root() / rel_path
    return pd.read_parquet(full)


def path_exists(rel_path: str | Path) -> bool:
    """Check whether a Parquet file exists on disk.

    Parameters
    ----------
    rel_path : str or Path
        Relative path beneath ``PARQUET_ROOT``.

    Returns
    -------
    bool
    """
    full = get_parquet_root() / rel_path
    return full.exists()
