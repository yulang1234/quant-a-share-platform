"""V1.4.5 Small Batch Planner — generate data_load_tasks for core universes.

Usage::

    python -m src.backfill.small_batch_planner \
      --universe core_50 --start-date 20200101 --end-date 20261231 \
      --adj qfq --limit 10 --dry-run

    python -m src.backfill.small_batch_planner \
      --universe core_50 --start-date 20200101 --end-date 20261231 \
      --adj qfq --limit 10 --confirm
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any


# ── Constants ────────────────────────────────────────────────────────────────

ALLOWED_UNIVERSES: frozenset[str] = frozenset({
    "core_50", "core_100",
    "test", "test_universe", "test_core",
})

LARGE_UNIVERSES: frozenset[str] = frozenset({
    "universe_all_a", "core_500",
})


# ── Pure helpers ─────────────────────────────────────────────────────────────

def _year_ranges(start: str, end: str) -> list[tuple[str, str]]:
    """Split a date range into calendar-year slices."""
    sy = int(start[:4])
    ey = int(end[:4])
    ranges: list[tuple[str, str]] = []
    for y in range(sy, ey + 1):
        s = f"{y}0101"
        e = f"{y}1231"
        if y == sy:
            s = start
        if y == ey:
            e = end
        ranges.append((s, e))
    return ranges


def _validate_universe(universe_name: str, allow_large_universe: bool = False) -> str | None:
    """Check if the universe is allowed. Returns error message or None."""
    if universe_name in LARGE_UNIVERSES and not allow_large_universe:
        return (
            f"Universe '{universe_name}' is too large for small-batch planning. "
            f"Use --allow-large-universe to proceed, or use core_50 / core_100."
        )
    # Allow anything with explicit --allow-large-universe, but warn
    if universe_name not in ALLOWED_UNIVERSES and universe_name not in LARGE_UNIVERSES:
        # For unrecognized universes, still allow but warn
        return None
    return None


def _validate_date_range(start_date: str, end_date: str) -> str | None:
    """Return an error message when the requested YYYYMMDD range is invalid."""
    try:
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
    except ValueError:
        return "start_date and end_date must use YYYYMMDD format."
    if start > end:
        return f"start_date must be <= end_date, got {start_date} > {end_date}."
    return None


# ── Data helpers ─────────────────────────────────────────────────────────────

def _get_universe_members(universe_name: str) -> list[dict[str, Any]]:
    """Read members of a universe."""
    try:
        from src.repositories.universe_repo import UniverseRepository
        urepo = UniverseRepository()
        unis = urepo.list_universes()
        uid = None
        for u in unis:
            if u.universe_name == universe_name:
                uid = u.universe_id
                break
        if uid is None:
            return []
        members = urepo.list_members(uid)
        return [
            {
                "symbol": str(m.symbol).zfill(6),
                "exchange": str(m.exchange).upper(),
                "asset_type": "stock",
            }
            for m in members
        ]
    except Exception:
        return []


# ── Core planner ─────────────────────────────────────────────────────────────

def plan_tasks(
    universe_name: str,
    start_date: str = "20060101",
    end_date: str = "20261231",
    adj: str = "all",
    split: str = "yearly",
    limit: int | None = None,
    dry_run: bool = True,
    allow_large_universe: bool = False,
) -> dict[str, Any]:
    """Generate data_load_tasks for a universe.

    Returns a dict with plan/task details.
    """
    # Validate
    date_err = _validate_date_range(start_date, end_date)
    if date_err:
        return {"error": date_err, "universe": universe_name, "tasks": [], "written": 0}

    err = _validate_universe(universe_name, allow_large_universe)
    if err:
        return {"error": err, "universe": universe_name, "tasks": [], "written": 0}

    # Get members
    members = _get_universe_members(universe_name)
    if not members:
        return {
            "universe": universe_name,
            "stock_count": 0,
            "tasks": [],
            "written": 0,
            "error": f"Universe '{universe_name}' not found or has no members.",
        }

    if limit and limit > 0:
        members = members[:limit]

    # Build tasks using the existing builder
    from src.data_tasks.task_builder import build_tasks_from_securities

    tasks = build_tasks_from_securities(
        securities=members,
        data_type="daily_bar",
        adj=adj,
        start_date=start_date,
        end_date=end_date,
        dry_run=dry_run,
        limit=limit,
    )

    result: dict[str, Any] = {
        "universe": universe_name,
        "stock_count": len(members),
        "adj_type": adj,
        "start_date": start_date,
        "end_date": end_date,
        "split": split,
        "planned_task_count": len(tasks),
        "tasks": tasks,
        "written": 0,
        "skipped_existing": 0,
    }

    # Write if confirm
    if not dry_run:
        try:
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
                    status="pending",
                )
                if existing and existing.status != "pending":
                    # Task already exists in a non-pending state
                    skipped_existing += 1
                else:
                    written += 1
            result["written"] = written
            result["skipped_existing"] = skipped_existing
        except Exception as e:
            result["error"] = str(e)

    return result


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="V1.4.5 Small Batch Planner — generate data_load_tasks for core universes",
    )
    p.add_argument(
        "--universe", default="core_50",
        help="Universe name (default: core_50)",
    )
    p.add_argument(
        "--start-date", default="20060101",
        help="Start date YYYYMMDD (default: 20060101)",
    )
    p.add_argument(
        "--end-date", default="20261231",
        help="End date YYYYMMDD (default: 20261231)",
    )
    p.add_argument(
        "--adj", default="all", choices=["raw", "qfq", "all"],
        help="Adjustment type (default: all)",
    )
    p.add_argument(
        "--split", default="yearly",
        help="Task split strategy (default: yearly)",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Max number of tasks to generate",
    )
    p.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Preview only, do not write tasks (default: True)",
    )
    p.add_argument(
        "--confirm", action="store_true", default=False,
        help="Actually write tasks to the database",
    )
    p.add_argument(
        "--allow-large-universe", action="store_true", default=False,
        help="Allow planning for large universes like universe_all_a",
    )
    args = p.parse_args()

    dry_run = not args.confirm

    result = plan_tasks(
        universe_name=args.universe,
        start_date=args.start_date,
        end_date=args.end_date,
        adj=args.adj,
        split=args.split,
        limit=args.limit,
        dry_run=dry_run,
        allow_large_universe=args.allow_large_universe,
    )

    # ── Output ──────────────────────────────────────────────────────────
    if result.get("error") and not result.get("tasks"):
        print(f"\n[ERROR] {result['error']}")
        return 1

    if dry_run:
        print(f"\n[DRY-RUN] Small Batch Planner")
        print(f"  Universe         : {result.get('universe', '?')}")
        print(f"  Stock count      : {result.get('stock_count', 0)}")
        print(f"  Adj type         : {result.get('adj_type', '?')}")
        print(f"  Start date       : {result.get('start_date', '?')}")
        print(f"  End date         : {result.get('end_date', '?')}")
        print(f"  Split            : {result.get('split', '?')}")
        print(f"  Planned tasks    : {result.get('planned_task_count', 0)}")
        tasks = result.get("tasks", [])
        print(f"  First 10 tasks   :")
        for t in tasks[:10]:
            print(f"    {t['symbol']}.{t['exchange']} {t['data_type']} {t['adj_type']} {t['start_date']}-{t['end_date']}")
        if len(tasks) > 10:
            print(f"    ... and {len(tasks) - 10} more")
        print(f"  Will write       : No (dry-run)")
    else:
        print(f"\n[CONFIRMED] Small Batch Planner")
        print(f"  Universe         : {result.get('universe', '?')}")
        print(f"  Written tasks    : {result.get('written', 0)}")
        print(f"  Skipped existing : {result.get('skipped_existing', 0)}")
        print(f"  Planned total    : {result.get('planned_task_count', 0)}")

    if result.get("error"):
        print(f"\n[WARN] {result['error']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
