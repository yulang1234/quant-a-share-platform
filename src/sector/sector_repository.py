"""V1.5.3 sector repository — DuckDB CRUD for sector_basic and stock_sector_map.

Uses the existing ``query_df`` / ``duckdb_repo`` patterns.
All operations are idempotent (upsert via delete-then-insert).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

from src.storage.duckdb_repo import get_connection

logger = logging.getLogger(__name__)

_TABLE_SECTOR_BASIC = "sector_basic"
_TABLE_STOCK_SECTOR_MAP = "stock_sector_map"


# ── Sector Basic CRUD ──────────────────────────────────────────────────────


def upsert_sector_basic(df: pd.DataFrame) -> int:
    """Upsert rows into ``sector_basic``.

    Uses delete-then-insert by ``sector_code`` so that repeated syncs
    are idempotent.
    """
    if df is None or df.empty:
        return 0

    con = get_connection()
    _ensure_table(con, _TABLE_SECTOR_BASIC)

    # Ensure required columns
    df = _normalise_sector_basic_df(df)
    insert_cols = [
        "sector_code", "sector_name", "sector_type", "source",
        "source_sector_code", "description", "is_active", "updated_at",
    ]
    df_out = df[insert_cols]

    temp = "__upsert_sector_basic__"
    con.execute(f"DROP TABLE IF EXISTS {temp}")
    con.execute(f"CREATE TEMPORARY TABLE {temp} AS SELECT * FROM df_out")

    con.execute(f"""
        DELETE FROM {_TABLE_SECTOR_BASIC}
        WHERE sector_code IN (SELECT sector_code FROM {temp})
    """)
    cols = ", ".join(insert_cols)
    con.execute(
        f"INSERT INTO {_TABLE_SECTOR_BASIC} ({cols}) SELECT {cols} FROM {temp}"
    )
    con.execute(f"DROP TABLE IF EXISTS {temp}")
    logger.info("Upserted %d rows into %s.", len(df_out), _TABLE_SECTOR_BASIC)
    return len(df_out)


def get_sector_basic(
    sector_code: str | None = None, sector_name: str | None = None,
) -> pd.DataFrame:
    """Query sector_basic by code or name."""
    from src.storage.duckdb_repo import query_df

    if sector_code:
        return query_df(
            f"SELECT * FROM {_TABLE_SECTOR_BASIC} WHERE sector_code = ?",
            [sector_code],
        )
    if sector_name:
        return query_df(
            f"SELECT * FROM {_TABLE_SECTOR_BASIC} WHERE sector_name = ?",
            [sector_name],
        )
    return query_df(f"SELECT * FROM {_TABLE_SECTOR_BASIC} ORDER BY sector_code")


def list_all_sectors() -> pd.DataFrame:
    """Return all sector_basic rows."""
    from src.storage.duckdb_repo import query_df
    return query_df(
        f"SELECT * FROM {_TABLE_SECTOR_BASIC} WHERE is_active = TRUE ORDER BY sector_code"
    )


# ── Stock-Sector Map CRUD ──────────────────────────────────────────────────


def upsert_stock_sector_map(df: pd.DataFrame) -> int:
    """Upsert rows into ``stock_sector_map``.

    Uses delete-then-insert by ``(stock_code, sector_code, source)``.
    """
    if df is None or df.empty:
        return 0

    con = get_connection()
    _ensure_table(con, _TABLE_STOCK_SECTOR_MAP)

    df = _normalise_stock_sector_map_df(df)
    insert_cols = [
        "stock_code", "stock_name", "sector_code", "sector_name",
        "sector_type", "source", "weight", "is_active",
        "start_date", "end_date", "updated_at",
    ]
    df_out = df[insert_cols]

    temp = "__upsert_stock_sector_map__"
    con.execute(f"DROP TABLE IF EXISTS {temp}")
    con.execute(f"CREATE TEMPORARY TABLE {temp} AS SELECT * FROM df_out")

    con.execute(f"""
        DELETE FROM {_TABLE_STOCK_SECTOR_MAP}
        WHERE (stock_code, sector_code, source) IN (
            SELECT stock_code, sector_code, source FROM {temp}
        )
    """)
    cols = ", ".join(insert_cols)
    con.execute(
        f"INSERT INTO {_TABLE_STOCK_SECTOR_MAP} ({cols}) SELECT {cols} FROM {temp}"
    )
    con.execute(f"DROP TABLE IF EXISTS {temp}")
    logger.info("Upserted %d rows into %s.", len(df_out), _TABLE_STOCK_SECTOR_MAP)
    return len(df_out)


def get_sectors_by_stock(stock_code: str) -> pd.DataFrame:
    """Return all sectors for a given stock_code."""
    from src.storage.duckdb_repo import query_df
    return query_df(
        f"SELECT * FROM {_TABLE_STOCK_SECTOR_MAP} "
        "WHERE stock_code = ? AND is_active = TRUE",
        [str(stock_code).zfill(6)],
    )


def get_stocks_by_sector(
    sector_code: str | None = None, sector_name: str | None = None,
) -> pd.DataFrame:
    """Return all stocks for a given sector."""
    from src.storage.duckdb_repo import query_df
    if sector_code:
        return query_df(
            f"SELECT * FROM {_TABLE_STOCK_SECTOR_MAP} "
            "WHERE sector_code = ? AND is_active = TRUE",
            [sector_code],
        )
    if sector_name:
        return query_df(
            f"SELECT * FROM {_TABLE_STOCK_SECTOR_MAP} "
            "WHERE sector_name = ? AND is_active = TRUE",
            [sector_name],
        )
    return pd.DataFrame()


def count_sector_mappings() -> int:
    """Return total row count in stock_sector_map."""
    from src.storage.duckdb_repo import query_df
    df = query_df(f"SELECT COUNT(*) AS cnt FROM {_TABLE_STOCK_SECTOR_MAP}")
    if df is not None and not df.empty:
        return int(df.iloc[0]["cnt"])
    return 0


def delete_sector_mappings_by_source(source: str) -> int:
    """Delete all mappings for a given source. Returns deleted count."""
    con = get_connection()
    result = con.execute(
        f"DELETE FROM {_TABLE_STOCK_SECTOR_MAP} WHERE source = ?", [source],
    )
    return result.fetchone()[0] if result else 0


def delete_sector_basic_by_source(source: str) -> int:
    """Delete all sector_basic rows for a given source. Returns deleted count."""
    con = get_connection()
    result = con.execute(
        f"DELETE FROM {_TABLE_SECTOR_BASIC} WHERE source = ?", [source],
    )
    return result.fetchone()[0] if result else 0


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_table(con, table_name: str) -> None:
    """Ensure the table exists by running init_database if needed."""
    try:
        con.execute(f"SELECT 1 FROM {table_name} LIMIT 0")
    except Exception:
        from src.storage.duckdb_repo import init_database
        init_database()


def _normalise_sector_basic_df(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing columns with defaults."""
    df = df.copy()
    now = datetime.now().isoformat(timespec="seconds")
    defaults: dict[str, Any] = {
        "sector_type": "unknown",
        "source": "manual",
        "source_sector_code": None,
        "description": None,
        "is_active": True,
        "updated_at": now,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
    if "updated_at" in df.columns:
        df["updated_at"] = df["updated_at"].fillna(now)
    return df


def _normalise_stock_sector_map_df(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing columns with defaults."""
    df = df.copy()
    now = datetime.now().isoformat(timespec="seconds")
    defaults: dict[str, Any] = {
        "stock_name": "",
        "sector_name": "",
        "sector_type": "unknown",
        "source": "manual",
        "weight": 1.0,
        "is_active": True,
        "start_date": None,
        "end_date": None,
        "updated_at": now,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
    if "stock_code" in df.columns:
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
    if "updated_at" in df.columns:
        df["updated_at"] = df["updated_at"].fillna(now)
    return df
