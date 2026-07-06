"""V1.4.6 Sync trading calendar — Provider-driven with weekday fallback.

Usage::

    python -m src.trading_calendar.sync_trading_calendar --start-date 20240101 --end-date 20241231 --exchange CN --dry-run
    python -m src.trading_calendar.sync_trading_calendar --start-date 20240101 --end-date 20241231 --exchange CN --confirm
"""

from __future__ import annotations

import sys
from datetime import datetime


def _validate_dates(start_date: str, end_date: str) -> str | None:
    """Validate date format YYYYMMDD and start <= end. Returns error or None."""
    if len(start_date) != 8 or len(end_date) != 8:
        return "Dates must be in YYYYMMDD format (8 digits)"
    if not start_date.isdigit() or not end_date.isdigit():
        return "Dates must be numeric YYYYMMDD"
    try:
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
    except ValueError:
        return "Dates must be valid calendar dates in YYYYMMDD format"
    if start > end:
        return f"start_date ({start_date}) must be <= end_date ({end_date})"
    return None


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="V1.4.6 Sync trading calendar — Provider-driven with fallback",
    )
    p.add_argument("--start-date", default="20240101", help="Start date YYYYMMDD")
    p.add_argument("--end-date", default="20241231", help="End date YYYYMMDD")
    p.add_argument("--exchange", default="CN", help="Exchange code (default: CN)")
    p.add_argument("--provider", default=None, help="Preferred provider (optional)")
    p.add_argument("--dry-run", action="store_true", default=True,
                   help="Preview only (default: True)")
    p.add_argument("--confirm", action="store_true", default=False,
                   help="Actually write to database")
    args = p.parse_args()

    # Validate dates
    err = _validate_dates(args.start_date, args.end_date)
    if err:
        print(f"[ERROR] {err}")
        return 1

    # Try Provider-driven calendar
    is_real = False
    source_provider = "weekday_fallback"
    open_count = 0
    df_cal = None

    try:
        from src.data_sources.market_data_service import MarketDataService
        from src.data_sources.errors import ProviderDataEmptyError
        svc = MarketDataService()
        df_cal, prov = svc.get_trading_calendar(
            args.start_date, args.end_date, args.exchange, args.provider,
        )
        is_real = True
        source_provider = prov
        open_count = len(df_cal)
    except (ProviderDataEmptyError, Exception) as e:
        print(f"[WARN] Provider trading calendar unavailable: {e}")
        print("[WARN] Falling back to weekday calendar (Mon-Fri).")
        is_real = False
        source_provider = "weekday_fallback"

    # Compute expected open days for weekday fallback
    if not is_real:
        sd = datetime.strptime(args.start_date, "%Y%m%d")
        ed = datetime.strptime(args.end_date, "%Y%m%d")
        d = sd
        while d <= ed:
            if d.weekday() < 5:  # Mon-Fri
                open_count += 1
            d = __import__('datetime').timedelta(days=1) + d

    total_days = (datetime.strptime(args.end_date, "%Y%m%d") -
                  datetime.strptime(args.start_date, "%Y%m%d")).days + 1
    closed_count = total_days - open_count

    # ── Output ──────────────────────────────────────────────────────────
    print(f"\nTrading calendar sync plan:")
    print(f"  exchange        : {args.exchange}")
    print(f"  start_date      : {args.start_date}")
    print(f"  end_date        : {args.end_date}")
    print(f"  source_provider : {source_provider}")
    print(f"  is_real_calendar: {is_real}")
    print(f"  open_days       : {open_count}")
    print(f"  closed_days     : {closed_count}")
    print(f"  dry_run         : {not args.confirm}")

    if not is_real:
        print(f"  [WARN] Using fallback trading calendar. Coverage result may be inaccurate.")

    if not args.confirm:
        print(f"\n[DRY-RUN] No data written. Use --confirm to write.")
        return 0

    # ── Write ───────────────────────────────────────────────────────────
    from src.db.migrations import init_meta_db
    from src.trading_calendar.trading_calendar_service import TradingCalendarService

    init_meta_db()
    tsvc = TradingCalendarService()

    if is_real and df_cal is not None:
        count = tsvc.bulk_upsert_from_provider(
            df_cal, exchange=args.exchange, source_provider=source_provider,
        )
        print(f"\n[WRITTEN] {count} real trading days from {source_provider}.")
    else:
        count = tsvc.generate_weekdays(args.start_date, args.end_date, args.exchange)
        print(f"\n[WRITTEN] {count} weekday-generated days (is_real_calendar=False).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
