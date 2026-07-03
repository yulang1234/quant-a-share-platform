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
