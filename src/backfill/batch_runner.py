"""V1.4.8 Batch Runner — execute tasks for a specific batch.

Usage::

    python -m src.backfill.batch_runner --batch-id <id> --limit 10 --confirm --no-save --allow-core-500-run
    python -m src.backfill.batch_runner --batch-id <id> --profile safe-core500-test --limit 10 --confirm --save-local --allow-core-500-run
"""

from __future__ import annotations

import sys

MAX_LIMIT: int = 50
PROFILE_LIMIT: int = 10
SAFE_PROFILE = "safe-core500-test"


def _apply_profile(args) -> list[str]:
    """Apply safe-core500-test profile constraints. Returns warnings."""
    warnings = []
    if args.limit > PROFILE_LIMIT:
        args.limit = PROFILE_LIMIT
        warnings.append(f"Profile enforced limit={PROFILE_LIMIT}")
    if args.sleep < 1.0:
        args.sleep = 1.0
        warnings.append("Profile enforced sleep=1.0")
    if not args.stop_on_failed_rate:
        args.stop_on_failed_rate = True
        warnings.append("Profile enabled stop_on_failed_rate")
    if args.max_failed_rate > 0.3:
        args.max_failed_rate = 0.3
        warnings.append("Profile enforced max_failed_rate=0.3")
    if args.limit > 50:
        args.limit = 50
        warnings.append("Profile enforced max limit=50")
    return warnings


def _resolve_status(args) -> str:
    """Resolve status filter including retryable."""
    if args.status == "retryable":
        return "failed"  # will be filtered by attempt_count in run_tasks
    return args.status


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="V1.4.8 Batch Runner — execute tasks by batch_id",
    )
    p.add_argument("--batch-id", required=True, help="Batch ID (required)")
    p.add_argument("--limit", type=int, default=20,
                   help=f"Max tasks to execute (default: 20, max: {MAX_LIMIT})")
    p.add_argument("--status", default="pending",
                   choices=["pending", "failed", "empty", "retryable"],
                   help="Task status filter (default: pending)")
    p.add_argument("--adj", default="all", choices=["raw", "qfq", "all"])
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    p.add_argument("--no-save", action="store_true", default=True)
    p.add_argument("--save-local", action="store_true", default=False)
    p.add_argument("--sleep", type=float, default=1.0)
    p.add_argument("--provider", default=None)
    p.add_argument("--stop-on-failed-rate", action="store_true", default=False)
    p.add_argument("--max-failed-rate", type=float, default=0.5)
    # V1.4.8: core_500 protection
    p.add_argument("--allow-core-500-run", action="store_true", default=False,
                   help="Required for core_500 real execution")
    p.add_argument("--profile", default=None, choices=[SAFE_PROFILE],
                   help="Use safe execution profile")
    p.add_argument("--precheck", action="store_true", default=False,
                   help="Run precheck before executing")
    args = p.parse_args()

    # ── Profile ────────────────────────────────────────────────────────
    if args.profile == SAFE_PROFILE:
        warnings = _apply_profile(args)
        print(f"[PROFILE] {SAFE_PROFILE}")
        for w in warnings:
            print(f"  {w}")

    # ── Validation ─────────────────────────────────────────────────────
    if args.save_local and not args.confirm:
        print("[ERROR] --save-local requires --confirm")
        return 1

    if args.limit > MAX_LIMIT:
        print(f"[ERROR] --limit={args.limit} exceeds max ({MAX_LIMIT}).")
        return 1

    # ── Batch lookup ───────────────────────────────────────────────────
    from src.backfill.batch_repo import BatchRepository
    repo = BatchRepository()
    batch = repo.get_batch(args.batch_id)
    if batch is None:
        print(f"[ERROR] Batch '{args.batch_id}' not found.")
        return 1

    # ── V1.4.8: core_500 real execution protection ─────────────────────
    is_core500 = str(batch.universe_name or "").lower() in ("core_500", "core500")
    if is_core500 and args.confirm and not args.allow_core_500_run:
        print("[ERROR] core_500 real execution requires --allow-core-500-run")
        print("  Dry-run does not require this flag.")
        if args.profile == SAFE_PROFILE:
            print("  Add --allow-core-500-run to proceed with safe profile.")
        return 1

    # ── Precheck ───────────────────────────────────────────────────────
    if args.precheck:
        from src.backfill.batch_precheck import run_precheck
        pc = run_precheck(args.batch_id)
        for k, v in pc.items():
            if k not in ("warnings",):
                print(f"  precheck.{k}: {v}")
        if pc.get("warnings"):
            for w in pc["warnings"]:
                print(f"  [WARN] {w}")
        if not pc.get("safe_to_run", False):
            print("[ERROR] Precheck failed. Fix issues before executing.")
            return 1

    # ── Show batch summary ─────────────────────────────────────────────
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
    if is_core500:
        print(f"  [WARN] This is a core_500 batch — staged execution only.")

    if args.confirm:
        print("\n[CONFIRMED MODE] Tasks will be executed.")
    else:
        print("\n[DRY-RUN MODE] Use --confirm to execute real tasks.")

    # ── Execute ────────────────────────────────────────────────────────
    from src.backfill.batch_service import mark_running, update_batch_results, record_snapshot
    from src.data_tasks.task_runner import run_tasks

    if args.confirm:
        mark_running(args.batch_id)

    status_filter = _resolve_status(args)
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

        # V1.4.8: auto after-snapshot
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

        b2 = repo.get_batch(args.batch_id)
        if b2:
            print(f"\n  Updated status: {b2.status}")

    return 0 if result.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
