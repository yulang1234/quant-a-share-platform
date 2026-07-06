"""V1.4.7 Batch repository — CRUD for backfill_batch and backfill_batch_snapshot."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from src.db.schema_meta import BackfillBatch, BackfillBatchSnapshot
from src.repositories.meta_db import get_session


class BatchRepository:
    """CRUD for backfill_batch."""

    def __init__(self, session: Session | None = None):
        self._s = session or get_session()

    def create_batch(self, batch_id: str, **kwargs) -> BackfillBatch:
        b = BackfillBatch(batch_id=batch_id, **kwargs)
        self._s.add(b)
        self._s.commit()
        return b

    def get_batch(self, batch_id: str) -> BackfillBatch | None:
        return self._s.query(BackfillBatch).filter_by(batch_id=batch_id).first()

    def update_batch_status(self, batch_id: str, status: str, **kwargs) -> None:
        b = self.get_batch(batch_id)
        if b:
            b.status = status
            for k, v in kwargs.items():
                if hasattr(b, k) and v is not None:
                    setattr(b, k, v)
            self._s.commit()

    def update_batch_counts(self, batch_id: str, **counts) -> None:
        """Update success/failed/empty/skipped counts."""
        b = self.get_batch(batch_id)
        if b:
            for k, v in counts.items():
                if hasattr(b, k) and v is not None:
                    current = getattr(b, k, 0) or 0
                    setattr(b, k, current + v)
            b.executed_task_count = (
                (b.success_count or 0) + (b.failed_count or 0) +
                (b.empty_count or 0) + (b.skipped_count or 0)
            )
            self._s.commit()

    def list_batches(self, limit: int = 20, universe_name: str | None = None) -> list[BackfillBatch]:
        q = self._s.query(BackfillBatch).order_by(BackfillBatch.created_at.desc())
        if universe_name:
            q = q.filter_by(universe_name=universe_name)
        return q.limit(limit).all()

    def create_snapshot(self, **kwargs) -> BackfillBatchSnapshot:
        s = BackfillBatchSnapshot(**kwargs)
        self._s.add(s)
        self._s.commit()
        return s

    def get_batch_snapshots(self, batch_id: str) -> list[BackfillBatchSnapshot]:
        return self._s.query(BackfillBatchSnapshot).filter_by(
            batch_id=batch_id,
        ).order_by(BackfillBatchSnapshot.snapshot_type, BackfillBatchSnapshot.created_at).all()

    def get_latest_snapshot(self, batch_id: str, snapshot_type: str) -> BackfillBatchSnapshot | None:
        return self._s.query(BackfillBatchSnapshot).filter_by(
            batch_id=batch_id, snapshot_type=snapshot_type,
        ).order_by(BackfillBatchSnapshot.created_at.desc()).first()
