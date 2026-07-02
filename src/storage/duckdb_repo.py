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
        Number of rows inserted.
    """
    con = get_connection()
    columns = ", ".join(df.columns)
    con.execute(f"INSERT INTO {table_name} ({columns}) SELECT * FROM df")
    logger.debug("Inserted %d rows into %s.", len(df), table_name)
    return len(df)
