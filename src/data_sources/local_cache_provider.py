"""V1.4.1 LocalCacheProvider — reads existing DuckDB/Parquet daily data."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from src.data_sources.base import MarketDataProvider
from src.data_sources.errors import ProviderUnavailableError
from src.data_sources.field_mapper import apply_provider_name, normalise_symbol_exchange, validate_daily_bar_df
from src.storage.duckdb_repo import query_df

logger = logging.getLogger(__name__)


def _norm_date(d: str) -> str:
    """Normalise YYYYMMDD or YYYY-MM-DD to YYYY-MM-DD."""
    d = d.replace("-", "").strip()
    if len(d) == 8:
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return d


class LocalCacheProvider(MarketDataProvider):
    provider_name = "local_cache"

    def health_check(self) -> dict:
        try:
            df = query_df("SELECT COUNT(*) AS c FROM stock_daily_qfq")
            cnt = int(df.iloc[0]["c"]) if not df.empty else 0
            return {
                "provider_name": self.provider_name,
                "status": "healthy" if cnt > 0 else "degraded",
                "latency_ms": 0,
                "error_message": "" if cnt > 0 else "no cached daily data",
            }
        except Exception as e:
            return {
                "provider_name": self.provider_name,
                "status": "down",
                "latency_ms": 0,
                "error_message": str(e),
            }

    def _read_table(self, adj_type: str) -> str:
        return "stock_daily_qfq" if adj_type == "qfq" else "stock_daily_raw"

    def get_daily_bars(
        self, stock_code: str, start_date: str, end_date: str, adj_type: str = "raw",
    ) -> pd.DataFrame:
        symbol, exchange = normalise_symbol_exchange(stock_code)
        table = self._read_table(adj_type)
        # Normalise dates to YYYY-MM-DD for DuckDB
        sd = _norm_date(start_date)
        ed = _norm_date(end_date)
        try:
            df = query_df(
                f"SELECT stock_code, trade_date, open, high, low, close, volume, amount "
                f"FROM {table} WHERE stock_code = ? AND trade_date >= ? AND trade_date <= ? "
                f"ORDER BY trade_date",
                [symbol, sd, ed],
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.rename(columns={"stock_code": "symbol"})
            df["exchange"] = exchange
            df["adj_type"] = adj_type
            df["provider_name"] = self.provider_name
            df["source_timestamp"] = datetime.now().isoformat()
            df["security_id"] = symbol + "." + exchange
            return validate_daily_bar_df(df)
        except Exception as e:
            logger.warning("LocalCache get_daily_bars failed: %s", e)
            raise ProviderUnavailableError(f"Local cache read error: {e}") from e

    def get_minute_bars(self, stock_code: str, start_date: str, end_date: str, period: str = "1min") -> pd.DataFrame:
        raise ProviderUnavailableError("Local cache does not support minute bars")

    def get_realtime_quote(self, stock_code: str) -> pd.DataFrame:
        raise ProviderUnavailableError("Local cache does not support real-time quotes")

    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Read trading calendar from local meta DB (V1.4.6)."""
        try:
            from src.trading_calendar.trading_calendar_service import TradingCalendarService
            svc = TradingCalendarService()
            dates = svc.list_open_dates(start_date, end_date, "CN")
            if not dates:
                return pd.DataFrame()
            rows = []
            for d in dates:
                rows.append({
                    "trade_date": d.trade_date,
                    "is_open": d.is_open,
                    "exchange": d.exchange,
                    "provider_name": self.provider_name,
                })
            return pd.DataFrame(rows)
        except Exception as e:
            raise ProviderUnavailableError(f"LocalCache trading calendar failed: {e}") from e

    def get_stock_basic(self, stock_codes: list[str] | None = None) -> pd.DataFrame:
        """Read stock basic info from local security_master (V1.4.6)."""
        try:
            from src.repositories.security_master_repo import SecurityMasterRepository
            repo = SecurityMasterRepository()
            all_secs = repo.list_all(limit=10000)
            rows = []
            for s in all_secs:
                rows.append({
                    "stock_code": str(s.symbol).zfill(6),
                    "stock_name": s.security_name or "",
                    "exchange": s.exchange or "SZ",
                    "list_date": s.list_date,
                    "delist_date": s.delist_date,
                    "list_status": s.status or "active",
                    "is_active": s.status == "active",
                    "is_st": bool(s.is_st),
                    "is_delisted": s.status == "delisted",
                    "data_source": "local_cache",
                })
            df = pd.DataFrame(rows) if rows else pd.DataFrame()
            if stock_codes and not df.empty:
                codes_set = {str(c).zfill(6) for c in stock_codes}
                df = df[df["stock_code"].isin(codes_set)]
            return df
        except Exception as e:
            raise ProviderUnavailableError(f"LocalCache stock_basic failed: {e}") from e

    def download_history(
        self, stock_code: str, start_date: str, end_date: str,
        period: str = "daily", adj_type: str = "raw",
    ) -> pd.DataFrame:
        return self.get_daily_bars(stock_code, start_date, end_date, adj_type)
