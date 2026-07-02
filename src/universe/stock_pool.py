"""
Stock pool management — load, persist, and query the trading universe.

The core 500 (and future custom pools) are managed here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import get_stock_pool_path
from src.storage.duckdb_repo import insert_df, query_df


# ── CSV load / save ─────────────────────────────────────────────────────

def load_stock_pool_from_csv(csv_path: str | Path | None = None) -> pd.DataFrame:
    """Read the stock pool CSV file into a DataFrame.

    Parameters
    ----------
    csv_path : str or Path, optional
        Path to the CSV.  Defaults to the project-configured path.

    Returns
    -------
    pd.DataFrame
    """
    path = Path(csv_path) if csv_path else get_stock_pool_path()
    return pd.read_csv(path, dtype={"stock_code": str})


def save_stock_pool_to_db(df: pd.DataFrame) -> int:
    """Insert (or upsert) stock pool rows into the DuckDB table.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain at least ``stock_code`` and ``stock_name`` columns.

    Returns
    -------
    int
        Number of rows inserted.

    TODO(V0.2): implement proper upsert logic (MERGE).
    """
    return insert_df("stock_pool", df)


# ── Query helpers ───────────────────────────────────────────────────────

def get_active_stock_pool() -> pd.DataFrame:
    """Return all active (non-blacklisted) stocks from the database.

    Returns
    -------
    pd.DataFrame

    TODO(V0.2): add pool_name filtering, caching.
    """
    return query_df(
        "SELECT * FROM stock_pool WHERE is_active = TRUE AND is_blacklisted = FALSE"
    )


def add_stock_to_pool(
    stock_code: str,
    stock_name: str,
    pool_name: str = "core_500",
) -> None:
    """Add a single stock record to the database.

    Parameters
    ----------
    stock_code : str
        6-digit code.
    stock_name : str
        Stock name.
    pool_name : str, optional
        Pool identifier (default ``"core_500"``).

    TODO(V0.2): use MERGE to avoid duplicate-key errors.
    """
    df = pd.DataFrame(
        [
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "pool_name": pool_name,
            }
        ]
    )
    insert_df("stock_pool", df)


def deactivate_stock(stock_code: str) -> None:
    """Mark a stock as inactive.

    Parameters
    ----------
    stock_code : str
        6-digit code.

    TODO(V0.2): implement.
    """
    ...


def blacklist_stock(stock_code: str) -> None:
    """Blacklist a stock so it is excluded from the active pool.

    Parameters
    ----------
    stock_code : str
        6-digit code.

    TODO(V0.2): implement.
    """
    ...
