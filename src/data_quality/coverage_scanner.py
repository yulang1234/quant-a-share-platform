"""V1.4.3 Coverage scanner CLI — scan local data vs trading calendar.

Usage::

    python -m src.data_quality.coverage_scanner --universe universe_all_a --adj qfq --limit 20 --dry-run
"""

from __future__ import annotations

import sys
from datetime import datetime


def _read_local_dates(table: str, symbol: str, start_date: str, end_date: str) -> set[str]:
    """Read distinct trade_dates from DuckDB. Returns empty set on any failure."""
    try:
        from src.storage.duckdb_repo import query_df
        # Check table exists
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


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="V1.4.3 Coverage Scanner")
    p.add_argument("--universe", default="universe_all_a")
    p.add_argument("--data-type", default="daily_bar")
    p.add_argument("--adj", default="qfq", choices=["raw", "qfq", "all"])
    p.add_argument("--start-date", default="20200101")
    p.add_argument("--end-date", default="20261231")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    args = p.parse_args(argv)
    if args.confirm:
        args.dry_run = False

    if args.limit <= 0:
        print("[ERROR] --limit must be > 0")
        return 1

    # Get securities from universe
    securities = []
    try:
        from src.repositories.universe_repo import UniverseRepository
        urepo = UniverseRepository()
        unis = urepo.list_universes()
        uid = None
        for u in unis:
            if u.universe_name == args.universe:
                uid = u.universe_id; break
        if uid:
            members = urepo.list_members(uid)[:args.limit]
            securities = [{"symbol": m.symbol, "exchange": m.exchange} for m in members]
    except Exception:
        pass

    if not securities:
        try:
            from src.storage.duckdb_repo import query_df
            pool = query_df(f"SELECT stock_code, exchange FROM stock_pool WHERE is_active=TRUE LIMIT {args.limit}")
            securities = [{"symbol": r["stock_code"], "exchange": r.get("exchange", "SZ")} for _, r in pool.iterrows()]
        except Exception:
            securities = []

    if not securities:
        print("[WARN] No securities found in universe or stock_pool."); return 0

    # Get trading calendar open dates
    expected_all = []
    try:
        from src.trading_calendar.trading_calendar_service import TradingCalendarService
        csvc = TradingCalendarService()
        cal_dates = csvc.list_open_dates(args.start_date, args.end_date, "CN")
        expected_all = [d.trade_date.strftime("%Y-%m-%d") if hasattr(d.trade_date, "strftime") else str(d.trade_date)[:10] for d in cal_dates]
    except Exception:
        pass

    adj_types = ["raw", "qfq"] if args.adj == "all" else [args.adj]
    table_map = {"raw": "stock_daily_raw", "qfq": "stock_daily_qfq"}

    from src.data_quality.gap_detector import detect_gaps
    from src.data_quality.coverage_repo import CoverageReportRepository, GapDetailRepository

    cov_repo = CoverageReportRepository()
    gap_repo = GapDetailRepository()

    total = len(securities)
    results = []

    for sec in securities:
        sym = str(sec["symbol"]).zfill(6)
        ex = sec.get("exchange", "SZ").upper()
        for adj_t in adj_types:
            table = table_map[adj_t]
            actual = _read_local_dates(table, sym, args.start_date, args.end_date)
            exp_count = len(expected_all)
            act_count = len(actual)
            miss = exp_count - act_count
            rate = act_count / exp_count if exp_count > 0 else None

            if exp_count == 0:
                status = "calendar_missing"
            elif act_count == 0:
                status = "empty"
            elif miss == 0:
                status = "complete"
            else:
                status = "partial"

            # First/last data dates
            first_d = min(actual) if actual else None
            last_d = max(actual) if actual else None

            report_args = {
                "symbol": sym, "exchange": ex, "asset_type": "stock",
                "data_type": args.data_type, "adj_type": adj_t,
                "start_date": args.start_date, "end_date": args.end_date,
                "expected_trade_days": exp_count, "actual_trade_days": act_count,
                "missing_trade_days": max(0, miss), "coverage_rate": rate,
                "first_data_date": first_d, "last_data_date": last_d,
                "status": status, "generated_at": datetime.now(),
            }

            gaps = detect_gaps(expected_all, actual)

            if not args.dry_run and args.confirm:
                report = cov_repo.upsert(**report_args)
                if report.report_id:
                    gap_repo.clear_report_gaps(report.report_id)
                    for g in gaps:
                        g["report_id"] = report.report_id
                        g["symbol"] = sym; g["exchange"] = ex
                        g["data_type"] = args.data_type; g["adj_type"] = adj_t
                    gap_repo.insert_batch(gaps)

            results.append({"symbol": sym, "exchange": ex, "adj": adj_t,
                           "expected": exp_count, "actual": act_count,
                           "missing": max(0, miss), "rate": rate,
                           "status": status, "gaps": len(gaps)})

    # Summary
    complete = sum(1 for r in results if r["status"] == "complete")
    partial = sum(1 for r in results if r["status"] == "partial")
    empty = sum(1 for r in results if r["status"] == "empty")
    cal_missing = sum(1 for r in results if r["status"] == "calendar_missing")

    print(f"\nTotal securities scanned: {total}")
    print(f"  complete: {complete}, partial: {partial}, empty: {empty}, calendar_missing: {cal_missing}")
    for r in results[:10]:
        print(f"  {r['symbol']}.{r['exchange']} {r['adj']:4s} expected={r['expected']} actual={r['actual']} missing={r['missing']} rate={r['rate']} status={r['status']} gaps={r['gaps']}")
    if len(results) > 10:
        print(f"  ... and {len(results) - 10} more")

    if args.dry_run or not args.confirm:
        print("\n[DRY-RUN] No data written. Use --confirm to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
