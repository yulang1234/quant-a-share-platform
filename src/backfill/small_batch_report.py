"""V1.4.5 Small Batch Report — coverage report and provider stability for core backfill.

Usage::

    python -m src.backfill.small_batch_report \
      --universe core_50 --start-date 20200101 --end-date 20261231 \
      --adj qfq --limit 50
"""

from __future__ import annotations

import sys
from typing import Any


# ── Data helpers ─────────────────────────────────────────────────────────────

def _get_universe_members(universe_name: str, limit: int | None = None) -> list[dict[str, Any]]:
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
        if limit and limit > 0:
            members = members[:limit]
        return [
            {
                "symbol": str(m.symbol).zfill(6),
                "exchange": str(m.exchange).upper(),
            }
            for m in members
        ]
    except Exception:
        return []


def _read_local_dates(table: str, symbol: str, start_date: str, end_date: str) -> set[str]:
    """Read distinct trade_dates from DuckDB. Returns empty set on any failure."""
    try:
        from src.storage.duckdb_repo import query_df
        check = query_df(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table],
        )
        if check.iloc[0, 0] == 0:
            return set()
        df = query_df(
            f"SELECT DISTINCT trade_date FROM {table} WHERE stock_code = ? "
            f"AND trade_date >= ? AND trade_date <= ?",
            [symbol, start_date, end_date],
        )
        if df.empty:
            return set()
        return set(str(d)[:10] for d in df["trade_date"])
    except Exception:
        return set()


def _get_trading_calendar_dates(start_date: str, end_date: str) -> list[str]:
    """Get open trade dates from trading_calendar. Returns empty list if unavailable."""
    try:
        from src.trading_calendar.trading_calendar_service import TradingCalendarService
        csvc = TradingCalendarService()
        cal_dates = csvc.list_open_dates(start_date, end_date, "CN")
        return [
            d.trade_date.strftime("%Y-%m-%d") if hasattr(d.trade_date, "strftime")
            else str(d.trade_date)[:10]
            for d in cal_dates
        ]
    except Exception:
        return []


def _get_provider_stats(limit: int = 200) -> dict[str, dict[str, Any]]:
    """Read provider call log and compute per-provider stats."""
    try:
        from src.repositories.provider_repo import ProviderCallLogRepository
        repo = ProviderCallLogRepository()
        logs = repo.recent(limit=limit)
        if not logs:
            return {}

        stats: dict[str, dict[str, Any]] = {}
        for log_entry in logs:
            pname = log_entry.provider_name
            if pname not in stats:
                stats[pname] = {
                    "provider_name": pname,
                    "success_count": 0,
                    "failed_count": 0,
                    "empty_count": 0,
                    "skipped_count": 0,
                    "total_duration_ms": 0,
                    "total_row_count": 0,
                    "call_count": 0,
                    "recent_error": "",
                }
            s = stats[pname]
            status = log_entry.status or "unknown"
            if status == "success":
                s["success_count"] += 1
            elif status == "failed":
                s["failed_count"] += 1
                if not s["recent_error"]:
                    s["recent_error"] = (log_entry.error_message or "")[:200]
            elif status == "empty":
                s["empty_count"] += 1
            elif status == "skipped":
                s["skipped_count"] += 1
            s["total_duration_ms"] += log_entry.duration_ms or 0
            s["total_row_count"] += log_entry.row_count or 0
            s["call_count"] += 1

        # Compute averages
        for pname, s in stats.items():
            if s["call_count"] > 0:
                s["avg_duration_ms"] = int(s["total_duration_ms"] / s["call_count"])
            else:
                s["avg_duration_ms"] = 0

        return stats
    except Exception:
        return {}


# ── Core report ──────────────────────────────────────────────────────────────

