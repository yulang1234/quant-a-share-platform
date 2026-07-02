"""
Stock pool management — validate, load, persist, and query the trading universe.

Provides the full CRUD lifecycle for stock-pool entries:

- Code validation and exchange inference
- CSV import with field normalisation
- Upsert into DuckDB with duplicate prevention
- Status management (activate / deactivate / blacklist)
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from config.settings import get_stock_pool_path
from src.storage.duckdb_repo import get_connection, query_df

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────
REQUIRED_CSV_FIELDS = {"stock_code", "stock_name"}
DEFAULT_POOL = "core_500"


# ── Helpers ─────────────────────────────────────────────────────────────

def _now() -> datetime:
    """Return the current timestamp for ``created_at`` / ``updated_at``."""
    return datetime.now()


# ======================================================================
#  1.  Validation & inference helpers
# ======================================================================

def validate_stock_code(stock_code: str | int) -> str:
    """Normalise and validate a stock code to a 6-digit string.

    Parameters
    ----------
    stock_code : str or int
        Raw stock identifier, e.g. ``1``, ``"000001"``, ``600519``.

    Returns
    -------
    str
        6-digit zero-padded string.

    Raises
    ------
    ValueError
        If the code cannot be represented as exactly 6 digits.
    """
    if isinstance(stock_code, int):
        stock_code = str(stock_code)
        # int input is always zero-padded to 6 digits
        stock_code = stock_code.zfill(6)
        if len(stock_code) != 6:
            raise ValueError(f"Stock code must be 6 digits, got '{stock_code}'")
        return stock_code

    # str input
    stock_code = stock_code.strip()
    if not stock_code.isdigit():
        raise ValueError(f"Stock code must be numeric, got '{stock_code}'")
    if len(stock_code) != 6:
        raise ValueError(
            f"Stock code must be exactly 6 digits, got '{stock_code}' (len={len(stock_code)})"
        )
    return stock_code


def infer_exchange(stock_code: str) -> str:
    """Infer the exchange from a 6-digit A-stock code.

    Rules
    -----
    - 6xxxxx → SH (Shanghai)
    - 0xxxxx → SZ (Shenzhen)
    - 3xxxxx → SZ (Shenzhen ChiNext)
    - 8xxxxx → BJ (Beijing)
    - 4xxxxx → BJ (Beijing)
    - other  → UNKNOWN

    Parameters
    ----------
    stock_code : str
        A 6-digit stock code (already normalised).

    Returns
    -------
    str
        Exchange abbreviation.
    """
    code = stock_code.strip()
    if not code.isdigit() or len(code) != 6:
        return "UNKNOWN"

    prefix = code[0]
    if prefix == "6":
        return "SH"
    if prefix in ("0", "3"):
        return "SZ"
    if prefix in ("8", "4"):
        return "BJ"
    return "UNKNOWN"


def _normalise_bool(value: Any) -> bool:
    """Convert a variety of truthy/falsy representations to a Python bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "y")
    return bool(value)


# ======================================================================
#  2.  CSV load / save
# ======================================================================

