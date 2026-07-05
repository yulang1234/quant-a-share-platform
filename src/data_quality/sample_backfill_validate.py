"""V1.4.3 Sample backfill validation — small-scale repair verification.

Usage::

    python -m src.data_quality.sample_backfill_validate --limit 3 --dry-run
    python -m src.data_quality.sample_backfill_validate --limit 3 --confirm --no-save
    python -m src.data_quality.sample_backfill_validate --limit 3 --confirm --save-local
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="V1.4.3 Sample Backfill Validate")
    p.add_argument("--universe", default="universe_all_a")
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--start-date", default="20240101")
    p.add_argument("--end-date", default="20240131")
    p.add_argument("--adj", default="qfq", choices=["raw", "qfq", "all"])
    p.add_argument("--data-type", default="daily_bar")
    p.add_argument("--source", default="gaps", choices=["gaps", "tasks", "universe"])
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    p.add_argument("--no-save", action="store_true", default=True)
    p.add_argument("--save-local", action="store_true", default=False)
    p.add_argument("--provider", default=None)
    p.add_argument("--rerun-coverage", action="store_true", default=False)
    p.add_argument("--max-tasks", type=int, default=5)
    args = p.parse_args(argv)

    # Safety checks
    if args.limit <= 0:
        print("[ERROR] --limit must be > 0"); return 1
    if args.save_local and not args.confirm:
        print("[ERROR] --save-local requires --confirm"); return 1
    if args.save_local and args.limit > args.max_tasks:
        print(f"[ERROR] --save-local sample is capped by --max-tasks={args.max_tasks}")
        return 1
    if args.confirm:
        args.dry_run = False

    print(f"Source      : {args.source}")
    print(f"Limit       : {args.limit}")
    print(f"Date range  : {args.start_date} ~ {args.end_date}")
    print(f"Adj         : {args.adj}")
    print(f"Dry-run     : {args.dry_run}")
    print(f"Save-local  : {args.save_local}")
    print()

    candidates: list[dict] = []

    if args.source == "gaps":
        from src.data_quality.coverage_repo import GapDetailRepository
        repo = GapDetailRepository()
        gaps = repo.list_gaps(limit=args.limit, adj_type=args.adj if args.adj != "all" else None,
                              repair_status="pending")
        for g in gaps:
            candidates.append({"symbol": g.symbol, "exchange": g.exchange, "adj_type": g.adj_type,
                               "start_date": g.gap_start_date, "end_date": g.gap_end_date,
                               "source": "gap", "gap_type": g.gap_type})
    elif args.source == "tasks":
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = DataLoadTaskRepository()
        tasks = repo.list_pending(limit=args.limit)
        for t in tasks:
            candidates.append({"symbol": t.symbol, "exchange": t.exchange, "adj_type": t.adj_type,
                               "start_date": str(t.start_date)[:10] if t.start_date else args.start_date,
                               "end_date": str(t.end_date)[:10] if t.end_date else args.end_date,
                               "source": "task", "task_id": t.task_id})
    else:  # universe
        candidates = [{"symbol": "000001", "exchange": "SZ", "adj_type": "qfq",
                       "start_date": args.start_date, "end_date": args.end_date, "source": "universe"}]
        if args.limit < len(candidates):
            candidates = candidates[:args.limit]

    if not candidates:
        print("[No candidates found.]"); return 0

    print(f"Candidates  : {len(candidates)}")
    for c in candidates[:10]:
        print(f"  {c['symbol']}.{c['exchange']} {c.get('adj_type','qfq')} {c['start_date']}~{c['end_date']} [{c['source']}]")

    if args.dry_run:
        print("\n[DRY-RUN] No task executed. No data saved.")
        if args.rerun_coverage:
            print("[DRY-RUN] Would re-run coverage scanner before/after.")
        return 0

    # confirm mode
    if not args.save_local:
        print("\n[CONFIRM --NO-SAVE] Executing tasks via MarketDataService (no data saved)...")
        from src.data_sources.market_data_service import MarketDataService
        svc = MarketDataService()
        success = 0; failed = 0; empty = 0
        for c in candidates:
            try:
                df, prov = svc.get_daily_bars(
                    f"{c['symbol']}.{c['exchange']}", c['start_date'], c['end_date'],
                    c.get('adj_type', 'qfq'),
                )
                if df is not None and not df.empty:
                    print(f"  OK  {c['symbol']} via {prov} ({len(df)} rows)")
                    success += 1
                else:
                    print(f"  EMPTY {c['symbol']}")
                    empty += 1
            except Exception as e:
                print(f"  ERR {c['symbol']}: {type(e).__name__}")
                failed += 1
        print(f"\nResult: success={success} failed={failed} empty={empty}")
        print("[--no-save] No data written to Parquet/DuckDB.")
    else:
        print("\n[CONFIRM --SAVE-LOCAL] Executing and saving to local storage...")
        from src.data_tasks.task_runner import run_tasks
        result = run_tasks(limit=min(args.limit, args.max_tasks), confirm=True,
                           adj_filter=args.adj, save_local=True, no_save=False,
                           sleep_seconds=1.0)
        for k, v in result.items():
            print(f"  {k}: {v}")

    if args.rerun_coverage and not args.dry_run:
        print("\n[INFO] Re-run coverage scanner after backfill...")
        print("[INFO] Run: python -m src.data_quality.coverage_scanner --limit 5 --confirm")

    return 0


if __name__ == "__main__":
    sys.exit(main())
