"""
Repair planner — read quality reports and produce repair plans.

Builds a DataFrame of recommended repair actions from V0.5
``data_quality_report`` rows.  This module does **not** modify any data.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.storage.duckdb_repo import query_df

logger = logging.getLogger(__name__)

_ISSUE_ACTION_MAP: dict[str, str] = {
    "duplicate_record": "deduplicate",
    "price_anomaly": "refetch_range",
    "missing_trade_date": "refetch_range",
}


def load_quality_reports(
    pool_name: str = "core_500",
    status: str | None = "open",
    stock_code: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Load quality-check results from ``data_quality_report``.

    Parameters
    ----------
    pool_name : str
        Filter by pool (matched against a ``pool_name`` column if present,
        otherwise ignored).
    status : str, optional
        Filter by status (e.g. ``"open"``).  Pass ``None`` for all.
    stock_code : str, optional
        Filter by a single 6-digit stock code.
    limit : int, optional
        Max rows.

    Returns
    -------
    pd.DataFrame
        Possibly empty; never raises.
    """
    conditions: list[str] = []
    params: list[Any] = []

    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if stock_code:
        code = str(stock_code).strip().zfill(6)
        conditions.append("stock_code = ?")
        params.append(code)

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM data_quality_report WHERE {where} ORDER BY check_date DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    try:
        df = query_df(sql, params)
        if not df.empty and "stock_code" in df.columns:
            df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
        return df
    except Exception:
        logger.debug("load_quality_reports: table may not exist yet", exc_info=True)
        return pd.DataFrame()


def build_repair_plan(
    pool_name: str = "core_500",
    issue_type: str | None = None,
    stock_code: str | None = None,
    adj: str = "all",
    limit: int | None = None,
) -> pd.DataFrame:
    """Generate a repair plan from quality reports.

    Parameters
    ----------
    pool_name : str
    issue_type : str, optional
        e.g. ``"duplicate_record"``, ``"price_anomaly"``, ``"missing_trade_date"``.
    stock_code : str, optional
        Single stock code.
    adj : str
        ``"raw"``, ``"qfq"``, or ``"all"``.
    limit : int, optional

    Returns
    -------
    pd.DataFrame
        Columns: stock_code, pool_name, adj_type, issue_type,
        repair_action, start_date, end_date, reason.
    """
    if adj not in ("raw", "qfq", "all"):
        raise ValueError(f"adj must be 'raw', 'qfq', or 'all', got '{adj}'")

    reports = load_quality_reports(
        pool_name=pool_name, status="open",
        stock_code=stock_code, limit=limit,
    )

    if reports.empty:
        return pd.DataFrame(columns=[
            "stock_code", "pool_name", "adj_type", "issue_type",
            "repair_action", "start_date", "end_date", "reason",
        ])

    # Filter by issue_type if specified
    if issue_type and issue_type != "all":
        reports = reports[reports["issue_type"] == issue_type]
        if reports.empty:
            return pd.DataFrame(columns=[
                "stock_code", "pool_name", "adj_type", "issue_type",
                "repair_action", "start_date", "end_date", "reason",
            ])

    # Filter by adj
    if adj != "all" and "adj_type" in reports.columns:
        reports = reports[reports["adj_type"] == adj]

    if reports.empty:
        return pd.DataFrame(columns=[
            "stock_code", "pool_name", "adj_type", "issue_type",
            "repair_action", "start_date", "end_date", "reason",
        ])

    plans: list[dict[str, Any]] = []
    for _, row in reports.iterrows():
        itype = str(row.get("issue_type", "unknown"))
        action = _ISSUE_ACTION_MAP.get(itype, "skipped")
        reason = ""
        if action == "skipped":
            reason = f"unknown issue_type: {itype}"

        adj_type = str(row.get("adj_type", "all"))
        s_date, e_date = infer_repair_range(row, itype)

        plans.append({
            "stock_code": str(row["stock_code"]).zfill(6),
            "pool_name": pool_name,
            "adj_type": adj_type,
            "issue_type": itype,
            "repair_action": action,
            "start_date": s_date,
            "end_date": e_date,
            "reason": reason,
        })

    plan_df = pd.DataFrame(plans)
    # Deduplicate by stock_code + adj_type + repair_action
    if not plan_df.empty:
        plan_df = plan_df.drop_duplicates(
            subset=["stock_code", "adj_type", "repair_action"]
        ).reset_index(drop=True)

    if limit and len(plan_df) > limit:
        plan_df = plan_df.head(limit)

    return plan_df


def infer_repair_range(
    report_row: pd.Series, issue_type: str | None = None,
) -> tuple[str | None, str | None]:
    """Infer a date range for repair from a quality report row.

    Returns ``(start_date, end_date)`` as ``"YYYY-MM-DD"`` strings,
    or ``(None, None)`` if inference is not possible.
    """
    s_date: str | None = None
    e_date: str | None = None

    # Check for explicit start/end columns
    for col in ("start_date", "min_date"):
        val = report_row.get(col)
        if val and pd.notna(val):
            s_date = str(val)[:10]

    for col in ("end_date", "max_date"):
        val = report_row.get(col)
        if val and pd.notna(val):
            e_date = str(val)[:10]

    # If a single trade_date is present, expand to +/- 3 days
    if not s_date:
        td = report_row.get("check_date") or report_row.get("trade_date")
        if td and pd.notna(td):
            base = pd.Timestamp(str(td)[:10])
            s_date = (base - pd.Timedelta(days=3)).strftime("%Y-%m-%d")
            e_date = (base + pd.Timedelta(days=3)).strftime("%Y-%m-%d")

    return s_date, e_date
