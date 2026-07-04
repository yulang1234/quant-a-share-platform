"""
Date-range repair — re-fetch daily data for a stock+adj_type+date range.

All operations default to dry-run.  Pass ``confirm=True`` and
``dry_run=False`` to execute real AkShare calls and DB writes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

from src.data_repair.repair_log import write_repair_log
from src.storage.duckdb_repo import (
    count_daily_records,
    delete_daily_range,
    replace_daily_range,
)
from src.storage.parquet_repo import save_daily_parquet

logger = logging.getLogger(__name__)

_VALID_ADJ = frozenset({"raw", "qfq"})


def _validate_adj(adj: str) -> str:
    if adj not in _VALID_ADJ:
        raise ValueError(f"adj must be one of {sorted(_VALID_ADJ)}, got '{adj}'")
    return adj


def refetch_stock_range(
    stock_code: str,
    adj_type: str,
    start_date: str,
    end_date: str,
    dry_run: bool = True,
    confirm: bool = False,
    pool_name: str = "core_500",
) -> dict[str, Any]:
    """Re-fetch daily data for one stock over a date range.

    Parameters
    ----------
    stock_code : str
        6-digit code.
    adj_type : str
        ``"raw"`` or ``"qfq"``.
    start_date : str
        ``"YYYYMMDD"`` or ``"YYYY-MM-DD"``.
    end_date : str
    dry_run : bool
    confirm : bool
    pool_name : str

    Returns
    -------
    dict
        ``{"stock_code", "adj_type", "status", "affected_rows",
           "before_row_count", "after_row_count", "error_message"}``

    Raises
    ------
    ValueError
        If start_date > end_date or adj_type invalid.
    """
    adj_type = _validate_adj(adj_type)
    code = str(stock_code).strip().zfill(6)

    # Normalise dates
    s_date = _norm_date(start_date)
    e_date = _norm_date(end_date)
    if s_date > e_date:
        raise ValueError(
            f"start_date ({start_date}) must be <= end_date ({end_date})"
        )

    table_name = "stock_daily_raw" if adj_type == "raw" else "stock_daily_qfq"
    before_count = count_daily_records(table_name, code)

    if dry_run or not confirm:
        write_repair_log(
            stock_code=code, pool_name=pool_name, adj_type=adj_type,
            issue_type="price_anomaly", repair_action="refetch_range",
            start_date=s_date, end_date=e_date,
            dry_run=True, confirm=confirm, status="dry_run",
            before_row_count=before_count,
        )
        return {
            "stock_code": code,
            "adj_type": adj_type,
            "status": "dry_run",
            "affected_rows": 0,
            "before_row_count": before_count,
            "after_row_count": before_count,
            "error_message": None,
        }

    # Real execution
    try:
        from src.data_source.akshare_client import AkShareClient

        client = AkShareClient()
        start_ak = s_date.replace("-", "")
        end_ak = e_date.replace("-", "")
        df = client.fetch_stock_daily(code, start_ak, end_ak, adj=adj_type)

        if df is None or df.empty:
            write_repair_log(
                stock_code=code, pool_name=pool_name, adj_type=adj_type,
                issue_type="price_anomaly", repair_action="refetch_range",
                start_date=s_date, end_date=e_date,
                dry_run=False, confirm=True, status="skipped",
                before_row_count=before_count,
                error_message="AkShare returned empty data",
            )
            return {
                "stock_code": code, "adj_type": adj_type,
                "status": "skipped", "affected_rows": 0,
                "before_row_count": before_count,
                "after_row_count": before_count,
                "error_message": "AkShare returned empty data",
            }

        inserted = replace_daily_range(table_name, code, s_date, e_date, df)
        after_count = count_daily_records(table_name, code)

        # Update Parquet
        try:
            save_daily_parquet(df, code, adj_type)
        except Exception:
            logger.warning("Parquet update failed for %s (%s)", code, adj_type, exc_info=True)

        write_repair_log(
            stock_code=code, pool_name=pool_name, adj_type=adj_type,
            issue_type="price_anomaly", repair_action="refetch_range",
            start_date=s_date, end_date=e_date,
            dry_run=False, confirm=True, status="success",
            affected_rows=inserted,
            before_row_count=before_count, after_row_count=after_count,
        )
        return {
            "stock_code": code, "adj_type": adj_type,
            "status": "success", "affected_rows": inserted,
            "before_row_count": before_count,
            "after_row_count": after_count,
            "error_message": None,
        }
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        write_repair_log(
            stock_code=code, pool_name=pool_name, adj_type=adj_type,
            issue_type="price_anomaly", repair_action="refetch_range",
            start_date=s_date, end_date=e_date,
            dry_run=False, confirm=True, status="failed",
            before_row_count=before_count,
            error_message=err_msg,
        )
        logger.warning("Refetch failed for %s: %s", code, err_msg)
        return {
            "stock_code": code, "adj_type": adj_type,
            "status": "failed", "affected_rows": 0,
            "before_row_count": before_count,
            "after_row_count": before_count,
            "error_message": err_msg,
        }


def repair_from_plan(
    plan_df: pd.DataFrame,
    dry_run: bool = True,
    confirm: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    """Execute repair actions from a plan DataFrame.

    Parameters
    ----------
    plan_df : pd.DataFrame
        From ``build_repair_plan()``.
    dry_run : bool
    confirm : bool
    limit : int, optional

    Returns
    -------
    dict
        Summary: ``{"planned": int, "dry_run": int, "success": int,
        "failed": int, "skipped": int, "affected_rows": int}``.
    """
    summary = {"planned": 0, "dry_run": 0, "success": 0,
               "failed": 0, "skipped": 0, "affected_rows": 0}

    if plan_df.empty:
        return summary

    rows = plan_df.head(limit) if limit else plan_df
    summary["planned"] = len(rows)

    for _, row in rows.iterrows():
        action = row.get("repair_action", "skipped")
        code = str(row["stock_code"]).zfill(6)
        adj = row.get("adj_type", "all")
        s_date = row.get("start_date")
        e_date = row.get("end_date")

        if action == "deduplicate":
            from src.data_repair.duplicate_repair import deduplicate_daily_table  # noqa: F811
            for tbl in _adj_to_tables(adj):
                result = deduplicate_daily_table(tbl, code, dry_run=dry_run, confirm=confirm)
                _merge_result(summary, result)
        elif action == "refetch_range":
            if not s_date or not e_date:
                write_repair_log(
                    stock_code=code, adj_type=adj,
                    issue_type="price_anomaly", repair_action="refetch_range",
                    dry_run=dry_run, confirm=confirm, status="skipped",
                    error_message="missing date range",
                )
                summary["skipped"] += 1
                continue
            for adj_type in _adj_to_types(adj):
                result = refetch_stock_range(
                    code, adj_type, str(s_date), str(e_date),
                    dry_run=dry_run, confirm=confirm,
                )
                _merge_result(summary, result)
        elif action == "rebuild_parquet":
            from src.data_repair.parquet_repair import rebuild_parquet_from_duckdb  # noqa: F811
            for adj_type in _adj_to_types(adj):
                result = rebuild_parquet_from_duckdb(
                    code, adj_type, dry_run=dry_run, confirm=confirm,
                )
                _merge_result(summary, result)
        else:
            summary["skipped"] += 1

    return summary


def _norm_date(d: str) -> str:
    """Normalise YYYYMMDD or YYYY-MM-DD to YYYY-MM-DD."""
    d = d.replace("-", "").strip()
    if len(d) == 8:
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return d


def _adj_to_tables(adj: str) -> list[str]:
    if adj == "raw":
        return ["stock_daily_raw"]
    if adj == "qfq":
        return ["stock_daily_qfq"]
    return ["stock_daily_raw", "stock_daily_qfq"]


def _adj_to_types(adj: str) -> list[str]:
    if adj in ("raw", "qfq"):
        return [adj]
    return ["raw", "qfq"]


def _merge_result(summary: dict[str, int], result: dict[str, Any]) -> None:
    status = result.get("status", "skipped")
    summary[status] = summary.get(status, 0) + 1
    summary["affected_rows"] += result.get("affected_rows", 0)
