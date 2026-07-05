"""V1.4.1 MarketDataService — unified provider orchestration with fallback."""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd

from src.data_sources.akshare_provider import AkShareProvider
from src.data_sources.base import MarketDataProvider
from src.data_sources.errors import ProviderDataEmptyError, ProviderError
from src.data_sources.local_cache_provider import LocalCacheProvider
from src.data_sources.miniqmt_provider import MiniQMTProvider
from src.data_sources.provider_config import (
    DAILY_QFQ_PRIORITY,
    DAILY_RAW_PRIORITY,
    REALTIME_QUOTE_PRIORITY,
    STOCK_BASIC_PRIORITY,
    TRADING_CALENDAR_PRIORITY,
)
from src.data_sources.tushare_provider import TushareProvider
from src.repositories.provider_repo import ProviderCallLogRepository, ProviderHealthRepository

logger = logging.getLogger(__name__)


class MarketDataService:
    """Unified market data access with provider fallback and call logging."""

    def __init__(self) -> None:
        self._providers: dict[str, MarketDataProvider] = {
            "local_cache": LocalCacheProvider(),
            "miniqmt": MiniQMTProvider(),
            "tushare": TushareProvider(),
            "akshare": AkShareProvider(),
        }
        self._log_repo = ProviderCallLogRepository()
        self._health_repo = ProviderHealthRepository()

    def _priority_for(self, adj_type: str) -> list[str]:
        if adj_type == "qfq":
            return list(DAILY_QFQ_PRIORITY)
        return list(DAILY_RAW_PRIORITY)

    def _log_call(self, provider_name: str, method: str, status: str,
                  symbol: str = "", exchange: str = "", duration_ms: int = 0,
                  row_count: int = 0, error_type: str = "", error_message: str = "",
                  start_date: str = "", end_date: str = "", adj_type: str = "") -> None:
        try:
            self._log_repo.log_call(
                provider_name=provider_name, method_name=method, status=status,
                symbol=symbol, exchange=exchange, duration_ms=duration_ms,
                row_count=row_count, error_type=error_type,
                error_message=(error_message or "")[:1000],
                start_date=start_date, end_date=end_date, adj_type=adj_type,
            )
        except Exception as e:
            logger.debug("call_log write skipped: %s", e)

    def _update_health(self, provider_name: str, result: dict) -> None:
        try:
            self._health_repo.upsert(
                provider_name=provider_name, status=result.get("status", "down"),
                latency_ms=result.get("latency_ms", 0),
                error_type="",
                error_message=(result.get("error_message", "") or "")[:500],
            )
        except Exception as e:
            logger.debug("health update skipped: %s", e)

    def get_daily_bars(
        self, stock_code: str, start_date: str, end_date: str,
        adj_type: str = "raw",
    ) -> tuple[pd.DataFrame, str]:
        """Fetch daily bars with fallback. Returns (DataFrame, provider_used)."""
        priorities = self._priority_for(adj_type)

        last_error = ""
        for pname in priorities:
            provider = self._providers.get(pname)
            if provider is None:
                continue

            # Check health
            try:
                health = provider.health_check()
                self._update_health(pname, health)
                if health["status"] in ("disabled",):
                    self._log_call(pname, "get_daily_bars", "skipped",
                                   symbol=stock_code, adj_type=adj_type,
                                   error_message="provider disabled")
                    continue
            except Exception:
                pass

            t0 = time.time()
            try:
                df = provider.get_daily_bars(stock_code, start_date, end_date, adj_type)
                elapsed = int((time.time() - t0) * 1000)

                if df is not None and not df.empty:
                    self._log_call(pname, "get_daily_bars", "success",
                                   symbol=stock_code, adj_type=adj_type,
                                   duration_ms=elapsed, row_count=len(df))
                    return df, pname
                else:
                    self._log_call(pname, "get_daily_bars", "empty",
                                   symbol=stock_code, adj_type=adj_type,
                                   duration_ms=elapsed)
                    continue
            except ProviderError as e:
                elapsed = int((time.time() - t0) * 1000)
                err_type = type(e).__name__
                self._log_call(pname, "get_daily_bars", "failed",
                               symbol=stock_code, adj_type=adj_type,
                               duration_ms=elapsed, error_type=err_type,
                               error_message=str(e))
                last_error = str(e)
                continue
            except Exception as e:
                elapsed = int((time.time() - t0) * 1000)
                self._log_call(pname, "get_daily_bars", "failed",
                               symbol=stock_code, adj_type=adj_type,
                               duration_ms=elapsed, error_type="Exception",
                               error_message=str(e))
                last_error = str(e)
                continue

        # All providers exhausted
        raise ProviderDataEmptyError(
            f"No provider returned data for {stock_code} ({adj_type}). "
            f"Last error: {last_error}" if last_error else ""
        )

    def check_all_providers(self) -> list[dict[str, Any]]:
        results = []
        for pname, provider in self._providers.items():
            try:
                h = provider.health_check()
                self._update_health(pname, h)
                results.append(h)
            except Exception as e:
                r = {"provider_name": pname, "status": "down", "latency_ms": 0,
                     "error_message": str(e)}
                results.append(r)
        return results

    def get_call_stats(self) -> pd.DataFrame:
        try:
            logs = self._log_repo.recent(limit=1000)
            if not logs:
                return pd.DataFrame()
            rows = [{
                "provider_name": l.provider_name,
                "method_name": l.method_name,
                "status": l.status,
                "row_count": l.row_count,
                "duration_ms": l.duration_ms,
                "error_type": l.error_type,
                "created_at": l.created_at,
            } for l in logs]
            return pd.DataFrame(rows)
        except Exception:
            return pd.DataFrame()
