"""V1.4.5 Small Batch Runner — safe wrapper around task_runner for core backfill.

Usage::

    python -m src.backfill.small_batch_runner --limit 5 --adj qfq --confirm --no-save
    python -m src.backfill.small_batch_runner --limit 5 --adj qfq --confirm --save-local
"""

from __future__ import annotations

import sys


# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_LIMIT: int = 20
MAX_LIMIT_WITHOUT_FORCE: int = 50


# ── Core runner ──────────────────────────────────────────────────────────────

def run_small_batch(
    limit: int = 5,
    status_filter: str = "pending",
    adj_filter: str = "all",
    confirm: bool = False,
    no_save: bool = True,
    save_local: bool = False,
    sleep_seconds: float = 1.0,
    provider_name: str | None = None,
) -> dict[str, int]:
    """Run a small batch of data_load_tasks using the existing task_runner.

    Returns a dict with total/success/failed/empty/skipped counts.
    """
    # Validation
    if save_local and not confirm:
        return {"error": "--save-local requires --confirm", "total": 0,
                "success": 0, "failed": 0, "empty": 0, "skipped": 0}

    if limit > MAX_LIMIT_WITHOUT_FORCE:
        print(
            f"[WARN] --limit={limit} exceeds safe threshold ({MAX_LIMIT_WITHOUT_FORCE}). "
            f"Proceeding anyway since V1.4.5 allows small batches."
        )

    from src.data_tasks.task_runner import run_tasks

    try:
        result = run_tasks(
            limit=limit,
            status_filter=status_filter,
            adj_filter=adj_filter,
            no_save=no_save,
            save_local=save_local,
            confirm=confirm,
            sleep_seconds=sleep_seconds,
            provider_name=provider_name,
        )
        return result
    except Exception as e:
        return {"error": str(e), "total": 0, "success": 0, "failed": 1,
                "empty": 0, "skipped": 0}


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="V1.4.5 Small Batch Runner — safe wrapper for core backfill execution",
    )
    p.add_argument(
        "--limit", type=int, default=5,
        help=f"Max tasks to execute (default: 5, max recommended: {MAX_LIMIT_WITHOUT_FORCE})",
    )
    p.add_argument(
        "--status", default="pending",
        choices=["pending", "failed", "empty"],
        help="Filter tasks by status (default: pending)",
    )
    p.add_argument(
        "--adj", default="all", choices=["raw", "qfq", "all"],
        help="Filter tasks by adj type (default: all)",
    )
    p.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Preview only, do not execute tasks (default: True)",
    )
    p.add_argument(
        "--confirm", action="store_true", default=False,
        help="Actually execute tasks",
    )
    p.add_argument(
        "--no-save", action="store_true", default=True,
        help="Do not save market data to local storage (default: True)",
    )
    p.add_argument(
        "--save-local", action="store_true", default=False,
        help="Save market data to DuckDB + Parquet (requires --confirm)",
    )
    p.add_argument(
        "--sleep", type=float, default=1.0,
        help="Sleep seconds between tasks (default: 1.0)",
    )
    p.add_argument(
        "--provider", default=None,
        help="Preferred provider name (optional)",
    )
    args = p.parse_args()

    # Validation
    if args.save_local and not args.confirm:
        print("[ERROR] --save-local requires --confirm")
        return 1

    if args.limit > MAX_LIMIT_WITHOUT_FORCE:
        print(
            f"[WARN] --limit={args.limit} > {MAX_LIMIT_WITHOUT_FORCE}. "
            f"Consider reducing the limit for safer execution."
        )

    if not args.confirm and not args.dry_run:
        # If user explicitly did --no-dry-run but also --confirm, proceed
        pass

    if args.confirm:
        print("[CONFIRMED MODE] Tasks will be executed.\n")
    else:
        print("[DRY-RUN MODE] Use --confirm to execute real tasks.\n")

    result = run_small_batch(
        limit=args.limit,
        status_filter=args.status,
        adj_filter=args.adj,
        confirm=args.confirm,
        no_save=args.no_save,
        save_local=args.save_local,
        sleep_seconds=args.sleep,
        provider_name=args.provider,
    )

    if "error" in result:
        print(f"\n[ERROR] {result['error']}")
        return 1

    print(f"\nSmall batch runner result:")
    print(f"  total  : {result.get('total', 0)}")
    print(f"  success: {result.get('success', 0)}")
    print(f"  failed : {result.get('failed', 0)}")
    print(f"  empty  : {result.get('empty', 0)}")
    print(f"  skipped: {result.get('skipped', 0)}")

    return 0 if result.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
