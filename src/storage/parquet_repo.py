"""
Parquet repository -- lightweight read / write helper for partitioned Parquet files.

Provides per-stock daily data persistence for both raw and QFQ data.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from config.settings import get_parquet_root
from src.data_source.akshare_client import AkShareClient

logger = logging.getLogger(__name__)

# ── Helpers ─────────────────────────────────────────────────────────────

_VALID_ADJ_TYPES = frozenset({"raw", "qfq"})

_PARQUET_DIRS: dict[str, str] = {
    "raw": "dwd/daily_raw",
    "qfq": "dwd/daily_qfq",
}


def _validate_adj_type(adj_type: str) -> None:
    """Raise ``ValueError`` if *adj_type* is not ``"raw"`` or ``"qfq"``."""
    if adj_type not in _VALID_ADJ_TYPES:
        raise ValueError(
            f"adj_type must be 'raw' or 'qfq', got '{adj_type}'"
        )


def _get_file_path(stock_code: str, adj_type: str) -> Path:
    """Return the absolute path for a stock's daily Parquet file.

    Parameters
    ----------
    stock_code : str
        6-digit stock code (will be normalised).
    adj_type : str
        ``"raw"`` or ``"qfq"``.

    Returns
    -------
    Path
    """
    code = AkShareClient.normalize_code(stock_code)
    _validate_adj_type(adj_type)
    rel_dir = _PARQUET_DIRS[adj_type]
    return get_parquet_root() / rel_dir / f"{code}.parquet"


# ── Public functions ────────────────────────────────────────────────────


def save_daily_parquet(
    df: pd.DataFrame,
    stock_code: str,
    adj_type: str,
) -> int:
    """Save (or merge) daily data for one stock to a Parquet file.

    If the file already exists, the old data is read, merged with the new
    data, de-duplicated by ``(stock_code, trade_date)``, sorted by
    ``trade_date``, and written back.

    .. note::

       The input *df* is **not** modified by this function; a copy is made
       internally.

    Parameters
    ----------
    df : pd.DataFrame
        Daily data for the stock.
    stock_code : str
        6-digit stock code.
    adj_type : str
        ``"raw"`` or ``"qfq"``.

    Returns
    -------
    int
        Total number of rows in the file after merging.
    """
    code = AkShareClient.normalize_code(stock_code)
    _validate_adj_type(adj_type)
    path = _get_file_path(code, adj_type)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Work on a copy to avoid mutating the caller's DataFrame
    data = df.copy() if df is not None else None

    if data is not None and not data.empty:
        data["stock_code"] = code
        # Ensure trade_date is date type
        if "trade_date" in data.columns and not pd.api.types.is_datetime64_any_dtype(data["trade_date"]):
            data["trade_date"] = pd.to_datetime(data["trade_date"]).dt.date

    if path.exists():
        existing = pd.read_parquet(path)
        if data is not None and not data.empty:
            combined = pd.concat([existing, data], ignore_index=True)
        else:
            combined = existing
    else:
        if data is None or data.empty:
            combined = data if data is not None else pd.DataFrame()
        else:
            combined = data

    if not combined.empty:
        # Normalise trade_date to a consistent type for reliable dedup
        if "trade_date" in combined.columns:
            combined["trade_date"] = pd.to_datetime(combined["trade_date"]).dt.date
        # De-duplicate by (stock_code, trade_date)
        combined = combined.drop_duplicates(
            subset=["stock_code", "trade_date"], keep="last"
        )
        # Sort by trade_date
        if "trade_date" in combined.columns:
            combined = combined.sort_values("trade_date").reset_index(drop=True)

        combined.to_parquet(path, index=False)
        total_rows = len(combined)
    else:
        pd.DataFrame().to_parquet(path, index=False)
        total_rows = 0

    logger.debug(
        "Parquet saved: %s (adj=%s) -- %d rows", path.name, adj_type, total_rows,
    )
    return total_rows


def read_daily_parquet(stock_code: str, adj_type: str) -> pd.DataFrame:
    """Read daily Parquet data for one stock.

    Parameters
    ----------
    stock_code : str
        6-digit stock code.
    adj_type : str
        ``"raw"`` or ``"qfq"``.

    Returns
    -------
    pd.DataFrame
        Empty DataFrame if the file does not exist.
    """
    code = AkShareClient.normalize_code(stock_code)
    _validate_adj_type(adj_type)
    path = _get_file_path(code, adj_type)

    if not path.exists():
        logger.debug("Parquet file not found: %s", path)
        return pd.DataFrame()

    return pd.read_parquet(path)


# ── Legacy helpers (kept for backward compatibility) ────────────────────


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
