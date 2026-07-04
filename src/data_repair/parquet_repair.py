"""
Parquet repair — rebuild per-stock Parquet files from DuckDB.

All operations default to dry-run.  Pass ``confirm=True`` and
``dry_run=False`` to actually write files.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.data_repair.repair_log import write_repair_log
from src.storage.duckdb_repo import query_df
from src.storage.parquet_repo import save_daily_parquet

logger = logging.getLogger(__name__)

_VALID_ADJ = frozenset({"raw", "qfq"})


def rebuild_parquet_from_duckdb(
    stock_code: str,
    adj_type: str,
    dry_run: bool = True,
    confirm: bool = False,
    pool_name: str = "core_500",
) -> dict[str, Any]:
    """Rebuild a single stock's Parquet file from DuckDB data.

    Parameters
    ----------
    stock_code : str
        6-digit code.
    adj_type : str
        ``"raw"`` or ``"qfq"``.
    dry_run : bool
    confirm : bool
    pool_name : str

    Returns
    -------
    dict
        ``{"stock_code", "adj_type", "status", "row_count", "error_message"}``

    Raises
    ------
    ValueError
        If *adj_type* is invalid.
    """
    if adj_type not in _VALID_ADJ:
        raise ValueError(f"adj_type must be one of {sorted(_VALID_ADJ)}, got '{adj_type}'")

    code = str(stock_code).strip().zfill(6)
    table_name = "stock_daily_raw" if adj_type == "raw" else "stock_daily_qfq"

    # Read from DuckDB
    try:
        df = query_df(
            f"SELECT * FROM {table_name} WHERE stock_code = ? ORDER BY trade_date",
            [code],
        )
    except Exception as exc:
        write_repair_log(
            stock_code=code, pool_name=pool_name, adj_type=adj_type,
            issue_type="coverage", repair_action="rebuild_parquet",
            dry_run=dry_run, confirm=confirm, status="failed",
            error_message=f"{type(exc).__name__}: {exc}",
        )
        return {
            "stock_code": code, "adj_type": adj_type,
            "status": "failed", "row_count": 0,
            "error_message": str(exc),
        }

    row_count = len(df)

    if df.empty:
        write_repair_log(
            stock_code=code, pool_name=pool_name, adj_type=adj_type,
            issue_type="coverage", repair_action="rebuild_parquet",
            dry_run=dry_run, confirm=confirm, status="skipped",
            error_message="no data in DuckDB",
        )
        return {
            "stock_code": code, "adj_type": adj_type,
            "status": "skipped", "row_count": 0, "error_message": None,
        }

    # Deduplicate before writing
    if "stock_code" in df.columns and "trade_date" in df.columns:
        df = df.drop_duplicates(subset=["stock_code", "trade_date"], keep="first")

    if dry_run or not confirm:
        write_repair_log(
            stock_code=code, pool_name=pool_name, adj_type=adj_type,
            issue_type="coverage", repair_action="rebuild_parquet",
            dry_run=True, confirm=confirm, status="dry_run",
            affected_rows=row_count,
        )
        return {
            "stock_code": code, "adj_type": adj_type,
            "status": "dry_run", "row_count": row_count,
            "error_message": None,
        }

    # Real write
    try:
        save_daily_parquet(df, code, adj_type)
        write_repair_log(
            stock_code=code, pool_name=pool_name, adj_type=adj_type,
            issue_type="coverage", repair_action="rebuild_parquet",
            dry_run=False, confirm=True, status="success",
            affected_rows=row_count,
        )
        logger.info("Parquet rebuilt: %s %s -> %d rows", code, adj_type, row_count)
        return {
            "stock_code": code, "adj_type": adj_type,
            "status": "success", "row_count": row_count,
            "error_message": None,
        }
    except Exception as exc:
        write_repair_log(
            stock_code=code, pool_name=pool_name, adj_type=adj_type,
            issue_type="coverage", repair_action="rebuild_parquet",
            dry_run=False, confirm=True, status="failed",
            error_message=f"{type(exc).__name__}: {exc}",
        )
        return {
            "stock_code": code, "adj_type": adj_type,
            "status": "failed", "row_count": 0,
            "error_message": str(exc),
        }


def rebuild_all_parquet_from_duckdb(
    stock_codes: list[str] | None = None,
    adj: str = "all",
    limit: int | None = None,
    dry_run: bool = True,
    confirm: bool = False,
) -> dict[str, int]:
    """Batch-rebuild Parquet files.

    Parameters
    ----------
    stock_codes : list[str], optional
        Specific codes; if ``None``, reads from ``stock_pool``.
    adj : str
        ``"raw"``, ``"qfq"``, or ``"all"``.
    limit : int, optional
        Max stocks.
    dry_run : bool
    confirm : bool

    Returns
    -------
    dict
        ``{"success": int, "failed": int, "skipped": int, "dry_run": int}``
    """
    if stock_codes is None:
        try:
            pool_df = query_df(
                "SELECT stock_code FROM stock_pool WHERE is_active=TRUE "
                "ORDER BY stock_code"
            )
            stock_codes = pool_df["stock_code"].astype(str).str.zfill(6).tolist()
        except Exception:
            stock_codes = []

    if limit:
        stock_codes = stock_codes[:limit]

    adj_types = _adj_to_types(adj)
    summary = {"success": 0, "failed": 0, "skipped": 0, "dry_run": 0}

    for code in stock_codes:
        for adj_t in adj_types:
            result = rebuild_parquet_from_duckdb(
                code, adj_t, dry_run=dry_run, confirm=confirm,
            )
            status = result["status"]
            summary[status] = summary.get(status, 0) + 1

    return summary


def _adj_to_types(adj: str) -> list[str]:
    if adj in ("raw", "qfq"):
        return [adj]
    return ["raw", "qfq"]
