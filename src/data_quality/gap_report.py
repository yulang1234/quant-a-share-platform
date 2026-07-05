"""V1.4.3 Gap report CLI — read-only summary from data_gap_detail.

Usage::

    python -m src.data_quality.gap_report --universe universe_all_a --adj qfq --limit 20
"""

from __future__ import annotations

import json
import sys


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="V1.4.3 Gap Report")
    p.add_argument("--universe", default=None)
    p.add_argument("--adj", default="all", choices=["raw", "qfq", "all"])
    p.add_argument("--data-type", default="daily_bar")
    p.add_argument("--security-id", default=None)
    p.add_argument("--severity", default=None, choices=["low", "medium", "high"])
    p.add_argument("--repair-status", default=None)
    p.add_argument("--gap-type", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true", default=False)
    args = p.parse_args(argv)

    if args.limit <= 0:
        print("[ERROR] --limit must be > 0"); return 1

    from src.data_quality.coverage_repo import GapDetailRepository
    repo = GapDetailRepository()

    gaps = repo.list_gaps(limit=args.limit, adj_type=args.adj,
                          severity=args.severity, repair_status=args.repair_status,
                          gap_type=args.gap_type)
    sev_counts = repo.count_by_severity()
    type_counts = repo.count_by_gap_type()
    repair_counts = repo.count_by_repair_status()
    total_gaps = repo.total_count()
    total_missing = repo.total_missing_days()

    if args.json:
        output = {
            "total_gaps": total_gaps,
            "total_missing_days": total_missing,
            "by_severity": sev_counts,
            "by_gap_type": type_counts,
            "by_repair_status": repair_counts,
            "top_gaps": [{"symbol": g.symbol, "exchange": g.exchange, "adj_type": g.adj_type,
                          "gap_start": g.gap_start_date, "gap_end": g.gap_end_date,
                          "missing_days": g.missing_days, "gap_type": g.gap_type,
                          "severity": g.severity, "repair_status": g.repair_status}
                         for g in gaps],
        }
        print(json.dumps(output, ensure_ascii=False, default=str, indent=2))
        return 0

    print(f"Total gaps      : {total_gaps}")
    print(f"Total missing   : {total_missing} days")
    print(f"\nBy severity:")
    for s in ["low", "medium", "high"]:
        if s in sev_counts:
            print(f"  {s:10s}: {sev_counts[s]}")
    print(f"\nBy gap type:")
    for t, c in type_counts.items():
        print(f"  {t:20s}: {c}")
    print(f"\nBy repair status:")
    for s, c in repair_counts.items():
        print(f"  {s:16s}: {c}")

    if gaps:
        print(f"\nTop {len(gaps)} gaps:")
        for g in gaps[:10]:
            print(f"  {g.symbol}.{g.exchange} {g.adj_type:4s} {g.gap_start_date}~{g.gap_end_date} "
                  f"missing={g.missing_days} {g.gap_type} sev={g.severity} repair={g.repair_status}")

    if total_gaps == 0:
        print("\n[No gaps found. Run coverage_scanner first.]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
