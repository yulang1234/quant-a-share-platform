"""V1.4.8 Batch Report — comprehensive report for a single batch.

Usage::

    python -m src.backfill.batch_report --batch-id <batch_id>
"""

from __future__ import annotations

import sys
from typing import Any


def _compute_counts(batch_id: str) -> dict[str, int]:
    """Compute task counts by status, including retryable."""
    counts = {"pending": 0, "running": 0, "success": 0, "failed": 0,
              "empty": 0, "skipped": 0, "retryable": 0, "non_retryable": 0}
    try:
        from src.data_tasks.task_repo import DataLoadTaskRepository
        from src.repositories.meta_db import get_session
        from src.db.schema_meta import DataLoadTask
        from sqlalchemy import func
        s = get_session()
        for st in ("pending", "running", "success", "failed", "empty", "skipped"):
            cnt = s.query(func.count()).filter(
                DataLoadTask.batch_id == batch_id,
                DataLoadTask.status == st,
            ).scalar() or 0
            counts[st] = int(cnt)
        # Compute retryable / non-retryable from failed
        failed_tasks = s.query(DataLoadTask).filter(
            DataLoadTask.batch_id == batch_id,
            DataLoadTask.status == "failed",
        ).all()
        counts["retryable"] = sum(1 for t in failed_tasks if (t.attempt_count or 0) < (t.max_attempts or 5))
        counts["non_retryable"] = len(failed_tasks) - counts["retryable"]
    except Exception:
        pass
    return counts


def _suggested_retry_command(batch_id: str, save_local: bool = False) -> str:
    save = "--save-local" if save_local else "--no-save"
    return (
        f"python -m src.backfill.batch_runner --batch-id {batch_id} "
        f"--status retryable --limit 10 --confirm {save} --allow-core-500-run"
    )


