"""
Date utilities for the quant research platform.

Provides helpers for trading-day arithmetic, date range generation,
and string/date conversions commonly used across modules.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


# ── Date range helpers ──────────────────────────────────────────────────

TRADE_CALENDAR_START = date(2005, 1, 1)
"""Earliest date for which we might load data (≈20 years)."""


def today_str() -> str:
    """Return today's date as ``"YYYY-MM-DD"``."""
    return date.today().isoformat()


def parse_date(d: str | date | datetime) -> date:
    """Convert a string or datetime to a ``date`` object.

    Parameters
    ----------
    d : str or date or datetime
        If a string, accepted formats are ``"YYYY-MM-DD"`` or ``"YYYYMMDD"``.

    Returns
    -------
    date
    """
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    cleaned = d.replace("-", "")
    return datetime.strptime(cleaned, "%Y%m%d").date()


def twenty_years_ago() -> date:
    """Return the date 20 years before today.

    Used as the default start date for historical data init.
    """
    return date.today() - timedelta(days=365 * 20)
