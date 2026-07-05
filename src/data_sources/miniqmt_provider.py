"""V1.4.1 MiniQMTProvider — xtdata-based market data (optional).

Only uses xtquant.xtdata — never xttrader.
Lazy-imports xtquant so the project starts without MiniQMT installed.
"""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from src.data_sources.base import MarketDataProvider
from src.data_sources.errors import (
    ProviderAuthError,
    ProviderDataEmptyError,
    ProviderUnavailableError,
)
from src.data_sources.field_mapper import apply_provider_name, normalise_symbol_exchange, validate_daily_bar_df

logger = logging.getLogger(__name__)


def _try_import_xtdata():
    """Lazy-import xtquant.xtdata. Returns the module or None."""
    try:
        import xtquant.xtdata as xtdata  # type: ignore[import-untyped]
        return xtdata
    except ImportError:
        return None
    except Exception as e:
        logger.debug("xtquant import error: %s", e)
        return None


class MiniQMTProvider(MarketDataProvider):
    provider_name = "miniqmt"

    def __init__(self) -> None:
        self._xtdata = _try_import_xtdata()

    def _ensure_available(self) -> None:
        if self._xtdata is None:
            raise ProviderUnavailableError(
                "MiniQMT / xtquant is not installed. "
                "Install xtquant from your QMT directory to enable MiniQMTProvider."
            )

    def health_check(self) -> dict:
        if self._xtdata is None:
            return {
                "provider_name": self.provider_name,
                "status": "disabled",
                "latency_ms": 0,
                "error_message": "xtquant not installed",
            }
        try:
            # Quick connectivity check: download one day for a known stock
            import time
            t0 = time.time()
            data = self._xtdata.get_market_data_ex(
                stock_list=["000001.SZ"], period="1d",
                start_time="20240101", end_time="20240102",
            )
            latency = int((time.time() - t0) * 1000)
            ok = data is not None and (hasattr(data, "empty") and not data.empty if hasattr(data, "empty") else bool(data))
            return {
                "provider_name": self.provider_name,
                "status": "healthy" if ok else "degraded",
                "latency_ms": latency,
                "error_message": "" if ok else "MiniQMT returned no data",
            }
        except Exception as e:
            return {
                "provider_name": self.provider_name,
                "status": "down",
                "latency_ms": 0,
                "error_message": f"MiniQMT unreachable: {e}",
            }

    def get_daily_bars(
        self, stock_code: str, start_date: str, end_date: str, adj_type: str = "raw",
    ) -> pd.DataFrame:
        self._ensure_available()
        symbol, exchange = normalise_symbol_exchange(stock_code)
        xt_code = f"{symbol}.{exchange}"
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")

        try:
            data = self._xtdata.get_market_data_ex(  # type: ignore[union-attr]
                stock_list=[xt_code], period="1d",
                start_time=start, end_time=end,
            )
            if data is None or (hasattr(data, "empty") and data.empty):
                return pd.DataFrame()

            # xtdata returns a dict of DataFrames keyed by field name
            if isinstance(data, dict):
                fields = list(data.keys())
                if not fields:
                    return pd.DataFrame()
                # Try to assemble from dict
                try:
                    df = pd.DataFrame(data)
                    df = df.reset_index()
                except Exception:
                    return pd.DataFrame()
            else:
                df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)

            if df.empty:
                return pd.DataFrame()

            # Standardise columns
            col_map = {
                "open": "open", "high": "high", "low": "low", "close": "close",
                "volume": "volume", "amount": "amount",
                "time": "trade_date", "date": "trade_date",
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            # Ensure trade_date
            if "trade_date" not in df.columns and "index" in df.columns:
                df["trade_date"] = df["index"]
            df["symbol"] = symbol
            df["exchange"] = exchange
            df["adj_type"] = adj_type
            df["provider_name"] = self.provider_name
            df["security_id"] = xt_code
            df["source_timestamp"] = datetime.now().isoformat()
            return validate_daily_bar_df(df)

        except ProviderError:
            raise
        except Exception as e:
            raise ProviderUnavailableError(f"MiniQMT get_daily_bars failed: {e}") from e

    # ── Skeleton methods ───────────────────────────────────────

    def get_minute_bars(self, stock_code: str, start_date: str, end_date: str, period: str = "1min") -> pd.DataFrame:
        raise ProviderUnavailableError("MiniQMT minute bars not implemented (V1.4.2)")

    def get_realtime_quote(self, stock_code: str) -> pd.DataFrame:
        raise ProviderUnavailableError("MiniQMT real-time quote not implemented (V1.4.2)")

    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        raise ProviderUnavailableError("MiniQMT trading calendar not implemented (V1.4.2)")

    def get_stock_basic(self, stock_codes: list[str] | None = None) -> pd.DataFrame:
        raise ProviderUnavailableError("MiniQMT stock basic not implemented (V1.4.2)")

    def download_history(
        self, stock_code: str, start_date: str, end_date: str,
        period: str = "daily", adj_type: str = "raw",
    ) -> pd.DataFrame:
        return self.get_daily_bars(stock_code, start_date, end_date, adj_type)
