"""V1.4.1 Provider health view helpers — safe read-only queries for Streamlit."""

from __future__ import annotations

import pandas as pd

from config.settings import get_meta_db_url


def get_meta_db_status() -> dict:
    """Return meta DB status info (no credentials exposed)."""
    try:
        url = get_meta_db_url()
        if "postgresql" in url:
            db_type = "PostgreSQL"
            status = "已配置 PostgreSQL"
        elif "sqlite" in url:
            db_type = "SQLite"
            status = "SQLite fallback"
        else:
            db_type = "Unknown"
            status = "未知"

        # Test connectivity
        try:
            from src.db.meta_engine import get_meta_engine
            engine = get_meta_engine()
            with engine.connect() as conn:
                conn.execute(conn.text("SELECT 1"))
            connected = True
        except Exception:
            connected = False

        return {
            "db_type": db_type,
            "status": status,
            "connected": connected,
            "databases_url_configured": "postgresql" in url,
        }
    except Exception:
        return {"db_type": "Unknown", "status": "查询失败", "connected": False, "databases_url_configured": False}


def load_provider_health() -> pd.DataFrame:
    try:
        from src.repositories.provider_repo import ProviderHealthRepository
        repo = ProviderHealthRepository()
        results = repo.list_all()
        if not results:
            return pd.DataFrame()
        return pd.DataFrame([{
            "provider_name": r.provider_name,
            "health_status": r.health_status,
            "last_check_at": r.last_check_at,
            "latency_ms": r.latency_ms,
            "success_rate_1d": r.success_rate_1d,
            "success_rate_7d": r.success_rate_7d,
            "last_error_type": r.last_error_type,
            "last_error_message": (r.last_error_message or "")[:200],
        } for r in results])
    except Exception:
        return pd.DataFrame()


def load_provider_config() -> pd.DataFrame:
    try:
        from src.repositories.provider_repo import ProviderConfigRepository
        repo = ProviderConfigRepository()
        results = repo.list_all()
        if not results:
            return pd.DataFrame()
        return pd.DataFrame([{
            "provider_name": r.provider_name,
            "provider_type": r.provider_type,
            "priority": r.priority,
            "enabled": r.enabled,
            "supports_daily": r.supports_daily,
            "supports_minute": r.supports_minute,
            "supports_realtime": r.supports_realtime,
            "supports_calendar": r.supports_calendar,
            "supports_stock_basic": r.supports_stock_basic,
            "rate_limit_per_minute": r.rate_limit_per_minute,
            "timeout_seconds": r.timeout_seconds,
        } for r in results])
    except Exception:
        return pd.DataFrame()


def load_provider_stats() -> pd.DataFrame:
    try:
        from src.data_sources.market_data_service import MarketDataService
        svc = MarketDataService()
        df = svc.get_call_stats()
        if df.empty:
            return df
        agg = df.groupby("provider_name").agg(
            total_calls=("status", "count"),
            success_calls=("status", lambda x: (x == "success").sum()),
            failed_calls=("status", lambda x: (x == "failed").sum()),
            empty_calls=("status", lambda x: (x == "empty").sum()),
            skipped_calls=("status", lambda x: (x == "skipped").sum()),
            avg_duration_ms=("duration_ms", "mean"),
        ).reset_index()
        return agg
    except Exception:
        return pd.DataFrame()


def load_recent_errors(limit: int = 10) -> pd.DataFrame:
    try:
        from src.repositories.provider_repo import ProviderCallLogRepository
        repo = ProviderCallLogRepository()
        logs = repo.recent(limit=500)
        failed = [l for l in logs if l.status == "failed"]
        if not failed:
            return pd.DataFrame()
        rows = [{
            "created_at": l.created_at,
            "provider_name": l.provider_name,
            "method_name": l.method_name,
            "symbol": l.symbol,
            "adj_type": l.adj_type,
            "error_type": l.error_type,
            "error_message": (l.error_message or "")[:300],
        } for l in failed[:limit]]
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


STATUS_CN = {
    "healthy": "正常", "degraded": "降级", "down": "不可用", "disabled": "未启用",
}
