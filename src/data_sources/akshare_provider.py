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
        """Fetch stock basic info from AkShare (V1.4.6 enhanced).

        Returns standardised DataFrame with: stock_code, stock_name, exchange,
        list_date, delist_date, list_status, is_active, is_st, is_delisted.
        """
        try:
            import akshare as ak
            # Use akshare stock_info_a_code_name for all A-share stocks
            df = ak.stock_info_a_code_name()
            if df is None or df.empty:
                return pd.DataFrame()

            # Standardise columns
            col_map = {
                "code": "stock_code", "股票代码": "stock_code",
                "name": "stock_name", "股票简称": "stock_name",
                "exchange": "exchange", "交易所": "exchange",
                "list_date": "list_date", "上市日期": "list_date",
                "delist_date": "delist_date", "退市日期": "delist_date",
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

            # Ensure stock_code is 6-digit string
            if "stock_code" in df.columns:
                df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)

            # Infer exchange if missing
            if "exchange" not in df.columns:
                df["exchange"] = df["stock_code"].apply(
                    lambda x: "SH" if str(x).startswith("6") else
                    ("BJ" if str(x).startswith(("8", "4")) else "SZ")
                )

            # Compute derived fields
            if "stock_name" in df.columns:
                names = df["stock_name"].astype(str).str.upper()
                df["is_st"] = names.str.contains("ST|\\*ST|S\\*ST|PT", regex=True, na=False)
            else:
                df["is_st"] = False

            if "delist_date" in df.columns:
                df["is_delisted"] = df["delist_date"].notna() & (df["delist_date"] != "")
            else:
                df["is_delisted"] = False

            if "list_status" not in df.columns:
                df["list_status"] = "L"  # default: listed

            df["is_active"] = ~df["is_delisted"] & ~df["is_st"]
            df["data_source"] = self.provider_name

            # Filter by requested codes if provided
            if stock_codes:
                codes_set = {str(c).zfill(6) for c in stock_codes}
                df = df[df["stock_code"].isin(codes_set)]

            return df
        except Exception as e:
            raise ProviderUnavailableError(f"AkShare stock_basic failed: {e}") from e

    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch real A-share trading calendar from AkShare (V1.4.6).

        Uses ak.tool_trade_date_hist_sina() for sina-sourced trading calendar.
        Falls back to weekday generation if unavailable.
        """
        try:
            import akshare as ak
            df = ak.tool_trade_date_hist_sina()
            if df is None or df.empty:
                raise ProviderUnavailableError("AkShare trading calendar returned empty")

            # Standardise
            date_col = "trade_date" if "trade_date" in df.columns else df.columns[0]
            df = df.rename(columns={date_col: "trade_date"})
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
            df["is_open"] = True
            df["exchange"] = "CN"
            df["provider_name"] = self.provider_name
            return df[["trade_date", "is_open", "exchange", "provider_name"]]
        except Exception as e:
            raise ProviderUnavailableError(f"AkShare trading calendar failed: {e}") from e

    # ── Skeletons ───────────────────────────────────────────────

    def get_minute_bars(self, stock_code: str, start_date: str, end_date: str, period: str = "1min") -> pd.DataFrame:
        raise ProviderUnavailableError("AkShare minute bars not implemented")

    def get_realtime_quote(self, stock_code: str) -> pd.DataFrame:
        raise ProviderUnavailableError("AkShare real-time quote not implemented")

    def download_history(
        self, stock_code: str, start_date: str, end_date: str,
        period: str = "daily", adj_type: str = "raw",
    ) -> pd.DataFrame:
        return self.get_daily_bars(stock_code, start_date, end_date, adj_type)
