"""
Duplicate repair — find & deduplicate daily K-line data.

All operations default to dry-run.  Pass ``confirm=True`` and
``dry_run=False`` to execute real changes.

Real dedup uses a safe read-dedup-write strategy:
1. Read all rows for the affected stock(s) from DuckDB.
2. Deduplicate in pandas (keep best row per group).
3. Delete **only** those stocks' old data within the target table.
4. Re-insert the deduplicated DataFrame.

This avoids row-by-row DELETEs that could accidentally remove the
"best" row along with duplicates.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.data_repair.repair_log import write_repair_log
from src.storage.duckdb_repo import get_connection, query_df

logger = logging.getLogger(__name__)

_VALID_TABLES = frozenset({"stock_daily_raw", "stock_daily_qfq"})


def find_duplicate_rows(
    table_name: str, stock_code: str | None = None,
) -> pd.DataFrame:
    """Find rows with duplicate ``(stock_code, trade_date)`` keys.

    Parameters
    ----------
    table_name : str
        ``"stock_daily_raw"`` or ``"stock_daily_qfq"``.
    stock_code : str, optional
        6-digit code filter.

    Returns
    -------
    pd.DataFrame
        All rows that participate in a duplicate group.
        Empty DataFrame if no duplicates exist.

    Raises
    ------
    ValueError
        If *table_name* is invalid.
    """
    if table_name not in _VALID_TABLES:
        raise ValueError(
            f"table_name must be one of {sorted(_VALID_TABLES)}, got '{table_name}'"
        )

    code_filter = ""
    params: list[Any] = []
    if stock_code:
        code = str(stock_code).strip().zfill(6)
        code_filter = "WHERE stock_code = ?"
        params.append(code)

    sql = f"""
        SELECT * FROM {table_name}
        WHERE (stock_code, trade_date) IN (
            SELECT stock_code, trade_date
            FROM {table_name}
            {code_filter}
            GROUP BY stock_code, trade_date
            HAVING COUNT(*) > 1
        )
        ORDER BY stock_code, trade_date
    """
    return query_df(sql, params)


def _dedup_df(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate *df* keeping the best row per (stock_code, trade_date).

    Best = most non-null fields; ties go to the last row.
    """
    if df.empty:
        return df
    df = df.copy()
    df["__non_null__"] = df.notna().sum(axis=1)
    # Sort so the best row comes last within each group
    df = df.sort_values("__non_null__")
    result = df.drop_duplicates(
        subset=["stock_code", "trade_date"], keep="last",
    ).drop(columns=["__non_null__"])
    return result.reset_index(drop=True)


def deduplicate_daily_table(
    table_name: str,
    stock_code: str | None = None,
    dry_run: bool = True,
    confirm: bool = False,
    pool_name: str = "core_500",
) -> dict[str, Any]:
    """Remove duplicate ``(stock_code, trade_date)`` rows.

    Safe read-dedup-write strategy:
    1. Find which stocks have duplicates.
    2. Read their full data from DuckDB.
    3. Deduplicate in pandas.
    4. Delete old data for only those stocks.
    5. Re-insert deduplicated data.

    Parameters
    ----------
    table_name : str
    stock_code : str, optional
    dry_run : bool
    confirm : bool
    pool_name : str

    Returns
    -------
    dict
    """
    if table_name not in _VALID_TABLES:
        raise ValueError(
            f"table_name must be one of {sorted(_VALID_TABLES)}, got '{table_name}'"
        )

    con = get_connection()

    # 1. Find which stocks have duplicates
    dup_df = find_duplicate_rows(table_name, stock_code)
    if dup_df.empty:
        before_all = int(con.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0])
        write_repair_log(
            stock_code=stock_code, pool_name=pool_name,
            adj_type="raw" if "raw" in table_name else "qfq",
            issue_type="duplicate", repair_action="deduplicate",
            dry_run=dry_run, confirm=confirm, status="skipped",
            before_row_count=before_all, after_row_count=before_all,
        )
        return {
            "status": "skipped",
            "duplicate_groups": 0,
            "affected_rows": 0,
            "before_row_count": before_all,
            "after_row_count": before_all,
        }

    affected_codes = dup_df["stock_code"].unique().tolist()
    dup_groups = dup_df.groupby(["stock_code", "trade_date"])
    dup_group_count = len(dup_groups)
    affected = len(dup_df) - dup_group_count

    # 2. Dry-run / no-confirm: preview only
    if dry_run or not confirm:
        before_all = int(con.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0])
        write_repair_log(
            stock_code=stock_code, pool_name=pool_name,
            adj_type="raw" if "raw" in table_name else "qfq",
            issue_type="duplicate", repair_action="deduplicate",
            dry_run=True, confirm=confirm, status="dry_run",
            affected_rows=affected,
            before_row_count=before_all,
        )
        return {
            "status": "dry_run",
            "duplicate_groups": dup_group_count,
            "affected_rows": affected,
            "before_row_count": before_all,
            "after_row_count": before_all,
        }

    # 3. Real execution: read-dedup-write for each affected stock
    total_before = 0
    total_after = 0

    for code in affected_codes:
        c = str(code).zfill(6)

        # Read all rows for this stock
        before_df = query_df(
            f"SELECT * FROM {table_name} WHERE stock_code = ? ORDER BY trade_date",
            [c],
        )
        before_count = len(before_df)
        total_before += before_count

        if before_df.empty:
            continue

        # Dedup in pandas
        deduped = _dedup_df(before_df)
        after_count = len(deduped)
        total_after += after_count

        if after_count == before_count:
            continue  # no duplicates after all — skip

        # Delete this stock's old data
        con.execute(
            f"DELETE FROM {table_name} WHERE stock_code = ?", [c],
        )
        # Re-insert deduplicated data
        cols = ", ".join(deduped.columns)
        con.execute(
            f"INSERT INTO {table_name} ({cols}) SELECT * FROM deduped",
        )

    removed = total_before - total_after
    write_repair_log(
        stock_code=stock_code, pool_name=pool_name,
        adj_type="raw" if "raw" in table_name else "qfq",
        issue_type="duplicate", repair_action="deduplicate",
        dry_run=False, confirm=True, status="success",
        affected_rows=removed,
        before_row_count=total_before, after_row_count=total_after,
    )
    logger.info(
        "Dedup %s: %d stocks, removed %d rows (%d groups), %d -> %d",
        table_name, len(affected_codes), removed,
        dup_group_count, total_before, total_after,
    )
    return {
        "status": "success",
        "duplicate_groups": dup_group_count,
        "affected_rows": removed,
        "before_row_count": total_before,
        "after_row_count": total_after,
    }
