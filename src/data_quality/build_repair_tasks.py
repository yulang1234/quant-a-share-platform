"""V1.4.3 Build repair tasks from coverage gaps.

Usage::

    python -m src.data_quality.build_repair_tasks --universe universe_all_a --adj qfq --limit 20 --dry-run
"""

from __future__ import annotations

import sys

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="V1.4.3 Build Repair Tasks from Gaps")
    p.add_argument("--universe", default="universe_all_a")
    p.add_argument("--adj", default="all", choices=["raw", "qfq", "all"])
    p.add_argument("--data-type", default="daily_bar")
    p.add_argument("--min-severity", default="low", choices=["low", "medium", "high"])
    p.add_argument("--gap-type", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    args = p.parse_args(argv)
    if args.confirm:
        args.dry_run = False  # confirm implies no-dry-run

    if args.limit <= 0:
        print("[ERROR] --limit must be > 0"); return 1

    from src.data_quality.coverage_repo import GapDetailRepository
    from src.data_tasks.task_repo import DataLoadTaskRepository

    gap_repo = GapDetailRepository()
    task_repo = DataLoadTaskRepository()

    min_sev = _SEVERITY_ORDER[args.min_severity]
    adj_types = ["raw", "qfq"] if args.adj == "all" else [args.adj]

    matched = 0
    created = 0
    skipped_existing = 0
    skipped_calendar = 0
    linked = 0
    errors = 0

    for adj_t in adj_types:
        gaps = gap_repo.list_gaps(limit=args.limit, adj_type=adj_t, repair_status="pending",
                                  gap_type=args.gap_type)
        for gap in gaps:
            if gap.gap_type == "calendar_missing":
                skipped_calendar += 1; continue
            if _SEVERITY_ORDER.get(gap.severity, 0) < min_sev:
                continue
            matched += 1

            task_kw = {
                "symbol": gap.symbol, "exchange": gap.exchange,
                "asset_type": "stock", "data_type": gap.data_type or "daily_bar",
                "adj_type": gap.adj_type,
                "start_date": gap.gap_start_date, "end_date": gap.gap_end_date,
                "status": "pending",
            }

            if not args.dry_run and args.confirm:
                existing = task_repo.upsert_task(**task_kw)
                if existing.status != "pending":
                    skipped_existing += 1
                else:
                    created += 1
                gap_repo.update_repair_status(gap.gap_id, "task_created", task_id=existing.task_id)
                linked += 1
            else:
                # dry-run: only check, don't write
                print(f"  {gap.symbol}.{gap.exchange} {gap.adj_type:4s} "
                      f"{gap.gap_start_date}~{gap.gap_end_date} "
                      f"missing={gap.missing_days} {gap.gap_type} -> task (dry-run)")

    print(f"\nSummary:")
    print(f"  Gaps matched       : {matched}")
    print(f"  Skipped calendar   : {skipped_calendar}")
    print(f"  Created tasks      : {created}")
    print(f"  Skipped existing   : {skipped_existing}")
    print(f"  Linked gaps        : {linked}")
    print(f"  Errors             : {errors}")

    if args.dry_run or not args.confirm:
        print("\n[DRY-RUN] No data written. Use --confirm to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
