"""Test provider call logging via repository."""
import pytest
from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.repositories.provider_repo import ProviderCallLogRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestCallLog:
    def test_log_success(self) -> None:
        repo = ProviderCallLogRepository()
        entry = repo.log_call("test_prov", "get_daily_bars", "success", symbol="000001", row_count=100, duration_ms=500)
        assert entry.status == "success"
        assert entry.row_count == 100

    def test_log_failed(self) -> None:
        repo = ProviderCallLogRepository()
        entry = repo.log_call("test_prov", "get_daily_bars", "failed", error_type="ProviderTimeoutError", error_message="timeout")
        assert entry.status == "failed"
        assert entry.error_type == "ProviderTimeoutError"

    def test_recent(self) -> None:
        repo = ProviderCallLogRepository()
        repo.log_call("p1", "m1", "success")
        repo.log_call("p2", "m2", "failed")
        recent = repo.recent(limit=5)
        assert len(recent) >= 2
