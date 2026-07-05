"""V1.4.1 MarketDataProvider abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    """Abstract interface for market data providers.

    All providers must implement these methods.
    Returns pandas.DataFrame with standardised columns.
    """

    provider_name: str = "base"

    @abstractmethod
    def health_check(self) -> dict:
        """Return health status dict.

        Must include: provider_name, status (healthy/degraded/down/disabled),
        latency_ms, error_message.
        """

    @abstractmethod
    def get_daily_bars(
        self, stock_code: str, start_date: str, end_date: str, adj_type: str = "raw"
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars.

        Returns DataFrame with columns: symbol, exchange, trade_date,
        open, high, low, close, volume, amount, adj_type, provider_name.
        """

    @abstractmethod
    def get_minute_bars(
        self, stock_code: str, start_date: str, end_date: str, period: str = "1min"
    ) -> pd.DataFrame:
        """Fetch minute-level bars (skeleton in V1.4.1)."""

    @abstractmethod
    def get_realtime_quote(self, stock_code: str) -> pd.DataFrame:
        """Fetch real-time quote snapshot (skeleton in V1.4.1)."""

    @abstractmethod
    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch trading calendar (skeleton in V1.4.1)."""

    @abstractmethod
    def get_stock_basic(self, stock_codes: list[str] | None = None) -> pd.DataFrame:
        """Fetch stock basic info (symbol, name, exchange, list_date, etc.)."""

    @abstractmethod
    def download_history(
        self, stock_code: str, start_date: str, end_date: str,
        period: str = "daily", adj_type: str = "raw",
    ) -> pd.DataFrame:
        """Download historical data and return standardised DataFrame."""
