"""V1.4.2 DataLoadTask and DataLoadTaskLog repositories."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from src.db.schema_meta import DataLoadTask, DataLoadTaskLog
from src.repositories.meta_db import get_session


class DataLoadTaskRepository:
    def __init__(self, session: Session | None = None):
        self._s = session or get_session()

    def create(self, **kwargs) -> DataLoadTask:
        t = DataLoadTask(**kwargs)
        self._s.add(t); self._s.commit(); return t

    def get_by_id(self, task_id: int) -> DataLoadTask | None:
        return self._s.query(DataLoadTask).filter_by(task_id=task_id).first()

    def list_pending(self, limit: int = 10, status: str = "pending",
                     batch_id: str | None = None) -> list[DataLoadTask]:
        q = self._s.query(DataLoadTask).filter(DataLoadTask.status == status)
        if batch_id:
            q = q.filter(DataLoadTask.batch_id == batch_id)
        return q.limit(limit).all()

    def count_by_status(self) -> dict[str, int]:
        rows = self._s.query(DataLoadTask.status, __import__('sqlalchemy').func.count()).group_by(DataLoadTask.status).all()
        return {r[0]: r[1] for r in rows}

    def update_status(self, task_id: int, status: str, **kwargs) -> None:
        t = self.get_by_id(task_id)
        if t:
            t.status = status
            t.attempt_count = kwargs.get("attempt_count", t.attempt_count)
            t.row_count = kwargs.get("row_count", t.row_count)
            t.error_type = kwargs.get("error_type")
            t.error_message = kwargs.get("error_message")
            t.next_retry_at = kwargs.get("next_retry_at", t.next_retry_at)
            t.last_attempt_at = kwargs.get("last_attempt_at", datetime.now())
            self._s.commit()

    def top_errors(self, limit: int = 5) -> list[tuple[str, int]]:
        from sqlalchemy import func
        rows = (
            self._s.query(DataLoadTask.error_message, func.count())
            .filter(DataLoadTask.error_message.isnot(None))
            .group_by(DataLoadTask.error_message)
            .order_by(func.count().desc())
            .limit(limit)
            .all()
        )
        return [(str(r[0])[:200], int(r[1])) for r in rows]

    def upsert_task(self, symbol: str, exchange: str, data_type: str, adj_type: str,
                    start_date, end_date, batch_id: str | None = None, **kwargs) -> DataLoadTask:
        existing = self._s.query(DataLoadTask).filter_by(
            symbol=str(symbol).zfill(6), exchange=exchange.upper(),
            data_type=data_type, adj_type=adj_type,
            start_date=start_date, end_date=end_date,
        ).first()
        if existing:
            if batch_id and not existing.batch_id:
                existing.batch_id = batch_id
                self._s.commit()
            return existing
        return self.create(symbol=symbol, exchange=exchange, data_type=data_type,
                           adj_type=adj_type, start_date=start_date, end_date=end_date,
                           batch_id=batch_id, **kwargs)


class DataLoadTaskLogRepository:
    def __init__(self, session: Session | None = None):
        self._s = session or get_session()

    def log(self, task_id: int, status_before: str, status_after: str,
            provider_used: str = "", row_count: int = 0, duration_ms: int = 0,
            error_type: str = "", error_message: str = "") -> DataLoadTaskLog:
        entry = DataLoadTaskLog(
            task_id=task_id, status_before=status_before, status_after=status_after,
            provider_used=provider_used, row_count=row_count, duration_ms=duration_ms,
            error_type=error_type or None, error_message=(error_message or "")[:1000],
        )
        self._s.add(entry); self._s.commit(); return entry
