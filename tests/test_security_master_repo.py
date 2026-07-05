"""Test SecurityMasterRepository."""
import pytest
from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.repositories.security_master_repo import SecurityMasterRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestSecurityMaster:
    def test_add_and_find(self) -> None:
        repo = SecurityMasterRepository()
        repo.add_or_update("000001", "SZ", security_name="平安银行", asset_type="stock")
        sec = repo.find_by_symbol("000001", "SZ")
        assert sec is not None
        assert sec.security_name == "平安银行"

    def test_update_existing(self) -> None:
        repo = SecurityMasterRepository()
        repo.add_or_update("600519", "SH", security_name="贵州茅台")
        repo.add_or_update("600519", "SH", security_name="贵州茅台", industry="白酒")
        sec = repo.find_by_symbol("600519", "SH")
        assert sec.industry == "白酒"

    def test_count(self) -> None:
        repo = SecurityMasterRepository()
        assert repo.count() >= 0
