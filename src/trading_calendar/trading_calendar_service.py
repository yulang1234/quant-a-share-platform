"""V1.4.6 Trading calendar service — insert and query trading days.

Supports real exchange calendars (via Provider) and weekday fallback.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.db.schema_meta import TradingCalendar
from src.repositories.meta_db import get_session


class TradingCalendarService:
    def __init__(self, session: Session | None = None):
        self._s = session or get_session()

    def upsert_trading_day(self, trade_date, exchange: str = "CN", is_open: bool = True,
                           is_weekend: bool = False, is_holiday: bool = False,
                           source: str = "manual",
                           calendar_source: str = "generated",
                           is_real_calendar: bool = False,
                           source_provider: str | None = None,
                           source_updated_at: datetime | None = None) -> TradingCalendar:
        td = trade_date if isinstance(trade_date, datetime) else datetime.strptime(str(trade_date)[:10], "%Y-%m-%d")
        existing = self._s.query(TradingCalendar).filter_by(trade_date=td, exchange=exchange).first()
        if existing:
            existing.is_open = is_open
            existing.is_weekend = is_weekend
            existing.is_holiday = is_holiday
            existing.source = source
            existing.calendar_source = calendar_source
            existing.is_real_calendar = is_real_calendar
            if source_provider:
                existing.source_provider = source_provider
            if source_updated_at:
                existing.source_updated_at = source_updated_at
            self._s.commit()
            return existing
        cal = TradingCalendar(
            trade_date=td, exchange=exchange, is_open=is_open,
            is_weekend=is_weekend, is_holiday=is_holiday, source=source,
            calendar_source=calendar_source, is_real_calendar=is_real_calendar,
            source_provider=source_provider, source_updated_at=source_updated_at,
        )
        self._s.add(cal); self._s.commit()
        return cal

    def bulk_upsert_from_provider(
        self, df, exchange: str = "CN", source_provider: str = "",
    ) -> int:
        """Insert/update trading calendar rows from a provider DataFrame.

        Expected columns: trade_date, is_open
        """
        now = datetime.now()
        count = 0
        for _, row in df.iterrows():
            td = row["trade_date"]
            is_open = bool(row.get("is_open", True))
            is_weekend = td.weekday() >= 5 if hasattr(td, "weekday") else False
            self.upsert_trading_day(
                trade_date=td,
                exchange=exchange,
                is_open=is_open,
                is_weekend=is_weekend,
                is_holiday=not is_open and not is_weekend,
                source="provider",
                calendar_source=source_provider,
                is_real_calendar=True,
                source_provider=source_provider,
                source_updated_at=now,
            )
            count += 1
        self.update_adjacent_dates(exchange)
        return count

    def get_calendar_source_info(self, exchange: str = "CN") -> dict:
        """Return info about the current calendar source.

        Returns dict with is_real_calendar, source_provider, calendar_source, open_days_count.
        """
        rows = self._s.query(TradingCalendar).filter(
            TradingCalendar.exchange == exchange, TradingCalendar.is_open == True  # noqa: E712
        ).all()
        if not rows:
            return {"is_real_calendar": False, "source_provider": None,
                    "calendar_source": "none", "open_days_count": 0}
        # Check if any rows are real
        real = any(r.is_real_calendar for r in rows)
        sources = list({r.calendar_source for r in rows if r.calendar_source})
        providers = list({r.source_provider for r in rows if r.source_provider})
        return {
            "is_real_calendar": real,
            "source_provider": providers[0] if providers else None,
            "calendar_source": sources[0] if sources else "generated",
            "open_days_count": len(rows),
        }

    def update_adjacent_dates(self, exchange: str = "CN") -> int:
        """Compute pre_trade_date and next_trade_date for is_open=true rows."""
        all_open = self._s.query(TradingCalendar).filter(
            TradingCalendar.exchange == exchange, TradingCalendar.is_open == True  # noqa: E712
        ).order_by(TradingCalendar.trade_date).all()
        if len(all_open) < 2:
            return 0
        updated = 0
        for i, cal in enumerate(all_open):
            cal.pre_trade_date = all_open[i - 1].trade_date if i > 0 else None
            cal.next_trade_date = all_open[i + 1].trade_date if i < len(all_open) - 1 else None
            updated += 1
        self._s.commit()
        return updated

    def generate_weekdays(self, start_date: str, end_date: str, exchange: str = "CN") -> int:
        """Generate weekday calendar (Mon-Fri as open, Sat-Sun as weekend).

        V1.4.6: now marks generated calendars with is_real_calendar=False.
        """
        sd = datetime.strptime(start_date[:10].replace("-", ""), "%Y%m%d") if "-" not in start_date else datetime.strptime(start_date[:10], "%Y-%m-%d")
        ed = datetime.strptime(end_date[:10].replace("-", ""), "%Y%m%d") if "-" not in end_date else datetime.strptime(end_date[:10], "%Y-%m-%d")
        count = 0
        d = sd
        while d <= ed:
            is_weekend = d.weekday() >= 5
            is_open = not is_weekend
            self.upsert_trading_day(
                d, exchange=exchange, is_open=is_open, is_weekend=is_weekend,
                source="generated", calendar_source="weekday_fallback",
                is_real_calendar=False,
            )
            count += 1
            d += timedelta(days=1)
        self.update_adjacent_dates(exchange)
        return count

    def list_open_dates(self, start_date: str, end_date: str, exchange: str = "CN") -> list:
        sd = datetime.strptime(start_date[:10], "%Y-%m-%d") if "-" in start_date else datetime.strptime(start_date[:8], "%Y%m%d")
        ed = datetime.strptime(end_date[:10], "%Y-%m-%d") if "-" in end_date else datetime.strptime(end_date[:8], "%Y%m%d")
        return self._s.query(TradingCalendar).filter(
            TradingCalendar.exchange == exchange,
            TradingCalendar.is_open == True,  # noqa: E712
            TradingCalendar.trade_date >= sd,
            TradingCalendar.trade_date <= ed,
        ).order_by(TradingCalendar.trade_date).all()

    def count_open_days(self, start_date: str, end_date: str, exchange: str = "CN") -> int:
        """Return the number of open trading days in a range."""
        return len(self.list_open_dates(start_date, end_date, exchange))
