"""V1.4.1 AkShareProvider — wraps existing AkShareClient in Provider interface."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from src.data_source.akshare_client import AkShareClient
from src.data_sources.base import MarketDataProvider
from src.data_sources.errors import (
    ProviderDataEmptyError,
    ProviderDataFormatError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from src.data_sources.field_mapper import validate_daily_bar_df

logger = logging.getLogger(__name__)


class AkShareProvider(MarketDataProvider):
    provider_name = "akshare"

    def __init__(self) -> None:
        self._client = AkShareClient()

    def health_check(self) -> dict:
        try:
            import akshare  # noqa: F401
        except Exception as e:
            return {
                "provider_name": self.provider_name,
                "status": "disabled",
                "latency_ms": 0,
                "error_message": f"akshare import failed: {type(e).__name__}",
            }
        return {
            "provider_name": self.provider_name,
            "status": "healthy",
            "latency_ms": 0,
            "error_message": "",
        }

    def _wrap_akshare_error(self, e: Exception) -> None:
        msg = str(e).lower()
        if "proxy" in msg or "connect" in msg or "timeout" in msg:
            raise ProviderUnavailableError(f"AkShare network error: {e}") from e
        if "rate" in msg or "limit" in msg:
            raise ProviderRateLimitError(f"AkShare rate limit: {e}") from e
        if "timeout" in msg:
            raise ProviderTimeoutError(f"AkShare timeout: {e}") from e
        raise ProviderUnavailableError(f"AkShare error: {e}") from e

    def get_daily_bars(
        self, stock_code: str, start_date: str, end_date: str, adj_type: str = "raw",
    ) -> pd.DataFrame:
        from src.universe.stock_pool import infer_exchange
        from src.data_sources.field_mapper import normalise_symbol_exchange

        symbol, exchange = normalise_symbol_exchange(stock_code)
        start = start_date.replace("-", "")[:8]
        end = end_date.replace("-", "")[:8]

        try:
            df = self._client.fetch_stock_daily(symbol, start, end, adj=adj_type)
        except Exception as e:
            self._wrap_akshare_error(e)
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(columns={"stock_code": "symbol"})
        df["exchange"] = infer_exchange(symbol)
        df["adj_type"] = adj_type
        df["provider_name"] = self.provider_name
        df["source_timestamp"] = datetime.now().isoformat()
        df["security_id"] = symbol + "." + exchange
        return validate_daily_bar_df(df)

    def get_stock_basic(self, stock_codes: list[str] | None = None) -> pd.DataFrame:
        try:
            info = self._client.get_stock_basic_info(stock_codes[0] if stock_codes else "000001")
            return pd.DataFrame([info]) if info.get("stock_name") else pd.DataFrame()
        except Exception as e:
            raise ProviderUnavailableError(f"AkShare stock_basic failed: {e}") from e

    # ── Skeletons ───────────────────────────────────────────────

    def get_minute_bars(self, stock_code: str, start_date: str, end_date: str, period: str = "1min") -> pd.DataFrame:
        raise ProviderUnavailableError("AkShare minute bars not implemented")

    def get_realtime_quote(self, stock_code: str) -> pd.DataFrame:
        raise ProviderUnavailableError("AkShare real-time quote not implemented")

    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        raise ProviderUnavailableError("AkShare trading calendar not implemented")

    def download_history(
        self, stock_code: str, start_date: str, end_date: str,
        period: str = "daily", adj_type: str = "raw",
    ) -> pd.DataFrame:
        return self.get_daily_bars(stock_code, start_date, end_date, adj_type)
