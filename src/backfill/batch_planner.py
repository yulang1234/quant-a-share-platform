"""V1.4.7 Batch Planner — generate batch plans for staged backfill.

V1.5.7: universe_all_a is now the default, with safety constraints
(default recent-days ≤45, --allow-large-range to override).

Usage::

    python -m src.backfill.batch_planner --universe universe_all_a --recent-days 30 --adj qfq --dry-run
    python -m src.backfill.batch_planner --universe universe_all_a --recent-days 30 --adj qfq --confirm
    python -m src.backfill.batch_planner --universe core_500 --start-date 20240101 --end-date 20240131 --adj qfq --dry-run
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any


# ── Constants ────────────────────────────────────────────────────────────────

LARGE_UNIVERSES: frozenset[str] = frozenset({"universe_all_a", "core_500"})
DEFAULT_MAX_LIMIT: int = 50
ABSOLUTE_MAX_LIMIT: int = 100
MAX_RECENT_DAYS: int = 45  # V1.5.7: max days without --allow-large-range


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_universe_members(universe_name: str) -> list[dict[str, Any]]:
    try:
        from src.repositories.universe_repo import UniverseRepository
        urepo = UniverseRepository()
        unis = urepo.list_universes()
        uid = None
        for u in unis:
            if u.universe_name == universe_name:
                uid = u.universe_id; break
        if uid is None:
            return []
        members = urepo.list_members(uid)
        return [{"symbol": str(m.symbol).zfill(6), "exchange": str(m.exchange).upper(), "asset_type": "stock"}
                for m in members]
    except Exception:
        return []


# ── Core planner ─────────────────────────────────────────────────────────────

def plan_batch(
    universe_name: str,
    start_date: str = "20060101",
    end_date: str = "20261231",
    adj: str = "all",
    split: str = "yearly",
    limit: int = 20,
    dry_run: bool = True,
    batch_name: str | None = None,
    allow_core_500_plan: bool = False,
) -> dict[str, Any]:
    """Generate a batch plan with batch_id and tasks.

    Returns dict with batch info, tasks, and status.
    """
    # ── Safety checks ──────────────────────────────────────────────────
    if universe_name == "universe_all_a":
        # V1.5.7: allow all_a with safety constraints
        if start_date != "20060101" and end_date != "20261231":
            days = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days
            if days > MAX_RECENT_DAYS and not dry_run and not allow_core_500_plan:
                return {
                    "error": f"universe_all_a range {days}d exceeds {MAX_RECENT_DAYS}d limit. "
                             f"Use --allow-large-range to override.",
                    "tasks": [],
                }
    elif universe_name == "core_500":
        if not dry_run and not allow_core_500_plan:
            return {
                "error": "core_500 requires --allow-core-500-plan (legacy). "
                         "Consider using universe_all_a instead.",
                "tasks": [],
            }

    if limit > ABSOLUTE_MAX_LIMIT:
        return {"error": f"limit ({limit}) exceeds absolute max ({ABSOLUTE_MAX_LIMIT}).", "tasks": []}

    if limit > DEFAULT_MAX_LIMIT:
        print(f"[WARN] limit={limit} exceeds recommended max ({DEFAULT_MAX_LIMIT}). Proceeding with caution.")

    # ── Get members ────────────────────────────────────────────────────
    members = _get_universe_members(universe_name)
    if not members:
        return {"error": f"Universe '{universe_name}' not found or has no members.", "tasks": []}

    stock_count = len(members)
    if limit and limit > 0:
        members = members[:limit]

    # ── Build tasks ────────────────────────────────────────────────────
    from src.data_tasks.task_builder import build_tasks_from_securities

    tasks = build_tasks_from_securities(
        securities=members,
        data_type="daily_bar",
        adj=adj,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    planned_task_count = len(tasks)

    # ── Generate batch_id ──────────────────────────────────────────────
    from src.backfill.batch_service import generate_batch_id

    batch_id = generate_batch_id(universe_name, adj)

    result: dict[str, Any] = {
        "batch_id": batch_id,
        "batch_name": batch_name or f"{universe_name} {adj} {start_date}-{end_date}",
        "universe": universe_name,
        "stock_count": stock_count,
        "adj_type": adj,
        "start_date": start_date,
        "end_date": end_date,
        "split": split,
        "limit": limit,
        "planned_task_count": planned_task_count,
        "tasks": tasks,
        "written": 0,
        "written_task_count": 0,
        "before_snapshot": None,
    }

    # ── Write if confirm ───────────────────────────────────────────────
    if not dry_run:
        # Create batch
        from src.backfill.batch_service import create_batch_plan, mark_tasks_written, record_snapshot
        from src.backfill.batch_repo import BatchRepository

        binfo = create_batch_plan(
            universe_name=universe_name,
            adj_type=adj,
            start_date=start_date,
            end_date=end_date,
            split=split,
            batch_name=batch_name,
            planned_task_count=planned_task_count,
            limit=limit,
            batch_id=batch_id,
        )

        # Record before snapshot (non-critical)
        try:
            from src.backfill.small_batch_report import generate_report
            rpt = generate_report(universe_name, start_date, end_date, adj, limit=min(stock_count, 100))
            snap = record_snapshot(batch_id, "before", rpt)
            result["before_snapshot"] = snap
        except Exception as e:
            print(f"[WARN] Before snapshot failed (non-critical): {e}")

        # Write tasks
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = DataLoadTaskRepository()
        written = 0
        skipped_existing = 0
        for t in tasks:
            existing = repo.upsert_task(
                symbol=t["symbol"],
                exchange=t["exchange"],
                data_type=t.get("data_type", "daily_bar"),
                adj_type=t["adj_type"],
                start_date=t["start_date"],
                end_date=t["end_date"],
                batch_id=batch_id,
                status="pending",
            )
            if existing and existing.status != "pending":
                skipped_existing += 1
            else:
                written += 1

        result["written"] = written
        result["written_task_count"] = written
        result["skipped_existing"] = skipped_existing

        # Update batch status
        mark_tasks_written(batch_id, written)

    return result


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="V1.5.7 Batch Planner — generate backfill batch plans",
    )
    p.add_argument("--universe", default="universe_all_a", help="Universe name (default: universe_all_a)")
    p.add_argument("--recent-days", type=int, default=None, help="Override dates from recent N days")
    p.add_argument("--start-date", default=None, help="Start date YYYYMMDD")
    p.add_argument("--end-date", default=None, help="End date YYYYMMDD")
    p.add_argument("--adj", default="all", choices=["raw", "qfq", "all"])
    p.add_argument("--split", default="yearly")
    p.add_argument("--limit", type=int, default=20, help="Max tasks to generate")
    p.add_argument("--batch-name", default=None, help="Custom batch name")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    p.add_argument("--allow-core-500-plan", action="store_true", default=False,
                   help="Allow large universe confirm (legacy)")
    p.add_argument("--allow-large-range", action="store_true", default=False,
                   help="Allow universe_all_a over 45 days")
    args = p.parse_args()

    # Resolve dates from --recent-days
    if args.recent_days and not args.start_date:
        from datetime import date, timedelta
        end = date.today()
        start = end - timedelta(days=args.recent_days)
        args.start_date = start.strftime("%Y%m%d")
        args.end_date = end.strftime("%Y%m%d")

    # Default dates if neither provided
    if not args.start_date:
        args.start_date = (date.today() - timedelta(days=30)).strftime("%Y%m%d")
    if not args.end_date:
        args.end_date = date.today().strftime("%Y%m%d")

    dry_run = not args.confirm

    result = plan_batch(
        universe_name=args.universe,
        start_date=args.start_date,
        end_date=args.end_date,
        adj=args.adj,
        split=args.split,
        limit=args.limit,
        dry_run=dry_run,
        batch_name=args.batch_name,
        allow_core_500_plan=args.allow_core_500_plan or args.allow_large_range,
    )

    if result.get("error") and not result.get("tasks"):
        print(f"\n[ERROR] {result['error']}")
        return 1

    if dry_run:
        print(f"\n[DRY-RUN] Batch Planner")
        print(f"  Batch name       : {result.get('batch_name', '?')}")
        print(f"  Planned batch_id : {result.get('batch_id', '?')}")
        print(f"  Universe         : {result.get('universe', '?')}")
        print(f"  Stock count      : {result.get('stock_count', 0)}")
        print(f"  Adj type         : {result.get('adj_type', '?')}")
        print(f"  Date range       : {result.get('start_date', '?')} ~ {result.get('end_date', '?')}")
        print(f"  Split            : {result.get('split', '?')}")
        print(f"  Limit            : {result.get('limit', 0)}")
        print(f"  Planned tasks    : {result.get('planned_task_count', 0)}")
        tasks = result.get("tasks", [])
        print(f"  First 10 tasks   :")
        for t in tasks[:10]:
            print(f"    {t['symbol']}.{t['exchange']} {t['data_type']} {t['adj_type']} {t['start_date']}-{t['end_date']}")
        if len(tasks) > 10:
            print(f"    ... and {len(tasks) - 10} more")
        print(f"  Will write batch : False")
        print(f"  Will write tasks : False")
    else:
        print(f"\n[CONFIRMED] Batch Planner")
        print(f"  Batch ID         : {result.get('batch_id', '?')}")
        print(f"  Batch name       : {result.get('batch_name', '?')}")
        print(f"  Written tasks    : {result.get('written_task_count', 0)}")
        print(f"  Planned tasks    : {result.get('planned_task_count', 0)}")
        if result.get("before_snapshot"):
            bs = result["before_snapshot"]
            if "error" not in bs:
                print(f"  Before snapshot  : id={bs.get('snapshot_id')}, rate={bs.get('avg_coverage_rate')}")
            else:
                print(f"  Before snapshot  : failed ({bs['error']})")
        print(f"  Status           : tasks_written")

    return 0


if __name__ == "__main__":
    sys.exit(main())
