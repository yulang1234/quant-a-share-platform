"""Test V1.4.7 batch schema and migrations."""
from __future__ import annotations

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestBackfillBatchSchema:
    def test_new_tables_created(self) -> None:
        """backfill_batch and backfill_batch_snapshot tables should exist."""
        from src.db.meta_engine import get_meta_engine
        from sqlalchemy import inspect
        engine = get_meta_engine()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "backfill_batch" in tables
        assert "backfill_batch_snapshot" in tables

    def test_data_load_task_has_batch_id(self) -> None:
        """data_load_task should have batch_id column."""
        from src.db.meta_engine import get_meta_engine
        from sqlalchemy import inspect
        engine = get_meta_engine()
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("data_load_task")}
        assert "batch_id" in cols

    def test_migration_idempotent(self) -> None:
        """Running init_meta_db twice should not error."""
        # Already run once in fixture, run again
        init_meta_db()
        # Should not raise

    def test_old_tasks_without_batch_id(self) -> None:
        """Old tasks without batch_id should work fine."""
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = DataLoadTaskRepository()
        repo.create(symbol="000001", exchange="SZ", data_type="daily_bar",
                    adj_type="qfq", start_date="20240101", end_date="20240131",
                    status="pending")
        tasks = repo.list_pending(limit=5)
        assert len(tasks) >= 1
        # batch_id should be None for old-style tasks
        assert tasks[0].batch_id is None

    def test_batch_repo_create(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        b = repo.create_batch(
            batch_id="bf_test_001",
            batch_name="Test Batch",
            universe_name="core_500",
            adj_type="qfq",
            status="planned",
        )
        assert b.batch_id == "bf_test_001"
        assert b.status == "planned"

    def test_batch_snapshot_create(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_test_002", batch_name="Test", universe_name="core_500")
        s = repo.create_snapshot(
            batch_id="bf_test_002",
            snapshot_type="before",
            avg_coverage_rate=0.85,
            is_real_calendar=True,
        )
        assert s.snapshot_type == "before"
        assert s.avg_coverage_rate == 0.85
