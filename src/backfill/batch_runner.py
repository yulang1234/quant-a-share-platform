"""V1.4.7 Batch Runner — execute tasks for a specific batch.

Usage::

    python -m src.backfill.batch_runner --batch-id <id> --limit 10 --confirm --no-save
    python -m src.backfill.batch_runner --batch-id <id> --limit 10 --confirm --save-local
"""

from __future__ import annotations

import sys


MAX_LIMIT: int = 50


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="V1.4.7 Batch Runner — execute tasks by batch_id",
    )
    p.add_argument("--batch-id", required=True, help="Batch ID (required)")
    p.add_argument("--limit", type=int, default=20,
                   help=f"Max tasks to execute (default: 20, max: {MAX_LIMIT})")
    p.add_argument("--status", default="pending", choices=["pending", "failed", "empty"])
    p.add_argument("--adj", default="all", choices=["raw", "qfq", "all"])
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    p.add_argument("--no-save", action="store_true", default=True)
    p.add_argument("--save-local", action="store_true", default=False)
    p.add_argument("--sleep", type=float, default=1.0)
    p.add_argument("--provider", default=None)
    p.add_argument("--skip-failed", action="store_true", default=False,
                   help="Skip tasks that have already failed")
    p.add_argument("--stop-on-failed-rate", action="store_true", default=False,
                   help="Stop if failed rate exceeds threshold")
    p.add_argument("--max-failed-rate", type=float, default=0.5,
                   help="Max failed rate before stopping (default: 0.5)")
    args = p.parse_args()

    # ── Validation ─────────────────────────────────────────────────────
    if args.save_local and not args.confirm:
        print("[ERROR] --save-local requires --confirm")
        return 1

    if args.limit > MAX_LIMIT:
        print(f"[ERROR] --limit={args.limit} exceeds max ({MAX_LIMIT}). Reduce or use small_batch_runner.")
        return 1

    # ── Show batch summary ─────────────────────────────────────────────
    from src.backfill.batch_repo import BatchRepository
    repo = BatchRepository()
    batch = repo.get_batch(args.batch_id)
    if batch is None:
        print(f"[ERROR] Batch '{args.batch_id}' not found.")
        return 1

    print(f"\nBatch Summary:")
    print(f"  Batch ID      : {batch.batch_id}")
    print(f"  Name          : {batch.batch_name}")
    print(f"  Universe      : {batch.universe_name}")
    print(f"  Adj           : {batch.adj_type}")
    print(f"  Date range    : {batch.start_date} ~ {batch.end_date}")
    print(f"  Status        : {batch.status}")
    print(f"  Planned tasks : {batch.planned_task_count}")
    print(f"  Written tasks : {batch.written_task_count}")
    print(f"  Success/fail  : {batch.success_count}/{batch.failed_count}")

    if args.confirm:
        print("\n[CONFIRMED MODE] Tasks will be executed.")
    else:
        print("\n[DRY-RUN MODE] Use --confirm to execute real tasks.")

    # ── Execute ────────────────────────────────────────────────────────
    from src.backfill.batch_service import mark_running, update_batch_results, record_snapshot
    from src.data_tasks.task_runner import run_tasks

    if args.confirm:
        mark_running(args.batch_id)

    status_filter = "failed" if args.skip_failed else args.status
    result = run_tasks(
        limit=args.limit,
        status_filter=status_filter,
        adj_filter=args.adj,
        no_save=args.no_save,
        save_local=args.save_local,
        confirm=args.confirm,
        sleep_seconds=args.sleep,
        provider_name=args.provider,
        batch_id=args.batch_id,
        stop_on_failed_rate=args.stop_on_failed_rate,
        max_failed_rate=args.max_failed_rate,
    )

    print(f"\nBatch runner result:")
    print(f"  total  : {result.get('total', 0)}")
    print(f"  success: {result.get('success', 0)}")
    print(f"  failed : {result.get('failed', 0)}")
    print(f"  empty  : {result.get('empty', 0)}")
    print(f"  skipped: {result.get('skipped', 0)}")

    # ── Update batch counts ────────────────────────────────────────────
    if args.confirm and result.get("total", 0) > 0:
        update_batch_results(args.batch_id, result)

        # Record after snapshot (non-critical)
        try:
            from src.backfill.small_batch_report import generate_report
            b = repo.get_batch(args.batch_id)
            if b:
                rpt = generate_report(
                    b.universe_name or "core_500",
                    b.start_date or "20240101",
                    b.end_date or "20240131",
                    b.adj_type or "all",
                    limit=min((b.written_task_count or 50), 100),
                )
                snap = record_snapshot(args.batch_id, "after", rpt)
                if snap and "error" not in snap:
                    print(f"  After snapshot: id={snap.get('snapshot_id')}, rate={snap.get('avg_coverage_rate')}")
                elif snap:
                    print(f"[WARN] After snapshot failed (non-critical): {snap.get('error')}")
        except Exception as e:
            print(f"[WARN] After snapshot failed (non-critical): {e}")

        # Show updated status
        b2 = BatchRepository().get_batch(args.batch_id)
        if b2:
            print(f"\n  Updated status: {b2.status}")

    return 0 if result.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
