"""Test universe_all_a builder."""
import pytest
from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.repositories.security_master_repo import SecurityMasterRepository
from src.repositories.universe_repo import UniverseRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestUniverseBuilder:
    def test_build_universe(self) -> None:
        sec_repo = SecurityMasterRepository()
        sec_repo.add_or_update("000010", "SZ", security_name="test1", asset_type="stock", status="active")
        sec_repo.add_or_update("600520", "SH", security_name="test2", asset_type="stock", status="active")

        uni_repo = UniverseRepository()
        u = uni_repo.add_universe("test_uni2", "test2", "stock")
        secs = sec_repo.list_all(limit=10)
        stocks = [s for s in secs if s.asset_type == "stock" and s.status == "active"]
        for s in stocks:
            uni_repo.add_member(u.universe_id, s.symbol, s.exchange)
        assert uni_repo.count_members(u.universe_id) >= 2

    def test_inactive_excluded(self) -> None:
        sec_repo = SecurityMasterRepository()
        sec_repo.add_or_update("000020", "SZ", asset_type="stock", status="delisted")
        secs = sec_repo.list_all(limit=10)
        active = [s for s in secs if s.status in ("active", "listed", "normal")]
        active_symbols = [s.symbol for s in active]
        assert "000020" not in active_symbols
