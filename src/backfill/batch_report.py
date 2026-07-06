"""V1.4.7 Batch Report — comprehensive report for a single batch.

Usage::

    python -m src.backfill.batch_report --batch-id <batch_id>
"""

from __future__ import annotations

import sys
from typing import Any


def _next_suggested_action(batch_info: dict[str, Any],
                           before_snap: dict | None,
                           after_snap: dict | None) -> str:
    """Suggest next action based on batch state."""
    status = batch_info.get("status", "")
    failed = batch_info.get("failed_count", 0) or 0
    success = batch_info.get("success_count", 0) or 0
    empty = batch_info.get("empty_count", 0) or 0

    if failed > 0 and success == 0:
        return "Check task_stats for failure details, then retry failed tasks."
    if failed > 0:
        return "Some tasks failed. Run batch_runner --status failed to retry."
    if empty > 0:
        return "Some tasks returned empty. Check Provider or stock code mapping."
    if status == "tasks_written" or status == "planned":
        return f"Tasks are ready. Run: python -m src.backfill.batch_runner --batch-id {batch_info.get('batch_id', '?')} --limit 20 --confirm --no-save"
    if status == "partial_success":
        return "Batch partially complete. Run batch_runner with remaining tasks."
    if status == "success":
        return "Batch complete. Proceed to next batch or expand date range."

    if not batch_info.get("is_real_calendar", True):
        return "Sync real trading calendar first: python -m src.trading_calendar.sync_trading_calendar --confirm"

    return "Review batch and decide next step."


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="V1.4.7 Batch Report — detailed report for a batch",
    )
    p.add_argument("--batch-id", required=True, help="Batch ID")
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

    # Provider stats
    provider_success_rate = None
    provider_failed_rate = None
    total_executed = (batch.success_count or 0) + (batch.failed_count or 0) + (batch.empty_count or 0)
    if total_executed > 0:
        provider_success_rate = (batch.success_count or 0) / total_executed
        provider_failed_rate = (batch.failed_count or 0) / total_executed

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
    print(f"  Planned tasks     : {batch.planned_task_count}")
    print(f"  Written tasks     : {batch.written_task_count}")
    print(f"  Executed tasks    : {total_executed}")
    print(f"  Success           : {batch.success_count}")
    print(f"  Failed            : {batch.failed_count}")
    print(f"  Empty             : {batch.empty_count}")
    print(f"  Skipped           : {batch.skipped_count}")

    # Before snapshot
    if before_snap:
        print(f"\n  --- Before Snapshot ---")
        print(f"  Snapshot ID       : {before_snap.snapshot_id}")
        print(f"  Stocks scanned    : {before_snap.stock_count}")
        print(f"  Complete/Partial  : {before_snap.complete_count}/{before_snap.partial_count}")
        print(f"  Avg coverage      : {before_snap.avg_coverage_rate}")
        print(f"  Calendar source   : {before_snap.calendar_source}")
        print(f"  Is real calendar  : {before_snap.is_real_calendar}")
    else:
        print(f"\n  --- Before Snapshot ---")
        print(f"  (none)")

    # After snapshot
    if after_snap:
        print(f"\n  --- After Snapshot ---")
        print(f"  Snapshot ID       : {after_snap.snapshot_id}")
        print(f"  Stocks scanned    : {after_snap.stock_count}")
        print(f"  Complete/Partial  : {after_snap.complete_count}/{after_snap.partial_count}")
        print(f"  Avg coverage      : {after_snap.avg_coverage_rate}")
        print(f"  Calendar source   : {after_snap.calendar_source}")
    else:
        print(f"\n  --- After Snapshot ---")
        print(f"  (none)")

    # Coverage delta
    if coverage_delta is not None:
        sign = "+" if coverage_delta >= 0 else ""
        print(f"\n  Coverage delta    : {sign}{coverage_delta:.4f}")
    else:
        print(f"\n  Coverage delta    : N/A")

    # Provider rates
    if provider_success_rate is not None:
        print(f"\n  Provider success  : {provider_success_rate:.1%}")
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

    # Suggested action
    batch_info = {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "success_count": batch.success_count,
        "failed_count": batch.failed_count,
        "empty_count": batch.empty_count,
        "is_real_calendar": after_snap.is_real_calendar if after_snap else (before_snap.is_real_calendar if before_snap else True),
    }
    action = _next_suggested_action(batch_info,
                                     before_snap.__dict__ if before_snap else None,
                                     after_snap.__dict__ if after_snap else None)
    print(f"\n  Next action       : {action}")

    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
