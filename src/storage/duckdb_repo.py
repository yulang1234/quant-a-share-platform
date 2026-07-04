"""
DuckDB repository — lightweight wrapper around DuckDB.

Provides connection management, DDL initialisation, and convenience methods
for reading / writing DataFrames.  No ORM — keep it simple.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from config.settings import get_duckdb_path
from src.storage.schema import CREATE_TABLE_SQL

logger = logging.getLogger(__name__)

# Tables that store daily market data (validated against injection)
_DAILY_TABLES = frozenset({"stock_daily_raw", "stock_daily_qfq"})

# ── Module-level singleton (lazy) ───────────────────────────────────
_connection: duckdb.DuckDBPyConnection | None = None


def get_connection(db_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Return (or create) the DuckDB connection singleton.

    Parameters
    ----------
    db_path : Path, optional
        Path to the DuckDB file.  Defaults to the project-configured path.
    """
    global _connection
    if _connection is None:
        path = db_path or get_duckdb_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _connection = duckdb.connect(str(path))
        logger.info("DuckDB connection opened: %s", path)
    return _connection


def close_connection() -> None:
    """Close the DuckDB connection if it is open."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
        logger.info("DuckDB connection closed.")


def init_database(db_path: Path | None = None) -> None:
    """Create all tables defined in ``schema.py`` if they do not exist.

    Safe to call repeatedly (``IF NOT EXISTS`` is used throughout).
    Will NOT destroy existing data.
    """
    con = get_connection(db_path)

    # Auto-migrate V0.1 -> V0.2 if old stock_pool PK is detected
    _migrate_stock_pool_if_needed(con)

    for ddl in CREATE_TABLE_SQL:
        con.execute(ddl)
    _migrate_data_quality_report_if_needed(con)
    _migrate_stock_pool_add_sector(con)
    logger.info("Database initialised (%d tables).", len(CREATE_TABLE_SQL))


def _migrate_stock_pool_if_needed(con: duckdb.DuckDBPyConnection) -> None:
    """Check whether ``stock_pool`` still has the V0.1 single-column PK
    ``(stock_code)`` and, if so, drop and recreate it with the V0.2
    composite PK ``(stock_code, pool_name)``.

    The migration is **idempotent** — it only runs once because the new
    schema is then persisted in the database file.
    """
    if not _table_exists(con, "stock_pool"):
        return  # fresh install, nothing to migrate

    # Probe: the old PK (stock_code) rejects a second row with the same
    # stock_code even if pool_name differs.  The new composite PK accepts it.
    probe_code = "__v0_2_probe__"
    try:
        con.execute(
            "INSERT INTO stock_pool (stock_code, stock_name, pool_name) "
            "VALUES (?, ?, ?)",
            [probe_code, "probe1", "pool_a"],
        )
        con.execute(
            "INSERT INTO stock_pool (stock_code, stock_name, pool_name) "
            "VALUES (?, ?, ?)",
            [probe_code, "probe2", "pool_b"],
        )
    except Exception:
        # Second insert failed -> old single-column PK detected
        logger.warning(
            "Detected V0.1 stock_pool schema (single-column PK). "
            "Dropping and recreating table with composite PK. "
            "Existing data will be lost."
        )
        con.execute("DROP TABLE IF EXISTS stock_pool")
    finally:
        con.execute("DELETE FROM stock_pool WHERE stock_code = ?", [probe_code])


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    """Return True if a table named ``name`` exists in the main schema."""
    r = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = ?",
        [name],
    ).fetchone()
    return r is not None and r[0] > 0


def execute_sql(sql: str, params: list[Any] | None = None) -> duckdb.DuckDBPyConnection:
    """Execute a raw SQL statement.

    Parameters
    ----------
    sql : str
        SQL statement to execute.
    params : list, optional
        Positional parameters for prepared statements.

    Returns
    -------
    duckdb.DuckDBPyConnection
        The connection (useful for chaining).
    """
    con = get_connection()
    if params:
        con.execute(sql, params)
    else:
        con.execute(sql)
    return con


def query_df(sql: str, params: list[Any] | None = None) -> pd.DataFrame:
    """Execute a SQL query and return results as a pandas DataFrame.

    Parameters
    ----------
    sql : str
        SQL SELECT statement.
    params : list, optional
        Positional parameters.

    Returns
    -------
    pd.DataFrame
    """
    con = get_connection()
    if params:
        return con.execute(sql, params).fetchdf()
    return con.execute(sql).fetchdf()


def insert_df(table_name: str, df: pd.DataFrame) -> int:
    """Insert all rows from a DataFrame into a DuckDB table.

    Parameters
    ----------
    table_name : str
        Target table name.
    df : pd.DataFrame
        Data to insert.

    Returns
    -------
    int
        Number of rows inserted (0 if df is empty).
    """
    if df is None or df.empty:
        logger.debug("Empty DataFrame — nothing inserted into %s.", table_name)
        return 0

    con = get_connection()
    columns = ", ".join(df.columns)
    con.execute(f"INSERT INTO {table_name} ({columns}) SELECT * FROM df")
    logger.debug("Inserted %d rows into %s.", len(df), table_name)
    return len(df)


def upsert_daily_data(table_name: str, df: pd.DataFrame) -> int:
    """Upsert daily price data into *table_name*.

    Uses a delete-then-insert strategy for reliability:
      1. Delete existing rows where ``(stock_code, trade_date)`` matches
         any row in *df*.
      2. Insert new rows.

    Parameters
    ----------
    table_name : str
        One of ``"stock_daily_raw"`` or ``"stock_daily_qfq"``.
    df : pd.DataFrame
        Must contain at least ``stock_code`` and ``trade_date`` columns.

    Returns
    -------
    int
        Number of rows inserted.
    """
    if df is None or df.empty:
        return 0

    con = get_connection()

    # Match DataFrame columns to the target table's schema
    table_cols = con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ?",
        [table_name],
    ).fetchdf()["column_name"].tolist()
    insert_cols = [c for c in df.columns if c in table_cols]
    if not insert_cols:
        logger.warning("No matching columns for %s — skipping insert.", table_name)
        return 0
    df_filtered = df[insert_cols]

    # Temp table for set-based operations
    temp_name = f"__upsert_temp_{table_name}__"
    con.execute(f"DROP TABLE IF EXISTS {temp_name}")
    con.execute(f"CREATE TEMPORARY TABLE {temp_name} AS SELECT * FROM df_filtered")

    # Delete existing rows that overlap with the incoming data
    con.execute(f"""
        DELETE FROM {table_name}
        WHERE (stock_code, trade_date) IN (
            SELECT stock_code, trade_date FROM {temp_name}
        )
    """)

    # Insert new data
    cols = ", ".join(insert_cols)
    con.execute(f"INSERT INTO {table_name} ({cols}) SELECT * FROM {temp_name}")
    inserted = len(df_filtered)

    con.execute(f"DROP TABLE IF EXISTS {temp_name}")

    logger.debug(
        "Upserted %d rows into %s (deleted overlapping first).",
        inserted, table_name,
    )
    return inserted


def get_max_trade_date(table_name: str, stock_code: str) -> str | None:
    """Return the latest ``trade_date`` for *stock_code* in *table_name*.

    Parameters
    ----------
    table_name : str
        ``"stock_daily_raw"`` or ``"stock_daily_qfq"``.
    stock_code : str
        6-digit stock code.

    Returns
    -------
    str or None
        ``"YYYY-MM-DD"`` string, or ``None`` if no data exists.

    Raises
    ------
    ValueError
        If *table_name* is not a recognised daily-data table.
    """
    if table_name not in _DAILY_TABLES:
        raise ValueError(
            f"table_name must be one of {sorted(_DAILY_TABLES)}, "
            f"got '{table_name}'"
        )
    con = get_connection()
    result = con.execute(
        f"SELECT MAX(trade_date) FROM {table_name} WHERE stock_code = ?",
        [stock_code],
    ).fetchone()
    val = result[0] if result else None
    if val is None:
        return None
    # DuckDB returns date objects; convert to string
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    return str(val)[:10]


def count_daily_records(table_name: str, stock_code: str | None = None) -> int:
    """Count rows in a daily-data table, optionally filtered by stock.

    Parameters
    ----------
    table_name : str
        ``"stock_daily_raw"`` or ``"stock_daily_qfq"``.
    stock_code : str, optional
        6-digit stock code.

    Returns
    -------
    int
        Row count.

    Raises
    ------
    ValueError
        If *table_name* is not a recognised daily-data table.
    """
    if table_name not in _DAILY_TABLES:
        raise ValueError(
            f"table_name must be one of {sorted(_DAILY_TABLES)}, "
            f"got '{table_name}'"
        )
    con = get_connection()
    if stock_code:
        result = con.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE stock_code = ?",
            [stock_code],
        ).fetchone()
    else:
        result = con.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()
    return int(result[0]) if result else 0


# ── Data-quality helpers ────────────────────────────────────────────────

_QUALITY_REPORT_TABLE = "data_quality_report"


def _migrate_data_quality_report_if_needed(con: duckdb.DuckDBPyConnection) -> None:
    """Add ``adj_type`` column to ``data_quality_report`` if it is missing.

    The column was introduced in V0.5.  Existing tables created by V0.4 or
    earlier do not have it, so we ALTER TABLE to keep the schema compatible
    without losing previously stored rows.
    """
    if not _table_exists(con, _QUALITY_REPORT_TABLE):
        return
    cols = con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ?",
        [_QUALITY_REPORT_TABLE],
    ).fetchdf()["column_name"].tolist()
    if "adj_type" not in cols:
        con.execute(
            f"ALTER TABLE {_QUALITY_REPORT_TABLE} ADD COLUMN adj_type VARCHAR(8)"
        )
        logger.info("Migrated %s: added adj_type column.", _QUALITY_REPORT_TABLE)


def _column_exists(
    con: duckdb.DuckDBPyConnection, table_name: str, column_name: str
) -> bool:
    """Return True if *column_name* exists in *table_name*."""
    r = con.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ? AND column_name = ?",
        [table_name, column_name],
    ).fetchone()
    return r is not None and r[0] > 0


def _migrate_stock_pool_add_sector(con: duckdb.DuckDBPyConnection) -> None:
    """Add ``sector`` column to ``stock_pool`` if it is missing.

    The column was introduced in V0.6.  Existing tables created by V0.5 or
    earlier do not have it, so we ALTER TABLE to keep the schema compatible
    without losing previously stored rows.

    After adding the column, backfill empty ``sector`` values from ``note``
    for rows where the user had stored industry/sector labels in the note
    field.  This is **idempotent** — once ``sector`` is non-empty, it will
    not be overwritten.
    """
    if not _table_exists(con, "stock_pool"):
        return

    added_col = False
    if not _column_exists(con, "stock_pool", "sector"):
        con.execute("ALTER TABLE stock_pool ADD COLUMN sector VARCHAR(128)")
        logger.info("Migrated stock_pool: added sector column.")
        added_col = True

    # Backfill sector from note for existing rows (idempotent).
    # Only fills rows where sector is still empty and note has content.
    updated = con.execute(
        "UPDATE stock_pool SET sector = note "
        "WHERE (sector IS NULL OR sector = '') "
        "  AND note IS NOT NULL AND note != ''"
    ).fetchone()
    if updated and updated[0] > 0:
        logger.info(
            "Migrated stock_pool: backfilled sector from note for %d rows.",
            updated[0],
        )


def insert_quality_report(df: pd.DataFrame) -> int:
    """Insert quality-check issues into ``data_quality_report``.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain at least ``stock_code``, ``check_date``,
        ``issue_type``, ``issue_level``, ``issue_detail`` and ``adj_type``.

    Returns
    -------
    int
        Number of rows inserted.
    """
    if df is None or df.empty:
        return 0

    con = get_connection()

    # Compute sequential IDs starting after the current maximum.
    max_id = con.execute(
        f"SELECT COALESCE(MAX(id), 0) FROM {_QUALITY_REPORT_TABLE}"
    ).fetchone()[0]
    df = df.copy()
    df["id"] = range(max_id + 1, max_id + 1 + len(df))

    if "status" not in df.columns:
        df["status"] = "open"
    if "created_at" not in df.columns:
        df["created_at"] = pd.Timestamp.now()

    # Keep only columns that exist in the target table.
    table_cols = con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ?",
        [_QUALITY_REPORT_TABLE],
    ).fetchdf()["column_name"].tolist()
    insert_cols = [c for c in df.columns if c in table_cols]
    df_out = df[insert_cols]

    cols = ", ".join(insert_cols)
    con.execute(f"INSERT INTO {_QUALITY_REPORT_TABLE} ({cols}) SELECT * FROM df_out")
    logger.info("Inserted %d rows into %s.", len(df_out), _QUALITY_REPORT_TABLE)
    return len(df_out)


def count_quality_issues(
    issue_type: str | None = None,
    stock_code: str | None = None,
    adj_type: str | None = None,
    status: str | None = None,
) -> int:
    """Count rows in ``data_quality_report`` with optional filters."""
    con = get_connection()
    conditions: list[str] = []
    params: list[Any] = []
    if issue_type:
        conditions.append("issue_type = ?")
        params.append(issue_type)
    if stock_code:
        conditions.append("stock_code = ?")
        params.append(stock_code)
    if adj_type:
        conditions.append("adj_type = ?")
        params.append(adj_type)
    if status:
        conditions.append("status = ?")
        params.append(status)

    where = " AND ".join(conditions) if conditions else "1=1"
    result = con.execute(
        f"SELECT COUNT(*) FROM {_QUALITY_REPORT_TABLE} WHERE {where}",
        params,
    ).fetchone()
    return int(result[0]) if result else 0


def query_daily_data(table_name: str, stock_code: str | None = None) -> pd.DataFrame:
    """Return all rows from a daily-data table, optionally filtered by stock.

    Parameters
    ----------
    table_name : str
        ``"stock_daily_raw"`` or ``"stock_daily_qfq"``.
    stock_code : str, optional
        6-digit stock code.

    Returns
    -------
    pd.DataFrame
    """
    if table_name not in _DAILY_TABLES:
        raise ValueError(
            f"table_name must be one of {sorted(_DAILY_TABLES)}, "
            f"got '{table_name}'"
        )
    con = get_connection()
    if stock_code:
        return con.execute(
            f"SELECT * FROM {table_name} WHERE stock_code = ? ORDER BY trade_date",
            [stock_code],
        ).fetchdf()
    return con.execute(f"SELECT * FROM {table_name} ORDER BY stock_code, trade_date").fetchdf()


# ── V0.6 data-repair helpers ─────────────────────────────────────────────

def delete_daily_range(
    table_name: str, stock_code: str,
    start_date: str | None = None, end_date: str | None = None,
) -> int:
    """Delete rows in *table_name* for *stock_code* within a date range.

    Parameters
    ----------
    table_name : str
        ``"stock_daily_raw"`` or ``"stock_daily_qfq"``.
    stock_code : str
        6-digit code.
    start_date : str, optional
        ``"YYYY-MM-DD"`` inclusive.  Omit to delete from the beginning.
    end_date : str, optional
        ``"YYYY-MM-DD"`` inclusive.  Omit to delete to the end.

    Returns
    -------
    int
        Number of rows deleted.

    Raises
    ------
    ValueError
        If *table_name* is not a recognised daily-data table.
    """
    if table_name not in _DAILY_TABLES:
        raise ValueError(
            f"table_name must be one of {sorted(_DAILY_TABLES)}, "
            f"got '{table_name}'"
        )

    con = get_connection()
    conditions = ["stock_code = ?"]
    params: list[Any] = [stock_code]

    if start_date:
        conditions.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= ?")
        params.append(end_date)

    # Count before
    before = con.execute(
        f"SELECT COUNT(*) FROM {table_name} WHERE {' AND '.join(conditions)}",
        params,
    ).fetchone()[0]

    if before == 0:
        return 0

    con.execute(
        f"DELETE FROM {table_name} WHERE {' AND '.join(conditions)}",
        params,
    )
    logger.debug(
        "delete_daily_range: %s rows deleted from %s for %s",
        before, table_name, stock_code,
    )
    return before


def fetch_daily_range(
    table_name: str, stock_code: str,
    start_date: str | None = None, end_date: str | None = None,
) -> pd.DataFrame:
    """Query daily data for *stock_code* with optional date range.

    Parameters
    ----------
    table_name : str
        ``"stock_daily_raw"`` or ``"stock_daily_qfq"``.
    stock_code : str
        6-digit code.
    start_date : str, optional
        ``"YYYY-MM-DD"``.
    end_date : str, optional
        ``"YYYY-MM-DD"``.

    Returns
    -------
    pd.DataFrame
        Ordered by trade_date.

    Raises
    ------
    ValueError
        If *table_name* is not recognised.
    """
    if table_name not in _DAILY_TABLES:
        raise ValueError(
            f"table_name must be one of {sorted(_DAILY_TABLES)}, "
            f"got '{table_name}'"
        )

    params: list[Any] = [stock_code]
    conditions = ["stock_code = ?"]
    if start_date:
        conditions.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("trade_date <= ?")
        params.append(end_date)

    return query_df(
        f"SELECT * FROM {table_name} WHERE {' AND '.join(conditions)} ORDER BY trade_date",
        params,
    )


def replace_daily_range(
    table_name: str, stock_code: str,
    start_date: str, end_date: str, df: pd.DataFrame,
) -> int:
    """Replace data in *table_name* for *stock_code* within a date range.

    Deletes existing rows in [start_date, end_date], then inserts *df*.
    If *df* is empty, **no data is deleted** (safety).

    Parameters
    ----------
    table_name : str
        ``"stock_daily_raw"`` or ``"stock_daily_qfq"``.
    stock_code : str
        6-digit code.
    start_date : str
        ``"YYYY-MM-DD"``.
    end_date : str
        ``"YYYY-MM-DD"``.
    df : pd.DataFrame
        Replacement data.  Must contain at least ``stock_code`` and
        ``trade_date`` columns.

    Returns
    -------
    int
        Number of rows inserted.

    Raises
    ------
    ValueError
        If *table_name* is not recognised.
    """
    if table_name not in _DAILY_TABLES:
        raise ValueError(
            f"table_name must be one of {sorted(_DAILY_TABLES)}, "
            f"got '{table_name}'"
        )
    if df is None or df.empty:
        logger.debug("replace_daily_range: empty df, skipping.")
        return 0

    con = get_connection()
    con.execute(
        f"DELETE FROM {table_name} "
        "WHERE stock_code = ? AND trade_date >= ? AND trade_date <= ?",
        [stock_code, start_date, end_date],
    )

    # Insert via temp table (reuse upsert pattern but simpler)
    temp = f"__replace_temp_{table_name}__"
    con.execute(f"DROP TABLE IF EXISTS {temp}")
    con.execute(f"CREATE TEMPORARY TABLE {temp} AS SELECT * FROM df")

    table_cols = con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ?",
        [table_name],
    ).fetchdf()["column_name"].tolist()
    insert_cols = [c for c in df.columns if c in table_cols]
    cols_sql = ", ".join(insert_cols)
    con.execute(f"INSERT INTO {table_name} ({cols_sql}) SELECT {cols_sql} FROM {temp}")
    inserted = len(df)
    con.execute(f"DROP TABLE IF EXISTS {temp}")

    logger.debug(
        "replace_daily_range: %d rows inserted into %s for %s",
        inserted, table_name, stock_code,
    )
    return inserted


# ── V0.7 factor helpers ─────────────────────────────────────────────────

_FACTORS_TABLE = "stock_daily_factors"


def upsert_daily_factors(df: pd.DataFrame) -> int:
    """Upsert rows into ``stock_daily_factors``.

    Uses delete-then-insert by (stock_code, trade_date) so that repeated
    runs are idempotent.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain at least ``stock_code`` and ``trade_date``.

    Returns
    -------
    int
        Number of rows inserted (0 if df is empty).
    """
    if df is None or df.empty:
        return 0

    con = get_connection()

    if "stock_code" in df.columns:
        df = df.copy()
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)

    table_cols = con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'main' AND table_name = ?",
        [_FACTORS_TABLE],
    ).fetchdf()["column_name"].tolist()

    insert_cols = [c for c in df.columns if c in table_cols]
    if not insert_cols:
        return 0
    df_out = df[insert_cols]

    temp = "__upsert_factors_temp__"
    con.execute(f"DROP TABLE IF EXISTS {temp}")
    con.execute(f"CREATE TEMPORARY TABLE {temp} AS SELECT * FROM df_out")

    con.execute(f"""
        DELETE FROM {_FACTORS_TABLE}
        WHERE (stock_code, trade_date) IN (
            SELECT stock_code, trade_date FROM {temp}
        )
    """)

    cols = ", ".join(insert_cols)
    con.execute(f"INSERT INTO {_FACTORS_TABLE} ({cols}) SELECT {cols} FROM {temp}")
    con.execute(f"DROP TABLE IF EXISTS {temp}")
    return len(df_out)


def fetch_daily_factors(
    stock_code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Query rows from ``stock_daily_factors``.

    Returns an empty DataFrame if the table does not exist.
    """
    try:
        conditions: list[str] = []
        params: list[Any] = []
        if stock_code:
            conditions.append("stock_code = ?")
            params.append(str(stock_code).zfill(6))
        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM {_FACTORS_TABLE} WHERE {where} ORDER BY stock_code, trade_date"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return query_df(sql, params)
    except Exception:
        return pd.DataFrame()
