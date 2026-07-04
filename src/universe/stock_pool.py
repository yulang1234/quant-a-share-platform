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

import pandas as pd

from config.settings import get_stock_pool_path
from src.storage.duckdb_repo import get_connection, query_df

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────
REQUIRED_CSV_FIELDS = {"stock_code", "stock_name"}
DEFAULT_POOL = "core_500"
_OVERRIDES_PATH = get_stock_pool_path().parent / "sector_overrides.csv"


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
        "sector": "",
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

    # ── Backfill sector from note (idempotent) ───────────────────────
    # If sector is empty but note contains industry/sector labels (the
    # historical convention), copy them over.  Do NOT clear note.
    empty_sector = raw["sector"].isna() | (raw["sector"].astype(str).str.strip() == "")
    note_has_value = raw["note"].notna() & (raw["note"].astype(str).str.strip() != "")
    mask = empty_sector & note_has_value
    if mask.any():
        raw.loc[mask, "sector"] = raw.loc[mask, "note"]
        logger.info("Backfilled sector from note for %d rows.", mask.sum())

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
        row_sector = str(row.get("sector", ""))

        if existing:
            # Read current row to detect true changes
            cur = con.execute(
                "SELECT stock_name, market, exchange, source, "
                "       is_active, is_blacklisted, note, sector "
                "FROM stock_pool WHERE stock_code = ? AND pool_name = ?",
                [code, pool],
            ).fetchone()

            # Default to same-exchange (order matches SELECT above)
            if (cur[0] == row_name and cur[1] == row_market
                    and cur[2] == row_exchange and cur[3] == row_source
                    and bool(cur[4]) == row_active
                    and bool(cur[5]) == row_blacklisted
                    and cur[6] == row_note
                    and cur[7] == row_sector):
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
                    sector         = ?,
                    updated_at     = ?
                WHERE stock_code = ? AND pool_name = ?
                """,
                [row_name, row_market, row_exchange, row_source,
                 row_active, row_blacklisted, row_note, row_sector,
                 now, code, pool],
            )
            updated += 1
        else:
            con.execute(
                """
                INSERT INTO stock_pool
                    (stock_code, stock_name, market, exchange, pool_name,
                     source, is_active, is_blacklisted, note, sector, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [code, row_name, row_market, row_exchange, pool,
                 row_source, row_active, row_blacklisted, row_note, row_sector,
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


def resolve_stock_sector(stock_code: str, stock_name: str = "") -> dict[str, str]:
    """Resolve sector/industry for a stock from all available sources.

    Priority (first non-empty wins):
    1. Local DuckDB ``stock_pool.sector``
    2. ``sector_overrides.csv`` (manual overrides)
    3. ``core_500.csv`` ``sector`` column
    4. ``core_500.csv`` ``note`` column (historical convention)
    5. AkShare East Money ``stock_individual_info_em``
    6. AkShare CNINFO ``stock_industry_category_cninfo``
    7. AkShare THS (同花顺) industry boards (cached)
    8. Tushare (optional, requires ``TUSHARE_TOKEN`` env var)

    Parameters
    ----------
    stock_code : str
        6-digit code (will be validated).
    stock_name : str, optional
        Hint for THS matching.

    Returns
    -------
    dict
        ``{"sector": str, "sector_source": str}``.
    """
    code = validate_stock_code(stock_code)
    result: dict[str, str] = {"sector": "", "sector_source": "empty"}
    _no_val = {"", "nan", "none", "None"}

    # ── 1. DuckDB ──────────────────────────────────────────────────────
    try:
        row = query_df(
            "SELECT sector FROM stock_pool WHERE stock_code = ? LIMIT 1", [code]
        )
        if not row.empty:
            sec = str(row.iloc[0].get("sector") or "").strip()
            if sec and sec not in _no_val:
                result["sector"] = sec
                result["sector_source"] = "local_db"
                return result
    except Exception:
        logger.debug("resolve_sector: DuckDB failed for %s", code, exc_info=True)

    # ── 2. sector_overrides.csv ────────────────────────────────────────
    try:
        if _OVERRIDES_PATH.exists():
            overrides = pd.read_csv(_OVERRIDES_PATH, dtype={"stock_code": str})
            overrides["stock_code"] = overrides["stock_code"].astype(str).str.zfill(6)
            match = overrides[overrides["stock_code"] == code]
            if not match.empty:
                s = str(match.iloc[0].get("sector", "")).strip()
                if s and s not in _no_val:
                    result["sector"] = s
                    result["sector_source"] = "local_override"
                    return result
    except Exception:
        logger.debug("resolve_sector: overrides failed for %s", code, exc_info=True)

    # ── 3-4. core_500.csv ─────────────────────────────────────────────
    try:
        csv_path = get_stock_pool_path()
        if csv_path.exists():
            raw = pd.read_csv(csv_path, dtype={"stock_code": str})
            raw["stock_code"] = raw["stock_code"].astype(str).str.zfill(6)
            match = raw[raw["stock_code"] == code]
            if not match.empty:
                r = match.iloc[0]
                s = str(r.get("sector", "")).strip()
                if s and s not in _no_val:
                    result["sector"] = s
                    result["sector_source"] = "local_csv_sector"
                    return result
                n = str(r.get("note", "")).strip()
                if n and n not in _no_val:
                    result["sector"] = n
                    result["sector_source"] = "local_csv_note"
                    return result
    except Exception:
        logger.debug("resolve_sector: CSV failed for %s", code, exc_info=True)

    # ── 5-8. Remote APIs ───────────────────────────────────────────────
    try:
        from src.data_source.akshare_client import AkShareClient  # noqa: F811
        sector, source = AkShareClient.resolve_sector_remote(code, stock_name)
        if sector:
            result["sector"] = sector
            result["sector_source"] = source
    except Exception:
        logger.debug("resolve_sector: remote failed for %s", code, exc_info=True)

    return result


def lookup_stock_info(stock_code: str) -> dict[str, str]:
    """Resolve stock name / exchange / sector from local data, then AkShare.

    Priority chain:
    1. DuckDB ``stock_pool`` table
    2. ``core_500.csv`` file
    3. AkShare ``get_stock_basic_info()``
    4. Exchange always inferred from code via :func:`infer_exchange`
    5. Sector resolved via :func:`resolve_stock_sector`

    Returns
    -------
    dict
        ``{"stock_code", "stock_name", "exchange", "sector", "sector_source"}``.
        Empty strings where data is unavailable.  Never raises.
    """
    code = validate_stock_code(stock_code)
    result: dict[str, str] = {
        "stock_code": code,
        "stock_name": "",
        "exchange": infer_exchange(code),
        "sector": "",
        "sector_source": "empty",
    }

    # ── 1. DuckDB ──────────────────────────────────────────────────────
    try:
        row = query_df(
            "SELECT stock_name FROM stock_pool WHERE stock_code = ? LIMIT 1",
            [code],
        )
        if not row.empty:
            name = str(row.iloc[0].get("stock_name") or "")
            if name and name != "待补充":
                result["stock_name"] = name
    except Exception:
        pass

    # ── 2. CSV  ────────────────────────────────────────────────────────
    try:
        csv_path = get_stock_pool_path()
        if csv_path.exists():
            raw = pd.read_csv(csv_path, dtype={"stock_code": str})
            raw["stock_code"] = raw["stock_code"].astype(str).str.zfill(6)
            match = raw[raw["stock_code"] == code]
            if not match.empty and not result["stock_name"]:
                n = str(match.iloc[0].get("stock_name", ""))
                if n and n != "nan" and n != "待补充":
                    result["stock_name"] = n
    except Exception:
        pass

    # ── 3. AkShare (name) ─────────────────────────────────────────────
    try:
        from src.data_source.akshare_client import AkShareClient  # noqa: F811
        if not result["stock_name"]:
            remote = AkShareClient.get_stock_basic_info(code)
            if remote.get("stock_name"):
                result["stock_name"] = remote["stock_name"]
    except Exception:
        logger.debug("AkShare name lookup failed for %s", code, exc_info=True)

    # ── 4. Fallback name ──────────────────────────────────────────────
    if not result["stock_name"]:
        result["stock_name"] = "待补充"

    # ── 5. Sector via multi-source resolver ───────────────────────────
    sector_info = resolve_stock_sector(code, result["stock_name"])
    result["sector"] = sector_info["sector"]
    result["sector_source"] = sector_info["sector_source"]

    return result


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
    sector: str = "",
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
    sector : str, optional
        Industry / sector classification.

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
                note = ?, sector = ?, updated_at = ?
            WHERE stock_code = ? AND pool_name = ?
            """,
            [stock_name, market, exchange, source, note, sector, now, code, pool_name],
        )
        action = "updated"
    else:
        con.execute(
            """
            INSERT INTO stock_pool
                (stock_code, stock_name, market, exchange, pool_name,
                 source, is_active, is_blacklisted, note, sector, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, TRUE, FALSE, ?, ?, ?, ?)
            """,
            [code, stock_name, market, exchange, pool_name, source, note, sector, now, now],
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


# ======================================================================
#  5.  Data repair
# ======================================================================

def repair_stock_pool_data(pool_name: str = DEFAULT_POOL) -> dict[str, int]:
    """One-shot repair of stock pool records.

    Fixes applied (idempotent — safe to run multiple times):

    1. Backfill empty ``sector`` from ``note`` (historical convention).
    2. Replace ``None`` / ``"None"`` sector values with ``""``.
    3. Fix garbled / placeholder stock names via AkShare.
    4. Repair sectors from all sources via :func:`resolve_stock_sector`.

    Does NOT overwrite user-edited sectors or correct names.

    Parameters
    ----------
    pool_name : str
        Pool to repair.

    Returns
    -------
    dict[str, int]
        ``{"sectors_fixed": int, "names_fixed": int, "names_to_fix": int}``
    """
    con = get_connection()
    result: dict[str, int] = {"sectors_fixed": 0, "names_fixed": 0, "names_to_fix": 0}

    # 1. Backfill sector from note
    updated = con.execute(
        "UPDATE stock_pool SET sector = note "
        "WHERE pool_name = ? "
        "  AND (sector IS NULL OR sector = '' OR sector = 'None') "
        "  AND note IS NOT NULL AND note != ''",
        [pool_name],
    ).fetchone()
    if updated:
        result["sectors_fixed"] = int(updated[0])

    # 2. Clear "None" string values & garbled sector placeholders
    con.execute(
        "UPDATE stock_pool SET sector = '' "
        "WHERE sector IN ('None', 'nan', '<NA>') AND pool_name = ?",
        [pool_name],
    )

    # 3. Fix bad stock names via AkShare
    bad_names = con.execute(
        "SELECT stock_code, stock_name FROM stock_pool "
        "WHERE pool_name = ? "
        "  AND (stock_name = '待补充' OR stock_name IS NULL "
        "       OR stock_name = '' OR stock_name = 'None')",
        [pool_name],
    ).fetchall()

    if bad_names:
        try:
            from src.data_source.akshare_client import AkShareClient  # noqa: F811
            for code, _old_name in bad_names:
                try:
                    info = AkShareClient.get_stock_basic_info(code)
                    new_name = info.get("stock_name", "")
                    if new_name:
                        con.execute(
                            "UPDATE stock_pool SET stock_name = ? "
                            "WHERE stock_code = ? AND pool_name = ?",
                            [new_name, str(code), pool_name],
                        )
                        result["names_fixed"] += 1
                        logger.info("Repair: fixed name for %s → %s", code, new_name)
                except Exception:
                    logger.debug("Name repair failed for %s", code, exc_info=True)
        except Exception:
            logger.debug("AkShare unavailable for name repair", exc_info=True)

    result["names_to_fix"] = len(bad_names) - result["names_fixed"]

    # 4. Repair sectors from all sources for rows still missing sector
    empty_sectors = con.execute(
        "SELECT stock_code, stock_name FROM stock_pool "
        "WHERE pool_name = ? "
        "  AND (sector IS NULL OR sector = '' OR sector = 'None')",
        [pool_name],
    ).fetchall()

    for code, name in empty_sectors:
        info = resolve_stock_sector(str(code), str(name) if name else "")
        if info["sector"]:
            con.execute(
                "UPDATE stock_pool SET sector = ? WHERE stock_code = ? AND pool_name = ?",
                [info["sector"], str(code), pool_name],
            )
            result["sectors_fixed"] += 1
            logger.info(
                "Repair: sector for %s → %s [%s]",
                code, info["sector"], info["sector_source"],
            )

    if result["sectors_fixed"]:
        logger.info("Repair: backfilled %d sectors.", result["sectors_fixed"])
    if result["names_fixed"]:
        logger.info("Repair: fixed %d stock names.", result["names_fixed"])
    if result["names_to_fix"]:
        logger.info("Repair: %d stocks still need name fix.", result["names_to_fix"])

    return result
