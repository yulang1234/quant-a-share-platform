"""V1.4.1 TushareProvider — skeleton for future Tushare integration.

Requires TUSHARE_TOKEN environment variable.
If token is missing, health_check returns disabled.
"""

from __future__ import annotations

import logging
import os

import pandas as pd

from src.data_sources.base import MarketDataProvider
from src.data_sources.errors import ProviderAuthError, ProviderUnavailableError

logger = logging.getLogger(__name__)


class TushareProvider(MarketDataProvider):
    provider_name = "tushare"

    _TOKEN_ENV = "TUSHARE_TOKEN"

    def health_check(self) -> dict:
        token = os.getenv(self._TOKEN_ENV, "")
        if not token:
            return {
                "provider_name": self.provider_name,
                "status": "disabled",
                "latency_ms": 0,
                "error_message": f"{self._TOKEN_ENV} not set; Tushare is disabled",
            }
        # Token exists but we don't test connectivity in V1.4.1
        return {
            "provider_name": self.provider_name,
            "status": "healthy",
            "latency_ms": 0,
            "error_message": "",
        }

    def get_daily_bars(
        self, stock_code: str, start_date: str, end_date: str, adj_type: str = "raw",
    ) -> pd.DataFrame:
        raise ProviderUnavailableError(
            "Tushare daily bars not implemented (V1.4.2). "
            f"Set {self._TOKEN_ENV} to enable."
        )

    def get_minute_bars(self, stock_code: str, start_date: str, end_date: str, period: str = "1min") -> pd.DataFrame:
        raise ProviderUnavailableError("Tushare minute bars not implemented (V1.4.2)")

    def get_realtime_quote(self, stock_code: str) -> pd.DataFrame:
        raise ProviderUnavailableError("Tushare real-time quote not implemented (V1.4.2)")

    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        raise ProviderUnavailableError("Tushare trading calendar not implemented (V1.4.2)")

    def get_stock_basic(self, stock_codes: list[str] | None = None) -> pd.DataFrame:
        raise ProviderUnavailableError("Tushare stock basic not implemented (V1.4.2)")

    def download_history(
        self, stock_code: str, start_date: str, end_date: str,
        period: str = "daily", adj_type: str = "raw",
    ) -> pd.DataFrame:
        raise ProviderUnavailableError("Tushare download_history not implemented (V1.4.2)")
