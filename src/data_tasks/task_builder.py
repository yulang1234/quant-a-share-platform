"""V1.4.2 Task builder — generate data_load_tasks split by year."""

from __future__ import annotations

import sys
from datetime import datetime


def _year_ranges(start: str, end: str) -> list[tuple[str, str]]:
    sy = int(start[:4]); ey = int(end[:4])
    ranges = []
    for y in range(sy, ey + 1):
        s = f"{y}0101"; e = f"{y}1231"
        if y == sy: s = start
        if y == ey: e = end
        ranges.append((s, e))
    return ranges


def build_tasks_from_securities(
    securities: list[dict],
    data_type: str = "daily_bar",
    adj: str = "all",
    start_date: str = "20060101",
    end_date: str = "20261231",
    dry_run: bool = True,
    limit: int | None = None,
) -> list[dict]:
    """Generate task dicts. Returns list of task specs."""
    adj_types = ["raw", "qfq"] if adj == "all" else [adj]
    years = _year_ranges(start_date, end_date)
    tasks = []

    for sec in securities:
        if limit and len(tasks) >= limit:
            break
        for adj_t in adj_types:
            for ys, ye in years:
                tasks.append({
                    "symbol": str(sec["symbol"]).zfill(6),
                    "exchange": sec.get("exchange", "").upper(),
                    "asset_type": sec.get("asset_type", "stock"),
                    "data_type": data_type,
                    "adj_type": adj_t,
                    "start_date": ys,
                    "end_date": ye,
                    "status": "pending",
                })
    return tasks[:limit] if limit else tasks


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="V1.4.2 Task Builder")
    p.add_argument("--universe", default="universe_all_a")
    p.add_argument("--data-type", default="daily_bar")
    p.add_argument("--adj", default="all", choices=["raw", "qfq", "all"])
    p.add_argument("--start-date", default="20060101")
    p.add_argument("--end-date", default="20261231")
    p.add_argument("--split", default="yearly")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    args = p.parse_args()

    from src.repositories.universe_repo import UniverseRepository
    urepo = UniverseRepository()
    unis = urepo.list_universes()
    uname_map = {u.universe_name: u.universe_id for u in unis}
    uid = uname_map.get(args.universe)
    if not uid:
        print(f"[WARN] Universe '{args.universe}' not found. Using stock_pool fallback.")
        # Fallback: read from stock_pool
        from src.storage.duckdb_repo import query_df
        pool = query_df("SELECT stock_code, exchange FROM stock_pool WHERE is_active=TRUE")
        securities = [{"symbol": r["stock_code"], "exchange": r.get("exchange", "SZ")}
                      for _, r in pool.iterrows()]
    else:
        members = urepo.list_members(uid)
        securities = [{"symbol": m.symbol, "exchange": m.exchange} for m in members]

    if not securities:
        print("[WARN] No securities found.")
        return 0

    tasks = build_tasks_from_securities(
        securities, args.data_type, args.adj,
        args.start_date, args.end_date, dry_run=args.dry_run, limit=args.limit,
    )
    print(f"Planned tasks: {len(tasks)}")
    for t in tasks[:5]:
        print(f"  {t['symbol']}.{t['exchange']} {t['data_type']} {t['adj_type']} {t['start_date']}-{t['end_date']}")
    if len(tasks) > 5:
        print(f"  ... and {len(tasks) - 5} more")

    if args.confirm:
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = DataLoadTaskRepository()
        written = 0
        for t in tasks:
            existing = repo.upsert_task(**t)
            if existing and existing.status != "pending":
                continue  # skip already-processed tasks
            written += 1
        print(f"Written: {written} new tasks")
    else:
        print("[DRY-RUN] No tasks written. Use --confirm to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
