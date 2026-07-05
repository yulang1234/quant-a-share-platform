"""V1.4.1 Fetch daily bars via MarketDataService.

Usage::

    python -m src.data_sources.fetch_daily --stock-code 000001.SZ --start-date 20240101 --end-date 20240701 --adj raw
"""

from __future__ import annotations

import sys


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Fetch daily bars via MarketDataService")
    p.add_argument("--stock-code", required=True, help="e.g. 000001.SZ")
    p.add_argument("--start-date", required=True, help="YYYYMMDD")
    p.add_argument("--end-date", required=True, help="YYYYMMDD")
    p.add_argument("--adj", default="raw", choices=["raw", "qfq"])
    p.add_argument(
        "--no-save",
        action="store_true",
        help="Compatibility flag. V1.4.1 fetch_daily is read-only and does not save bars.",
    )
    args = p.parse_args()

    from src.data_sources.market_data_service import MarketDataService
    from src.data_sources.errors import ProviderDataEmptyError

    svc = MarketDataService()
    try:
        df, provider_used = svc.get_daily_bars(
            args.stock_code, args.start_date, args.end_date, args.adj,
        )
        print(f"Provider used : {provider_used}")
        print(f"Rows returned : {len(df)}")
        if args.no_save:
            print("Save mode     : disabled")
        if not df.empty:
            print(f"Columns       : {list(df.columns)}")
            print(df.head(10).to_string())
        else:
            print("[No data returned]")
    except ProviderDataEmptyError as e:
        print(f"[All providers failed] {e}")
        return 1
    except Exception as e:
        print(f"[Error] {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
