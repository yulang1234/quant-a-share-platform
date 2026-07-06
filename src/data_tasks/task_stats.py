"""V1.4.6 Task statistics CLI — enhanced failure classification.

Usage::

    python -m src.data_tasks.task_stats
"""

from __future__ import annotations

import sys


def _classify_error(error_type: str | None) -> str:
    """Classify error_type into a standardised category (V1.4.6)."""
    if not error_type:
        return "UnknownError"
    et = str(error_type).lower()
    if "empty" in et or "dataempty" in et or "emptydata" in et:
        return "ProviderDataEmptyError"
    if "provider" in et and ("unavailable" in et or "error" in et):
        return "ProviderError"
    if "save" in et:
        return "SaveError"
    if "validation" in et or "validate" in et:
        return "ValidationError"
    if "network" in et or "timeout" in et or "connect" in et:
        return "NetworkError"
    if "rate" in et or "limit" in et:
        return "RateLimitError"
    if "calendar" in et:
        return "CalendarMissing"
    return "UnknownError"


def main() -> int:
    from src.data_tasks.task_repo import DataLoadTaskRepository, DataLoadTaskLogRepository
    from sqlalchemy import func
    repo = DataLoadTaskRepository()
    log_repo = DataLoadTaskLogRepository()

    counts = repo.count_by_status()

    if not counts:
        print("No tasks found.")
        return 0

    # ── Status summary ────────────────────────────────────────────────
    print(f"{'Status':<12} {'Count':>8}")
    print("-" * 22)
    for status in ["pending", "running", "success", "failed", "empty", "skipped"]:
        cnt = counts.get(status, 0)
        print(f"{status:<12} {cnt:>8}")
    print("-" * 22)
    print(f"{'TOTAL':<12} {sum(counts.values()):>8}")

    # ── Failed by error_type (V1.4.6 enhanced) ────────────────────────
    try:
        from src.repositories.meta_db import get_session
        from src.db.schema_meta import DataLoadTask
        s = get_session()
        error_rows = s.query(
            DataLoadTask.error_type, func.count()
        ).filter(
            DataLoadTask.status == "failed",
            DataLoadTask.error_type.isnot(None),
        ).group_by(DataLoadTask.error_type).order_by(func.count().desc()).all()

        if error_rows:
            print(f"\n{'Failed by error_type':<36} {'Count':>8}")
            print("-" * 46)
            for err_type, cnt in error_rows:
                category = _classify_error(err_type)
                print(f"  {err_type:<32} {cnt:>8}  [{category}]")

    except Exception:
        pass

    # ── Failed by provider (from task_log) ────────────────────────────
    try:
        from src.repositories.meta_db import get_session
        from src.db.schema_meta import DataLoadTaskLog
        s2 = get_session()
        prov_rows = s2.query(
            DataLoadTaskLog.provider_used, func.count()
        ).filter(
            DataLoadTaskLog.status_after == "failed",
            DataLoadTaskLog.provider_used.isnot(None),
        ).group_by(DataLoadTaskLog.provider_used).order_by(func.count().desc()).all()

        if prov_rows:
            print(f"\n{'Failed by provider':<28} {'Count':>8}")
            print("-" * 38)
            for prov, cnt in prov_rows:
                print(f"  {prov:<24} {cnt:>8}")

    except Exception:
        pass

    # ── Empty by provider ─────────────────────────────────────────────
    try:
        from src.repositories.meta_db import get_session
        from src.db.schema_meta import DataLoadTaskLog
        s3 = get_session()
        empty_rows = s3.query(
            DataLoadTaskLog.provider_used, func.count()
        ).filter(
            DataLoadTaskLog.status_after == "empty",
            DataLoadTaskLog.provider_used.isnot(None),
        ).group_by(DataLoadTaskLog.provider_used).order_by(func.count().desc()).all()

        if empty_rows:
            print(f"\n{'Empty by provider':<28} {'Count':>8}")
            print("-" * 38)
            for prov, cnt in empty_rows:
                print(f"  {prov:<24} {cnt:>8}")

    except Exception:
        pass

    # ── Recent errors ─────────────────────────────────────────────────
    errors = repo.top_errors(limit=5)
    if errors:
        print(f"\nTop recent errors:")
        for msg, cnt in errors:
            print(f"  {cnt:>4}  {msg[:120]}")

    # ── Retryable / non-retryable ─────────────────────────────────────
    try:
        from src.repositories.meta_db import get_session
        from src.db.schema_meta import DataLoadTask
        s4 = get_session()
        retryable = s4.query(func.count()).filter(
            DataLoadTask.status == "failed",
            DataLoadTask.attempt_count < DataLoadTask.max_attempts,
        ).scalar() or 0
        non_retryable = s4.query(func.count()).filter(
            DataLoadTask.status == "failed",
            DataLoadTask.attempt_count >= DataLoadTask.max_attempts,
        ).scalar() or 0

        print(f"\nRetry status:")
        print(f"  retryable     : {retryable}")
        print(f"  non-retryable : {non_retryable}")
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
