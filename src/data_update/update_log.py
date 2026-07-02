"""
Update log helpers — record and query data-update operations.

V0.1: skeleton only.
"""

from __future__ import annotations


def log_update_start(task_type: str, stock_code: str) -> int:
    """Insert a 'pending' record into ``data_update_log`` and return its ID.

    TODO(V0.3): implement.

    Returns
    -------
    int
        Log entry ID.
    """
    raise NotImplementedError("Logging will be implemented in V0.3.")


def log_update_finish(log_id: int, status: str, row_count: int = 0, error: str = "") -> None:
    """Mark a log entry as completed (success / error).

    TODO(V0.3): implement.
    """
    raise NotImplementedError("Logging will be implemented in V0.3.")
