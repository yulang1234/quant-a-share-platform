"""Tests for V1.4.2 task runner safety boundaries."""

import pandas as pd
import pytest

from src.data_tasks.task_repo import DataLoadTaskRepository
from src.data_tasks.task_runner import run_tasks
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


class _SuccessService:
    def get_daily_bars(self, *_args, **_kwargs):
        return pd.DataFrame({"close": [1.0, 2.0]}), "mock_provider"


class _FailService:
    def get_daily_bars(self, *_args, **_kwargs):
        raise RuntimeError("provider failed")


class TestTaskRunner:
    def _seed(self) -> None:
        repo = DataLoadTaskRepository()
        repo.create(
            symbol="000001",
            exchange="SZ",
            data_type="daily_bar",
            adj_type="qfq",
            start_date="20260101",
            end_date="20261231",
        )

    def test_dry_run_does_not_execute_provider(self, monkeypatch) -> None:
        self._seed()

        def _boom():
            raise AssertionError("MarketDataService should not be constructed in dry-run")

        monkeypatch.setattr("src.data_sources.market_data_service.MarketDataService", _boom)
        result = run_tasks(limit=1, confirm=False, sleep_seconds=0)
        assert result["skipped"] == 1

    def test_confirm_success_updates_task_without_saving_bars(self, monkeypatch) -> None:
        self._seed()
        monkeypatch.setattr(
            "src.data_sources.market_data_service.MarketDataService",
            lambda: _SuccessService(),
        )
        result = run_tasks(limit=1, confirm=True, no_save=True, sleep_seconds=0)
        assert result["success"] == 1
        task = DataLoadTaskRepository().list_pending(limit=10)
        assert task == []

    def test_single_failure_does_not_raise(self, monkeypatch) -> None:
        self._seed()
        monkeypatch.setattr(
            "src.data_sources.market_data_service.MarketDataService",
            lambda: _FailService(),
        )
        result = run_tasks(limit=1, confirm=True, no_save=True, sleep_seconds=0)
        assert result["failed"] == 1