def generate_report(
    universe_name: str,
    start_date: str = "20060101",
    end_date: str = "20261231",
    adj: str = "all",
    limit: int | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Generate a small-batch coverage report.

    Returns a dict with coverage summary and provider stats.
    """
    adj_types = ["raw", "qfq"] if adj == "all" else [adj]
    table_map = {"raw": "stock_daily_raw", "qfq": "stock_daily_qfq"}

    # Get universe members
    members = _get_universe_members(universe_name, limit=limit)
    if not members:
        return {
            "universe": universe_name,
            "stock_count": 0,
            "error": f"Universe '{universe_name}' not found or has no members.",
        }

    # Get trading calendar
    expected_dates = _get_trading_calendar_dates(start_date, end_date)
    calendar_available = len(expected_dates) > 0

    # V1.4.6: get calendar source info
    calendar_source = "none"
    is_real_calendar = False
    calendar_warning = ""
    try:
        from src.trading_calendar.trading_calendar_service import TradingCalendarService
        csvc = TradingCalendarService()
        cal_info = csvc.get_calendar_source_info("CN")
        calendar_source = cal_info.get("calendar_source", "none")
        is_real_calendar = cal_info.get("is_real_calendar", False)
    except Exception:
        pass

    if not is_real_calendar and calendar_available:
        calendar_warning = "Coverage result may be inaccurate."

    results: list[dict[str, Any]] = []

    for member in members:
        sym = member["symbol"]
        ex = member.get("exchange", "SZ").upper()

        for adj_t in adj_types:
            table = table_map[adj_t]
            actual = _read_local_dates(table, sym, start_date, end_date)
            exp_count = len(expected_dates) if calendar_available else 0
            act_count = len(actual)
            miss = exp_count - act_count
            rate = act_count / exp_count if exp_count > 0 else None

            if not calendar_available:
                status = "calendar_missing"
            elif act_count == 0:
                status = "empty"
            elif miss == 0:
                status = "complete"
            else:
                status = "partial"

            results.append({
                "symbol": sym,
                "exchange": ex,
                "adj_type": adj_t,
                "expected": exp_count,
                "actual": act_count,
                "missing": max(0, miss),
                "coverage_rate": rate,
                "status": status,
            })

    # Compute summary
    complete = [r for r in results if r["status"] == "complete"]
    partial = [r for r in results if r["status"] == "partial"]
    empty = [r for r in results if r["status"] == "empty"]
    cal_missing = [r for r in results if r["status"] == "calendar_missing"]

    rates = [r["coverage_rate"] for r in results if r["coverage_rate"] is not None]
    avg_rate = sum(rates) / len(rates) if rates else None
    min_rate = min(rates) if rates else None
    max_rate = max(rates) if rates else None

    # Top missing / complete stocks
    top_missing = sorted(
        [r for r in results if r["status"] in ("partial", "empty")],
        key=lambda x: x["missing"],
        reverse=True,
    )[:top_n]

    top_complete = sorted(
        [r for r in results if r["status"] == "complete"],
        key=lambda x: x["coverage_rate"] or 0,
        reverse=True,
    )[:top_n]

    # Provider stats
    provider_stats = _get_provider_stats(limit=200)

    report: dict[str, Any] = {
        "universe": universe_name,
        "adj_type": adj,
        "start_date": start_date,
        "end_date": end_date,
        "stock_count": len(members),
        "calendar_available": calendar_available,
        "calendar_source": calendar_source,
        "is_real_calendar": is_real_calendar,
        "calendar_warning": calendar_warning,
        "complete_count": len(complete),
        "partial_count": len(partial),
        "empty_count": len(empty),
        "calendar_missing_count": len(cal_missing),
        "avg_coverage_rate": avg_rate,
        "min_coverage_rate": min_rate,
        "max_coverage_rate": max_rate,
        "top_missing_stocks": top_missing,
        "top_complete_stocks": top_complete,
        "provider_stats": provider_stats,
        "results": results,
    }

    return report


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="V1.4.5 Small Batch Report — coverage & provider stats for core backfill",
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
        "--limit", type=int, default=50,
        help="Max stocks to scan (default: 50)",
    )
    p.add_argument(
        "--top", type=int, default=10,
        help="Number of top stocks to show (default: 10)",
    )
    args = p.parse_args()

    report = generate_report(
        universe_name=args.universe,
        start_date=args.start_date,
        end_date=args.end_date,
        adj=args.adj,
        limit=args.limit,
        top_n=args.top,
    )

    # ── Output ──────────────────────────────────────────────────────────
    if report.get("error") and report.get("stock_count", 0) == 0:
        print(f"\n[ERROR] {report['error']}")
        return 1

    print(f"\n{'='*60}")
    print(f"  Small Batch Coverage Report")
    print(f"{'='*60}")
    print(f"  Universe           : {report.get('universe', '?')}")
    print(f"  Adj type           : {report.get('adj_type', '?')}")
    print(f"  Date range         : {report.get('start_date', '?')} ~ {report.get('end_date', '?')}")
    print(f"  Stocks scanned     : {report.get('stock_count', 0)}")

    if not report.get("calendar_available"):
        print(f"  [WARN] Trading calendar not available — coverage rates may be inaccurate.")

    # V1.4.6: show calendar source info
    print(f"\n  --- Calendar ---")
    print(f"  Source            : {report.get('calendar_source', 'unknown')}")
    print(f"  Is real calendar  : {report.get('is_real_calendar', False)}")
    if report.get("calendar_warning"):
        print(f"  Warning           : {report['calendar_warning']}")

    print(f"\n  --- Coverage Summary ---")
    print(f"  Complete           : {report.get('complete_count', 0)}")
    print(f"  Partial            : {report.get('partial_count', 0)}")
    print(f"  Empty              : {report.get('empty_count', 0)}")
    print(f"  Calendar missing   : {report.get('calendar_missing_count', 0)}")

    avg = report.get("avg_coverage_rate")
    mn = report.get("min_coverage_rate")
    mx = report.get("max_coverage_rate")
    print(f"  Avg coverage rate  : {avg:.4f}" if avg is not None else "  Avg coverage rate  : N/A")
    print(f"  Min coverage rate  : {mn:.4f}" if mn is not None else "  Min coverage rate  : N/A")
    print(f"  Max coverage rate  : {mx:.4f}" if mx is not None else "  Max coverage rate  : N/A")

    # Top missing stocks
    top_missing = report.get("top_missing_stocks", [])
    if top_missing:
        print(f"\n  --- Top {len(top_missing)} Missing Stocks ---")
        for r in top_missing:
            rate_str = f"{r['coverage_rate']:.2%}" if r["coverage_rate"] is not None else "N/A"
            print(f"  {r['symbol']}.{r['exchange']} {r['adj_type']:4s}  missing={r['missing']:5d}  rate={rate_str}  status={r['status']}")
    else:
        print(f"\n  --- Top Missing Stocks ---")
        print(f"  (none)")

    # Top complete stocks
    top_complete = report.get("top_complete_stocks", [])
    if top_complete:
        print(f"\n  --- Top {len(top_complete)} Complete Stocks ---")
        for r in top_complete:
            rate_str = f"{r['coverage_rate']:.2%}" if r["coverage_rate"] is not None else "N/A"
            print(f"  {r['symbol']}.{r['exchange']} {r['adj_type']:4s}  actual={r['actual']:5d}  rate={rate_str}")

    # Provider stats
    provider_stats = report.get("provider_stats", {})
    if provider_stats:
        print(f"\n  --- Provider Stability ---")
        for pname, s in sorted(provider_stats.items()):
            print(f"  [{pname}]")
            print(f"    success: {s['success_count']}, failed: {s['failed_count']}, "
                  f"empty: {s['empty_count']}, skipped: {s['skipped_count']}")
            print(f"    avg_duration: {s['avg_duration_ms']}ms, total_rows: {s['total_row_count']}")
            if s.get("recent_error"):
                print(f"    recent_error: {s['recent_error'][:120]}")
    else:
        print(f"\n  --- Provider Stability ---")
        print(f"  No provider call log data available.")

    print(f"\n{'='*60}")

    if report.get("error"):
        print(f"[WARN] {report['error']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
