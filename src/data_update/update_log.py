"""
Update log helpers — record and query data-update operations.

Provides functions to write update log entries and query them for monitoring
and retry purposes.  All data is stored in the ``data_update_log`` table.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

from src.storage.duckdb_repo import get_connection, query_df

logger = logging.getLogger(__name__)


def write_update_log(
    stock_code: str,
    task_type: str,
    adj_type: str,
    start_date: str,
    end_date: str,
    row_count: int,
    status: str,
    error_message: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> int:
    """Write an entry to ``data_update_log``.

    Parameters
    ----------
    stock_code : str
        6-digit stock code.
    task_type : str
        e.g. ``"historical_load"``.
    adj_type : str
        ``"raw"`` or ``"qfq"``.
    start_date : str
        ``"YYYYMMDD"`` format.
    end_date : str
        ``"YYYYMMDD"`` format.
    row_count : int
        Number of rows fetched / written.
    status : str
        One of ``"success"``, ``"failed"``, ``"empty"``, ``"skipped"``.
    error_message : str, optional
        Error detail when status is ``"failed"``.
    started_at : datetime, optional
        When the task started.  Defaults to now.
    finished_at : datetime, optional
        When the task finished.  Defaults to now.

    Returns
    -------
    int
        The ID of the newly-inserted log entry.
    """
    con = get_connection()
    now = datetime.now()

    # Generate ID if the table doesn't use auto-increment
    max_id = con.execute("SELECT COALESCE(MAX(id), 0) FROM data_update_log").fetchone()[0]
    new_id = int(max_id) + 1

    con.execute(
        """
        INSERT INTO data_update_log
            (id, stock_code, task_type, adj_type, start_date, end_date,
             row_count, status, error_message, started_at, finished_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            new_id,
            stock_code,
            task_type,
            adj_type,
            _parse_date(start_date),
            _parse_date(end_date),
            row_count,
            status,
            error_message[:1024] if error_message else None,
            started_at or now,
            finished_at or now,
        ],
    )

    logger.debug(
        "Update log written: id=%d, stock=%s, adj=%s, status=%s, rows=%d",
        new_id, stock_code, adj_type, status, row_count,
    )
    return new_id


def get_failed_tasks(
    task_type: str = "historical_load",
    limit: int | None = None,
) -> pd.DataFrame:
    """Query recently failed tasks from the update log.

    De-duplication logic:
    - For the same ``(stock_code, adj_type)``, if a later ``"success"`` entry
      exists, that combination is **not** returned as a failed task.
    - Only the most recent ``"failed"`` entry (per combination) is returned.

    Parameters
    ----------
    task_type : str
    limit : int, optional
        Max number of failed tasks to return.

    Returns
    -------
    pd.DataFrame
        Columns: id, stock_code, adj_type, start_date, end_date,
        error_message, started_at, finished_at.
    """
    sql = """
        WITH failed_only AS (
            -- Get the latest failed entry per (stock_code, adj_type)
            SELECT id, stock_code, adj_type, start_date, end_date,
                   error_message, started_at, finished_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY stock_code, adj_type
                       ORDER BY finished_at DESC, id DESC
                   ) AS rn
            FROM data_update_log
            WHERE task_type = ?
              AND status = 'failed'
        ),
        had_later_success AS (
            -- Find (stock_code, adj_type) pairs that succeeded later
            SELECT DISTINCT stock_code, adj_type
            FROM data_update_log
            WHERE task_type = ?
              AND status = 'success'
        )
        SELECT fo.id, fo.stock_code, fo.adj_type,
               fo.start_date, fo.end_date,
               fo.error_message, fo.started_at, fo.finished_at
        FROM failed_only fo
        LEFT JOIN had_later_success hls
            ON fo.stock_code = hls.stock_code
            AND fo.adj_type = hls.adj_type
        WHERE fo.rn = 1
          AND hls.stock_code IS NULL
        ORDER BY fo.finished_at DESC, fo.id DESC
    """
    params: list[Any] = [task_type, task_type]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))

    return query_df(sql, params)


def get_recent_update_logs(limit: int = 100) -> pd.DataFrame:
    """Query the most recent update log entries.

    Parameters
    ----------
    limit : int, optional
        Number of rows to return (default 100).

    Returns
    -------
    pd.DataFrame
        Columns: id, stock_code, task_type, adj_type, start_date, end_date,
        row_count, status, error_message, started_at, finished_at.
    """
    return query_df(
        """
        SELECT id, stock_code, task_type, adj_type,
               start_date, end_date, row_count, status,
               error_message, started_at, finished_at
        FROM data_update_log
        ORDER BY id DESC
        LIMIT ?
        """,
        [int(limit)],
    )


def get_update_summary(task_type: str = "historical_load") -> dict[str, int]:
    """Return a summary of update log counts by status.

    Parameters
    ----------
    task_type : str

    Returns
    -------
    dict
        Keys: ``"success"``, ``"failed"``, ``"empty"``, ``"skipped"``, ``"total"``.
    """
    df = query_df(
        """
        SELECT status, COUNT(*) AS cnt
        FROM data_update_log
        WHERE task_type = ?
        GROUP BY status
        """,
        [task_type],
    )

    result: dict[str, int] = {
        "success": 0,
        "failed": 0,
        "empty": 0,
        "skipped": 0,
        "total": 0,
    }
    for _, row in df.iterrows():
        s = row["status"]
        c = int(row["cnt"])
        if s in result:
            result[s] = c
        result["total"] += c

    return result


def _parse_date(date_str: str) -> str:
    """Convert ``"YYYYMMDD"`` to date string parsable by DuckDB."""
    d = date_str.replace("-", "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