def _risk_warnings(batch_info: dict[str, Any], before_snap, after_snap) -> list[str]:
    """Generate risk warnings based on batch state."""
    warnings = []

    is_real = True
    if after_snap and hasattr(after_snap, 'is_real_calendar'):
        is_real = after_snap.is_real_calendar
    elif before_snap and hasattr(before_snap, 'is_real_calendar'):
        is_real = before_snap.is_real_calendar

    if not is_real:
        warnings.append("Calendar is not real — sync trading calendar first.")

    failed = batch_info.get("failed_count", 0) or 0
    success = batch_info.get("success_count", 0) or 0
    empty = batch_info.get("empty_count", 0) or 0
    total = failed + success + empty

    if failed > 0 and success == 0:
        warnings.append("All tasks failed — stop and investigate Provider before continuing.")
    if total > 0:
        rate = failed / total
        if rate > 0.3:
            warnings.append(f"Failed rate {rate:.1%} > 30% — reduce limit, increase sleep.")
    if empty > 0 and total > 0:
        erate = empty / total
        if erate > 0.5:
            warnings.append("High empty rate — check Provider and stock code mapping.")

    if not batch_info.get("is_real_calendar", True):
        warnings.append("Fallback calendar detected. Coverage may be inaccurate.")

    return warnings


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="V1.4.8 Batch Report")
    p.add_argument("--batch-id", required=True)
    args = p.parse_args()

    from src.backfill.batch_repo import BatchRepository
    repo = BatchRepository()
    batch = repo.get_batch(args.batch_id)
    if batch is None:
        print(f"[ERROR] Batch '{args.batch_id}' not found.")
        return 1

    # Get snapshots
    snapshots = repo.get_batch_snapshots(args.batch_id)
    before_snap = next((s for s in snapshots if s.snapshot_type == "before"), None)
    after_snap = next((s for s in snapshots if s.snapshot_type == "after"), None)

    # Compute coverage delta
    coverage_delta = None
    if before_snap and after_snap:
        br = before_snap.avg_coverage_rate
        ar = after_snap.avg_coverage_rate
        if br is not None and ar is not None:
            coverage_delta = ar - br

    # Task counts
    counts = _compute_counts(args.batch_id)
    total_executed = counts.get("success", 0) + counts.get("failed", 0) + counts.get("empty", 0)
    provider_success_rate = (counts["success"] / total_executed) if total_executed > 0 else None
    provider_failed_rate = (counts["failed"] / total_executed) if total_executed > 0 else None

    # Risk warnings
    batch_info = {
        "batch_id": batch.batch_id, "status": batch.status,
        "success_count": batch.success_count, "failed_count": batch.failed_count,
        "empty_count": batch.empty_count,
        "is_real_calendar": after_snap.is_real_calendar if after_snap else (before_snap.is_real_calendar if before_snap else True),
    }
    risks = _risk_warnings(batch_info, before_snap, after_snap)

    # ── Output ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Batch Report")
    print(f"{'='*60}")
    print(f"  Batch ID          : {batch.batch_id}")
    print(f"  Batch name        : {batch.batch_name}")
    print(f"  Universe          : {batch.universe_name}")
    print(f"  Adj type          : {batch.adj_type}")
    print(f"  Date range        : {batch.start_date} ~ {batch.end_date}")
    print(f"  Status            : {batch.status}")
    print(f"  Max limit         : {batch.max_limit}")
    print(f"  Sleep seconds     : {batch.sleep_seconds}")
    print(f"  Save local        : {batch.save_local}")

    print(f"\n  --- Task Counts ---")
    for st in ["pending", "running", "success", "failed", "empty", "skipped"]:
        print(f"  {st:<18}: {counts.get(st, 0):>6}")
    print(f"  retryable         : {counts.get('retryable', 0):>6}")
    print(f"  non-retryable     : {counts.get('non_retryable', 0):>6}")
    print(f"  total_executed    : {total_executed:>6}")

    # Before snapshot
    if before_snap:
        print(f"\n  --- Before Snapshot ---")
        print(f"  ID: {before_snap.snapshot_id}  stocks: {before_snap.stock_count}  "
              f"complete: {before_snap.complete_count}  partial: {before_snap.partial_count}")
        print(f"  Avg coverage: {before_snap.avg_coverage_rate}  "
              f"real_calendar: {before_snap.is_real_calendar}")
    else:
        print(f"\n  --- Before Snapshot ---")
        print(f"  (none)")

    # After snapshot
    if after_snap:
        print(f"\n  --- After Snapshot ---")
        print(f"  ID: {after_snap.snapshot_id}  stocks: {after_snap.stock_count}  "
              f"complete: {after_snap.complete_count}  partial: {after_snap.partial_count}")
        print(f"  Avg coverage: {after_snap.avg_coverage_rate}  "
              f"calendar: {after_snap.calendar_source}")
    else:
        print(f"\n  --- After Snapshot ---")
        print(f"  (none)")

    # Coverage delta
    if coverage_delta is not None:
        sign = "+" if coverage_delta >= 0 else ""
        print(f"\n  Coverage delta    : {sign}{coverage_delta:.4f}")

    # Provider rates
    if provider_success_rate is not None:
        print(f"  Provider success  : {provider_success_rate:.1%}")
    if provider_failed_rate is not None:
        print(f"  Provider failed   : {provider_failed_rate:.1%}")

    # Top errors
    try:
        from src.data_tasks.task_repo import DataLoadTaskRepository
        trepo = DataLoadTaskRepository()
        errors = trepo.top_errors(limit=3)
        if errors:
            print(f"\n  Top errors:")
            for msg, cnt in errors:
                print(f"    {cnt:>4}  {msg[:100]}")
    except Exception:
        pass

    # ── V1.4.8: Suggested commands ────────────────────────────────────
    save_used = bool(batch.save_local)
    retry_cmd = _suggested_retry_command(args.batch_id, save_used)

    print(f"\n  --- Suggested Commands ---")
    if counts.get("pending", 0) > 0:
        print(f"  Next: python -m src.backfill.batch_runner --batch-id {args.batch_id} "
              f"--status pending --limit 10 --confirm --no-save --allow-core-500-run")
    if counts.get("retryable", 0) > 0:
        print(f"  Retry: {retry_cmd}")
    if counts.get("failed", 0) > 0:
        print(f"  Investigate: python -m src.data_tasks.task_stats")

    # ── V1.4.8: Risk warnings ─────────────────────────────────────────
    if risks:
        print(f"\n  --- Risk Warnings ---")
        for r in risks:
            print(f"  [!] {r}")

    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
