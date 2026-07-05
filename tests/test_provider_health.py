"""Test provider health repository."""
import pytest
from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.repositories.provider_repo import ProviderHealthRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestHealth:
    def test_upsert_new(self) -> None:
        repo = ProviderHealthRepository()
        h = repo.upsert("test_p", "healthy", latency_ms=100)
        assert h.health_status == "healthy"

    def test_upsert_update(self) -> None:
        repo = ProviderHealthRepository()
        repo.upsert("test_p2", "healthy", latency_ms=100)
        h = repo.upsert("test_p2", "down", error_message="network error")
        assert h.health_status == "down"
        assert h.last_error_message == "network error"

    def test_list_all(self) -> None:
        repo = ProviderHealthRepository()
        repo.upsert("p1", "healthy")
        repo.upsert("p2", "disabled")
        all_h = repo.list_all()
        assert len(all_h) >= 2
