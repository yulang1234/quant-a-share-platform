"""V1.4.2 Trading calendar service — insert and query trading days."""

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
                           source: str = "manual") -> TradingCalendar:
        td = trade_date if isinstance(trade_date, datetime) else datetime.strptime(str(trade_date)[:10], "%Y-%m-%d")
        existing = self._s.query(TradingCalendar).filter_by(trade_date=td, exchange=exchange).first()
        if existing:
            existing.is_open = is_open
            existing.is_weekend = is_weekend
            existing.is_holiday = is_holiday
            existing.source = source
            self._s.commit()
            return existing
        cal = TradingCalendar(trade_date=td, exchange=exchange, is_open=is_open,
                              is_weekend=is_weekend, is_holiday=is_holiday, source=source)
        self._s.add(cal); self._s.commit()
        return cal

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
        """Generate weekday calendar (Mon-Fri as open, Sat-Sun as weekend)."""
        sd = datetime.strptime(start_date[:10].replace("-", ""), "%Y%m%d") if "-" not in start_date else datetime.strptime(start_date[:10], "%Y-%m-%d")
        ed = datetime.strptime(end_date[:10].replace("-", ""), "%Y%m%d") if "-" not in end_date else datetime.strptime(end_date[:10], "%Y-%m-%d")
        count = 0
        d = sd
        while d <= ed:
            is_weekend = d.weekday() >= 5
            is_open = not is_weekend
            self.upsert_trading_day(d, exchange=exchange, is_open=is_open, is_weekend=is_weekend, source="generated")
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
