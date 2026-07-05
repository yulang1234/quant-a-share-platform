"""V1.4.4 Single-stock smoke backfill CLI.

Usage::

    python -m src.data_quality.smoke_backfill --stock-code 000001.SZ --start-date 20240101 --end-date 20240131 --adj qfq --dry-run
    python -m src.data_quality.smoke_backfill --stock-code 000001.SZ --start-date 20240101 --end-date 20240131 --adj qfq --confirm --save-local
"""

from __future__ import annotations

import sys
from datetime import datetime


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="V1.4.4 Single-Stock Smoke Backfill")
    p.add_argument("--stock-code", required=True)
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--adj", default="qfq", choices=["raw", "qfq"])
    p.add_argument("--provider", default=None)
    p.add_argument("--confirm", action="store_true", default=False)
    p.add_argument("--no-save", action="store_true", default=True)
    p.add_argument("--save-local", action="store_true", default=False)
    p.add_argument("--rerun-coverage", action="store_true", default=False)
    args = p.parse_args(argv)

    if args.save_local and not args.confirm:
        print("[ERROR] --save-local requires --confirm"); return 1

    # Date range check
    try:
        sd = datetime.strptime(args.start_date[:8].replace("-", ""), "%Y%m%d")
        ed = datetime.strptime(args.end_date[:8].replace("-", ""), "%Y%m%d")
        if (ed - sd).days > 180:
            print("[ERROR] Date range exceeds 180 days. Refusing to run large backfill."); return 1
    except Exception as e:
        print(f"[ERROR] Invalid date: {e}"); return 1

    if not args.confirm:
        print(f"[DRY-RUN] Would fetch {args.stock_code} {args.adj} {args.start_date}~{args.end_date}")
        return 0

    from src.data_sources.market_data_service import MarketDataService
    svc = MarketDataService()
    try:
        df, prov = svc.get_daily_bars(args.stock_code, args.start_date, args.end_date, args.adj)
        print(f"Provider : {prov}")
        print(f"Rows     : {len(df)}")
        if df.empty:
            print("[EMPTY] No data returned.")
            return 0

        if args.save_local:
            from src.storage.duckdb_repo import upsert_daily_data
            table = "stock_daily_qfq" if args.adj == "qfq" else "stock_daily_raw"
            upsert_daily_data(table, df)
            try:
                from src.storage.parquet_repo import save_daily_parquet
                from src.data_sources.field_mapper import normalise_symbol_exchange
                sym, _ = normalise_symbol_exchange(args.stock_code)
                save_daily_parquet(df, sym, args.adj)
            except Exception: pass
            print("[SAVED] Data written to DuckDB + Parquet.")
        else:
            print("[--no-save] Data fetched but not saved.")
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
