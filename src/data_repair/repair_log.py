"""
Repair log — write and query ``data_repair_log`` records.

All repair actions (including dry-runs and skipped) should write a log entry
so the full repair history is auditable.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

import pandas as pd

from src.storage.duckdb_repo import get_connection, query_df

logger = logging.getLogger(__name__)

_TABLE = "data_repair_log"


def write_repair_log(
    repair_id: str | None = None,
    stock_code: str | None = None,
    pool_name: str = "core_500",
    adj_type: str = "all",
    issue_type: str = "manual",
    repair_action: str = "plan",
    start_date: str | None = None,
    end_date: str | None = None,
    dry_run: bool = True,
    confirm: bool = False,
    status: str = "planned",
    affected_rows: int = 0,
    before_row_count: int = 0,
    after_row_count: int = 0,
    error_message: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> str:
    """Write one row to ``data_repair_log``.

    Parameters
    ----------
    repair_id : str, optional
        Auto-generated UUID if omitted.
    stock_code : str, optional
        6-digit code; validated to 6-char string if provided.

    Returns
    -------
    str
        The ``repair_id`` of the written row.
    """
    rid = repair_id or str(uuid.uuid4())
    now = datetime.now()

    if stock_code is not None:
        stock_code = str(stock_code).strip().zfill(6)

    con = get_connection()
    try:
        con.execute(
            f"""
            INSERT INTO {_TABLE}
                (repair_id, stock_code, pool_name, adj_type, issue_type,
                 repair_action, start_date, end_date,
                 dry_run, confirm, status,
                 affected_rows, before_row_count, after_row_count,
                 error_message, started_at, finished_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                rid, stock_code, pool_name, adj_type, issue_type,
                repair_action, start_date, end_date,
                dry_run, confirm, status,
                affected_rows, before_row_count, after_row_count,
                error_message,
                started_at or now, finished_at, now,
            ],
        )
        logger.debug("Repair log written: %s action=%s status=%s", rid, repair_action, status)
    except Exception:
        logger.debug("Cannot write repair log (table may not exist)", exc_info=True)
    return rid


def get_recent_repair_logs(limit: int = 100) -> pd.DataFrame:
    """Return recent repair log entries, newest first."""
    try:
        return query_df(
            f"SELECT * FROM {_TABLE} ORDER BY created_at DESC LIMIT ?",
            [limit],
        )
    except Exception:
        return pd.DataFrame()


def get_repair_summary(pool_name: str = "core_500") -> dict[str, Any]:
    """Return summary counts grouped by status and repair_action."""
    try:
        status_df = query_df(
            f"""
            SELECT status, COUNT(*) AS cnt
            FROM {_TABLE} WHERE pool_name = ?
            GROUP BY status ORDER BY cnt DESC
            """,
            [pool_name],
        )
        action_df = query_df(
            f"""
            SELECT repair_action, COUNT(*) AS cnt
            FROM {_TABLE} WHERE pool_name = ?
            GROUP BY repair_action ORDER BY cnt DESC
            """,
            [pool_name],
        )
        total = int(status_df["cnt"].sum()) if not status_df.empty else 0
        return {
            "total_logs": total,
            "by_status": status_df.to_dict("records") if not status_df.empty else [],
            "by_action": action_df.to_dict("records") if not action_df.empty else [],
        }
    except Exception:
        return {"total_logs": 0, "by_status": [], "by_action": []}
