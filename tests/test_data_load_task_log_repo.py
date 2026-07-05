"""Tests for DataLoadTaskLogRepository."""

import pytest

from src.data_tasks.task_repo import DataLoadTaskLogRepository, DataLoadTaskRepository
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


class TestDataLoadTaskLogRepo:
    def test_log_truncates_error_message(self) -> None:
        task_repo = DataLoadTaskRepository()
        task = task_repo.create(
            symbol="000001",
            exchange="SZ",
            data_type="daily_bar",
            adj_type="qfq",
            start_date="20260101",
            end_date="20261231",
        )
        log_repo = DataLoadTaskLogRepository()
        entry = log_repo.log(
            task.task_id,
            "pending",
            "failed",
            error_type="ProviderError",
            error_message="x" * 2000,
        )
        assert entry.status_after == "failed"
        assert entry.error_type == "ProviderError"
        assert len(entry.error_message) == 1000
