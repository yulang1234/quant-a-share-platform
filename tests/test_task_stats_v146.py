"""Test V1.4.6 task_stats enhanced."""
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


class TestTaskStatsV146:
    def test_empty_tasks_not_error(self) -> None:
        """Should not crash with no tasks."""
        from src.data_tasks.task_stats import main
        rc = main()
        assert rc == 0

    def test_error_classification(self) -> None:
        from src.data_tasks.task_stats import _classify_error

        assert _classify_error("ProviderDataEmptyError") == "ProviderDataEmptyError"
        assert _classify_error("ProviderUnavailableError") == "ProviderError"
        assert _classify_error("SaveError") == "SaveError"
        assert _classify_error("ValidationError") == "ValidationError"
        assert _classify_error("NetworkError") == "NetworkError"
        assert _classify_error("RateLimitError") == "RateLimitError"
        assert _classify_error("CalendarMissing") == "CalendarMissing"
        assert _classify_error(None) == "UnknownError"
        assert _classify_error("SomeWeirdThing") == "UnknownError"

    def test_with_tasks(self) -> None:
        """Should handle tasks with various statuses."""
        from src.data_tasks.task_repo import DataLoadTaskRepository
        repo = DataLoadTaskRepository()
        repo.create(symbol="000001", exchange="SZ", data_type="daily_bar",
                    adj_type="qfq", start_date="20240101", end_date="20240131",
                    status="success")
        repo.create(symbol="000002", exchange="SZ", data_type="daily_bar",
                    adj_type="qfq", start_date="20240101", end_date="20240131",
                    status="failed", error_type="ProviderUnavailableError",
                    error_message="test error")

        from src.data_tasks.task_stats import main
        rc = main()
        assert rc == 0
