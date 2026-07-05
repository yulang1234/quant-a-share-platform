"""Provider repositories — config, health, call_log."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from src.db.schema_meta import DataProviderCallLog, DataProviderConfig, DataProviderHealth
from src.repositories.meta_db import get_session


class ProviderConfigRepository:
    def __init__(self, session: Session | None = None):
        self._session = session or get_session()

    def list_all(self) -> list[DataProviderConfig]:
        return self._session.query(DataProviderConfig).order_by(DataProviderConfig.priority).all()

    def set_enabled(self, name: str, enabled: bool) -> int:
        rows = self._session.query(DataProviderConfig).filter_by(provider_name=name).update({"enabled": enabled})
        self._session.commit()
        return rows


class ProviderHealthRepository:
    def __init__(self, session: Session | None = None):
        self._session = session or get_session()

    def upsert(self, provider_name: str, status: str, latency_ms: int = 0,
               error_type: str = "", error_message: str = "") -> DataProviderHealth:
        existing = self._session.query(DataProviderHealth).filter_by(provider_name=provider_name).first()
        if existing:
            existing.health_status = status
            existing.last_check_at = datetime.now()
            existing.latency_ms = latency_ms
            existing.last_error_type = error_type or None
            existing.last_error_message = error_message or None
            self._session.commit()
            return existing
        h = DataProviderHealth(
            provider_name=provider_name, health_status=status,
            last_check_at=datetime.now(), latency_ms=latency_ms,
            last_error_type=error_type or None, last_error_message=error_message or None,
        )
        self._session.add(h)
        self._session.commit()
        return h

    def list_all(self) -> list[DataProviderHealth]:
        return self._session.query(DataProviderHealth).all()


class ProviderCallLogRepository:
    def __init__(self, session: Session | None = None):
        self._session = session or get_session()

    def log_call(self, provider_name: str, method_name: str, status: str = "success",
                 symbol: str = "", exchange: str = "", row_count: int = 0,
                 duration_ms: int = 0, error_type: str = "", error_message: str = "",
                 start_date=None, end_date=None, adj_type: str = "") -> DataProviderCallLog:
        entry = DataProviderCallLog(
            provider_name=provider_name, method_name=method_name, status=status,
            symbol=str(symbol).zfill(6) if symbol else None,
            exchange=exchange.upper() if exchange else None,
            row_count=row_count, duration_ms=duration_ms,
            error_type=error_type or None, error_message=error_message or None,
            start_date=start_date, end_date=end_date, adj_type=adj_type,
        )
        self._session.add(entry)
        self._session.commit()
        return entry

    def recent(self, limit: int = 50) -> list[DataProviderCallLog]:
        return self._session.query(DataProviderCallLog).order_by(
            DataProviderCallLog.created_at.desc(),
        ).limit(limit).all()

    def count_today(self, provider_name: str) -> int:
        today = datetime.now().date()
        return self._session.query(DataProviderCallLog).filter(
            DataProviderCallLog.provider_name == provider_name,
            DataProviderCallLog.created_at >= today,
        ).count()
