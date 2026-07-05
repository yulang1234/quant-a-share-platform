"""V1.4.3 Coverage report CLI — read-only summary from data_coverage_report.

Usage::

    python -m src.data_quality.coverage_report --universe universe_all_a --adj qfq --top-missing --limit 20
"""

from __future__ import annotations

import json
import sys


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="V1.4.3 Coverage Report")
    p.add_argument("--universe", default=None)
    p.add_argument("--adj", default="all", choices=["raw", "qfq", "all"])
    p.add_argument("--data-type", default="daily_bar")
    p.add_argument("--start-date", default=None)
    p.add_argument("--end-date", default=None)
    p.add_argument("--status", default=None)
    p.add_argument("--top-missing", action="store_true", default=False)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true", default=False)
    args = p.parse_args(argv)

    if args.limit <= 0:
        print("[ERROR] --limit must be > 0"); return 1

    from src.data_quality.coverage_repo import CoverageReportRepository
    repo = CoverageReportRepository()

    reports = repo.list_all(limit=args.limit, adj_type=args.adj, status=args.status)
    counts = repo.count_by_status()
    adj_counts = repo.count_by_adj_type()
    avg_rate = repo.avg_coverage_rate()
    avg_miss = repo.avg_missing_days()
    top = repo.top_missing(limit=args.limit) if args.top_missing else []

    total = sum(counts.values())

    if args.json:
        output = {
            "total_reports": total,
            "by_status": counts,
            "by_adj_type": adj_counts,
            "avg_coverage_rate": avg_rate,
            "avg_missing_days": avg_miss,
        }
        if top:
            output["top_missing"] = [{"symbol": r.symbol, "exchange": r.exchange,
                                       "adj_type": r.adj_type, "missing": r.missing_trade_days,
                                       "rate": r.coverage_rate} for r in top]
        print(json.dumps(output, ensure_ascii=False, default=str, indent=2))
        return 0

    print(f"Total reports : {total}")
    print(f"Avg coverage  : {avg_rate:.2%}" if avg_rate is not None else "Avg coverage  : N/A")
    print(f"Avg missing   : {avg_miss:.1f} days")
    print(f"\nBy status:")
    for s in ["complete", "partial", "empty", "unknown", "error", "calendar_missing"]:
        if s in counts:
            print(f"  {s:20s}: {counts[s]}")
    print(f"\nBy adj_type:")
    for a, c in adj_counts.items():
        print(f"  {a:6s}: {c}")

    if top:
        print(f"\nTop {len(top)} missing:")
        for r in top[:10]:
            print(f"  {r.symbol}.{r.exchange} {r.adj_type:4s} missing={r.missing_trade_days} rate={r.coverage_rate}")

    if total == 0:
        print("\n[No coverage reports found. Run coverage_scanner first.]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
