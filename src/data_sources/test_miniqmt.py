"""V1.4.1 MiniQMT test CLI.

Usage::

    python -m src.data_sources.test_miniqmt --stock-code 000001.SZ --start-date 20240101 --end-date 20240701
"""

from __future__ import annotations

import sys


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Test MiniQMTProvider daily bars")
    p.add_argument("--stock-code", required=True, help="e.g. 000001.SZ")
    p.add_argument("--start-date", required=True, help="YYYYMMDD")
    p.add_argument("--end-date", required=True, help="YYYYMMDD")
    args = p.parse_args()

    from src.data_sources.miniqmt_provider import MiniQMTProvider

    provider = MiniQMTProvider()
    health = provider.health_check()
    print(f"Health: {health['status']}")
    if health["error_message"]:
        print(f"  Message: {health['error_message']}")
        if health["status"] in ("disabled", "down"):
            print("\n[MiniQMT is not available. The project can still operate without it.]")
            return 0

    try:
        df = provider.get_daily_bars(args.stock_code, args.start_date, args.end_date)
        print(f"Rows returned: {len(df)}")
        if not df.empty:
            print(df.head(5).to_string())
    except Exception as e:
        print(f"[Error] {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
