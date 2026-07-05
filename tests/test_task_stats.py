"""Tests for task statistics helpers."""

import pytest

from src.data_tasks.task_repo import DataLoadTaskRepository
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


class TestTaskStats:
    def test_count_by_status_empty(self) -> None:
        assert DataLoadTaskRepository().count_by_status() == {}

    def test_top_errors(self) -> None:
        repo = DataLoadTaskRepository()
        task = repo.create(
            symbol="000001",
            exchange="SZ",
            data_type="daily_bar",
            adj_type="qfq",
            start_date="20260101",
            end_date="20261231",
        )
        repo.update_status(task.task_id, "failed", error_message="network down")
        errors = repo.top_errors()
        assert errors[0] == ("network down", 1)
