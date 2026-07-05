"""V1.4.2 Sync trading calendar.

Usage::

    python -m src.trading_calendar.sync_trading_calendar --start-date 20260101 --end-date 20260131 --exchange CN --dry-run
"""

from __future__ import annotations

import sys


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Sync trading calendar")
    p.add_argument("--start-date", default="20260101")
    p.add_argument("--end-date", default="20261231")
    p.add_argument("--exchange", default="CN")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--confirm", action="store_true", default=False)
    args = p.parse_args()

    days = (int(args.end_date[:4]) - int(args.start_date[:4]) + 1) * 365
    print(f"Range: {args.start_date} ~ {args.end_date} (~{days} days)")

    if not args.confirm:
        print("[DRY-RUN] No data written. Use --confirm to write.")
        return 0

    from src.trading_calendar.trading_calendar_service import TradingCalendarService
    svc = TradingCalendarService()
    count = svc.generate_weekdays(args.start_date, args.end_date, args.exchange)
    print(f"[WRITTEN] {count} days inserted/updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