def load_stock_pool_from_csv(csv_path: str | Path | None = None) -> pd.DataFrame:
    """Read the stock pool CSV file and return a cleaned DataFrame.

    Steps
    -----
    1.  Read CSV (stock_code as string).
    2.  Validate required fields exist.
    3.  Normalise ``stock_code`` to 6-digit string.
    4.  Fill missing columns with defaults.
    5.  Normalise boolean columns.
    6.  Drop duplicate ``(stock_code, pool_name)`` rows.

    Parameters
    ----------
    csv_path : str or Path, optional
        Absolute or relative path to the CSV file.  Defaults to the
        project-configured path from ``settings.STOCK_POOL_PATH``.

    Returns
    -------
    pd.DataFrame
        Cleaned data ready for database insertion.

    Raises
    ------
    FileNotFoundError
        If the CSV file does not exist.
    ValueError
        If required columns are missing or stock codes are invalid.
    """
    path = Path(csv_path) if csv_path else get_stock_pool_path()
    if not path.exists():
        raise FileNotFoundError(f"Stock pool CSV not found: {path}")

    raw = pd.read_csv(path, dtype={"stock_code": str})
    logger.info("Loaded %d rows from %s", len(raw), path)

    # ── Validate required columns ────────────────────────────────────
    missing = REQUIRED_CSV_FIELDS - set(raw.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    # ── Normalise stock_code ─────────────────────────────────────────
    raw["stock_code"] = raw["stock_code"].apply(validate_stock_code)

    # ── Fill / create default columns ────────────────────────────────
    exchange_defaults = raw["stock_code"].apply(infer_exchange)
    defaults = {
        "market": "A股",
        "exchange": exchange_defaults,
        "pool_name": DEFAULT_POOL,
        "source": "manual",
        "is_active": True,
        "is_blacklisted": False,
        "note": "",
    }
    for col, default_val in defaults.items():
        if col not in raw.columns:
            raw[col] = default_val
        elif raw[col].isna().any():
            # Fill NaN in existing columns
            raw[col] = raw[col].fillna(default_val)

    # ── Normalise booleans ───────────────────────────────────────────
    for col in ("is_active", "is_blacklisted"):
        if col in raw.columns:
            raw[col] = raw[col].apply(_normalise_bool)

    # ── Drop duplicates (stock_code + pool_name) ─────────────────────
    before = len(raw)
    raw = raw.drop_duplicates(subset=["stock_code", "pool_name"], keep="last")
    if len(raw) < before:
        logger.warning("Removed %d duplicate rows from CSV", before - len(raw))

    # ── Ensure string types for key columns ──────────────────────────
    raw["stock_code"] = raw["stock_code"].astype(str)
    raw["stock_name"] = raw["stock_name"].astype(str)

    return raw.reset_index(drop=True)


def save_stock_pool_to_db(df: pd.DataFrame) -> dict[str, int]:
    """Upsert a stock pool DataFrame into the DuckDB ``stock_pool`` table.

    For each row:
    - If ``(stock_code, pool_name)`` already exists → UPDATE.
    - Otherwise → INSERT.

    Parameters
    ----------
    df : pd.DataFrame
        Must include at least ``stock_code`` and ``stock_name``.

    Returns
    -------
    dict[str, int]
        ``{"inserted_count": …, "updated_count": …, "total_count": …}``
    """
    con = get_connection()
    inserted = 0
    updated = 0
    skipped = 0

    for _, row in df.iterrows():
        code = validate_stock_code(row.get("stock_code", ""))
        pool = str(row.get("pool_name", DEFAULT_POOL))

        # Check whether the record already exists
        existing = con.execute(
            "SELECT stock_code FROM stock_pool WHERE stock_code = ? AND pool_name = ?",
            [code, pool],
        ).fetchone()

        # ── Collect row data ──────────────────────────────────────────
        now = _now()
        row_name = str(row.get("stock_name", ""))
        row_market = str(row.get("market", "A股"))
        row_exchange = str(row.get("exchange", infer_exchange(code)))
        row_source = str(row.get("source", "manual"))
        row_active = _normalise_bool(row.get("is_active", True))
        row_blacklisted = _normalise_bool(row.get("is_blacklisted", False))
        row_note = str(row.get("note", ""))

        if existing:
            # Read current row to detect true changes
            cur = con.execute(
                "SELECT stock_name, market, exchange, source, "
                "       is_active, is_blacklisted, note "
                "FROM stock_pool WHERE stock_code = ? AND pool_name = ?",
                [code, pool],
            ).fetchone()

            # Default to same-exchange (order matches SELECT above)
            if (cur[0] == row_name and cur[1] == row_market
                    and cur[2] == row_exchange and cur[3] == row_source
                    and bool(cur[4]) == row_active
                    and bool(cur[5]) == row_blacklisted
                    and cur[6] == row_note):
                skipped += 1
                continue

            con.execute(
                """
                UPDATE stock_pool SET
                    stock_name     = ?,
                    market         = ?,
                    exchange       = ?,
                    source         = ?,
                    is_active      = ?,
                    is_blacklisted = ?,
                    note           = ?,
                    updated_at     = ?
                WHERE stock_code = ? AND pool_name = ?
                """,
                [row_name, row_market, row_exchange, row_source,
                 row_active, row_blacklisted, row_note,
                 now, code, pool],
            )
            updated += 1
        else:
            con.execute(
                """
                INSERT INTO stock_pool
                    (stock_code, stock_name, market, exchange, pool_name,
                     source, is_active, is_blacklisted, note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [code, row_name, row_market, row_exchange, pool,
                 row_source, row_active, row_blacklisted, row_note,
                 now, now],
            )
            inserted += 1

    total = inserted + updated + skipped
    logger.info("Upsert complete: %d inserted, %d updated, %d skipped",
                 inserted, updated, skipped)
    return {
        "inserted_count": inserted,
        "updated_count": updated,
        "skipped_count": skipped,
        "total_count": total,
    }


# ======================================================================
#  3.  Query helpers
# ======================================================================

def get_stock_pool(
    pool_name: str = DEFAULT_POOL,
    include_inactive: bool = True,
    include_blacklisted: bool = True,
) -> pd.DataFrame:
    """Query stocks from the database with optional filtering.

    Parameters
    ----------
    pool_name : str
        Pool name filter (default ``"core_500"``).
    include_inactive : bool
        If ``False``, exclude ``is_active = FALSE`` rows.
    include_blacklisted : bool
        If ``False``, exclude ``is_blacklisted = TRUE`` rows.

    Returns
    -------
    pd.DataFrame
    """
    conditions = ["pool_name = ?"]
    params: list[Any] = [pool_name]

    if not include_inactive:
        conditions.append("is_active = TRUE")
    if not include_blacklisted:
        conditions.append("is_blacklisted = FALSE")

    where = " AND ".join(conditions)
    sql = f"SELECT * FROM stock_pool WHERE {where} ORDER BY stock_code"
    return query_df(sql, params)


def get_active_stock_pool(pool_name: str = DEFAULT_POOL) -> pd.DataFrame:
    """Return only active, non-blacklisted stocks.

    This is the primary function used by V0.3+ data-loading pipelines.

    Parameters
    ----------
    pool_name : str
        Pool name filter.

    Returns
    -------
    pd.DataFrame
        Columns: stock_code, stock_name, market, exchange, pool_name.
    """
    df = query_df(
        """
        SELECT stock_code, stock_name, market, exchange, pool_name
        FROM stock_pool
        WHERE pool_name = ?
          AND is_active = TRUE
          AND is_blacklisted = FALSE
        ORDER BY stock_code
        """,
        [pool_name],
    )
    return df


# ======================================================================
#  4.  Single-stock CRUD
# ======================================================================

def add_stock_to_pool(
    stock_code: str | int,
    stock_name: str,
    market: str = "A股",
    exchange: str | None = None,
    pool_name: str = DEFAULT_POOL,
    source: str = "manual",
    note: str = "",
) -> dict[str, Any]:
    """Add a single stock to the pool (or reactivate if already exists).

    Parameters
    ----------
    stock_code : str or int
        6-digit code (will be normalised).
    stock_name : str
    market : str, optional
    exchange : str, optional
        Auto-inferred if omitted.
    pool_name : str, optional
    source : str, optional
    note : str, optional

    Returns
    -------
    dict
        ``{"success": bool, "action": "inserted"|"updated", "stock_code": str}``
    """
    code = validate_stock_code(stock_code)
    if exchange is None:
        exchange = infer_exchange(code)

    con = get_connection()
    now = _now()
    existing = con.execute(
        "SELECT stock_code FROM stock_pool WHERE stock_code = ? AND pool_name = ?",
        [code, pool_name],
    ).fetchone()

    if existing:
        con.execute(
            """
            UPDATE stock_pool SET
                stock_name = ?, market = ?, exchange = ?, source = ?,
                is_active = TRUE, is_blacklisted = FALSE,
                note = ?, updated_at = ?
            WHERE stock_code = ? AND pool_name = ?
            """,
            [stock_name, market, exchange, source, note, now, code, pool_name],
        )
        action = "updated"
    else:
        con.execute(
            """
            INSERT INTO stock_pool
                (stock_code, stock_name, market, exchange, pool_name,
                 source, is_active, is_blacklisted, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, TRUE, FALSE, ?, ?, ?)
            """,
            [code, stock_name, market, exchange, pool_name, source, note, now, now],
        )
        action = "inserted"

    logger.info("Stock %s (%s) %s.", code, stock_name, action)
    return {"success": True, "action": action, "stock_code": code}


def deactivate_stock(
    stock_code: str | int, pool_name: str = DEFAULT_POOL, note: str | None = None
) -> bool:
    """Set a stock's ``is_active`` to ``False`` (soft-delete).

    The record is preserved; it will be excluded from the active pool.

    Parameters
    ----------
    stock_code : str or int
    pool_name : str
    note : str, optional
        Optional reason.

    Returns
    -------
    bool
        ``True`` if the stock existed and was updated.
    """
    code = validate_stock_code(stock_code)
    return _update_status(
        code, pool_name, is_active=False, note=note,
    )


def activate_stock(
    stock_code: str | int, pool_name: str = DEFAULT_POOL
) -> bool:
    """Set a stock's ``is_active`` to ``True``.

    Parameters
    ----------
    stock_code : str or int
    pool_name : str

    Returns
    -------
    bool
    """
    code = validate_stock_code(stock_code)
    return _update_status(code, pool_name, is_active=True)


def blacklist_stock(
    stock_code: str | int, pool_name: str = DEFAULT_POOL, note: str | None = None
) -> bool:
    """Blacklist a stock.

    Also sets ``is_active = False`` so it is excluded from further
    processing until explicitly removed.

    Parameters
    ----------
    stock_code : str or int
    pool_name : str
    note : str, optional

    Returns
    -------
    bool
    """
    code = validate_stock_code(stock_code)
    return _update_status(
        code, pool_name, is_active=False, is_blacklisted=True, note=note,
    )


def remove_blacklist(
    stock_code: str | int, pool_name: str = DEFAULT_POOL
) -> bool:
    """Remove the blacklist flag from a stock.

    Does **not** automatically reactivate the stock.

    Parameters
    ----------
    stock_code : str or int
    pool_name : str

    Returns
    -------
    bool
    """
    code = validate_stock_code(stock_code)
    return _update_status(code, pool_name, is_blacklisted=False)


def delete_stock_from_pool(
    stock_code: str | int, pool_name: str = DEFAULT_POOL
) -> bool:
    """Physically delete a record from the stock pool.

    Parameters
    ----------
    stock_code : str or int
    pool_name : str

    Returns
    -------
    bool
        ``True`` if a row was actually deleted.
    """
    code = validate_stock_code(stock_code)
    con = get_connection()
    # Check existence first
    exists = con.execute(
        "SELECT COUNT(*) FROM stock_pool WHERE stock_code = ? AND pool_name = ?",
        [code, pool_name],
    ).fetchone()[0] > 0

    if not exists:
        logger.warning("Stock %s not found in pool '%s' — nothing deleted.", code, pool_name)
        return False

    con.execute(
        "DELETE FROM stock_pool WHERE stock_code = ? AND pool_name = ?",
        [code, pool_name],
    )
    logger.info("Stock %s deleted from pool '%s'.", code, pool_name)
    return True


# ── Internal helpers ────────────────────────────────────────────────────

def _update_status(
    stock_code: str,
    pool_name: str,
    is_active: bool | None = None,
    is_blacklisted: bool | None = None,
    note: str | None = None,
) -> bool:
    """Generic status-field updater.

    Sets one or both boolean fields and optionally appends a note.
    """
    sets: list[str] = ["updated_at = ?"]
    params: list[Any] = [_now()]

    if is_active is not None:
        sets.append("is_active = ?")
        params.append(is_active)
    if is_blacklisted is not None:
        sets.append("is_blacklisted = ?")
        params.append(is_blacklisted)
    if note is not None:
        sets.append("note = ?")
        params.append(note)

    params.extend([stock_code, pool_name])
    sql = f"UPDATE stock_pool SET {', '.join(sets)} WHERE stock_code = ? AND pool_name = ?"

    con = get_connection()
    con.execute(sql, params)

    # Verify the update actually matched a row by reading it back
    check = con.execute(
        "SELECT COUNT(*) FROM stock_pool WHERE stock_code = ? AND pool_name = ?",
        [stock_code, pool_name],
    ).fetchone()
    # Note: for some calls (e.g. deactivate) a row that *was* there will
    # still be there; for delete we rely on the caller's rowcount from DELETE.
    updated = (check[0] > 0)

    if updated:
        logger.debug("Stock %s in '%s' status updated.", stock_code, pool_name)
    else:
        logger.warning("Stock %s not found in '%s' — no update.", stock_code, pool_name)
    return updated
