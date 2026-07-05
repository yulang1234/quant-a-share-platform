"""Test security master sync."""
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


class TestSecurityMasterSync:
    def test_upsert_new(self) -> None:
        repo = SecurityMasterRepository()
        sec = repo.add_or_update("000001", "SZ", security_name="平安银行", asset_type="stock")
        assert sec.security_id is not None

    def test_upsert_no_duplicate(self) -> None:
        repo = SecurityMasterRepository()
        s1 = repo.add_or_update("600519", "SH", security_name="贵州茅台")
        s2 = repo.add_or_update("600519", "SH", security_name="贵州茅台", industry="白酒")
        assert s1.security_id == s2.security_id
        assert s2.industry == "白酒"

    def test_no_overwrite_non_null(self) -> None:
        repo = SecurityMasterRepository()
        repo.add_or_update("000002", "SZ", security_name="万科A", industry="房地产")
        # Don't overwrite industry with None
        sec2 = repo.add_or_update("000002", "SZ")  # no kwargs
        assert sec2.industry == "房地产"

    def test_symbol_standardised(self) -> None:
        repo = SecurityMasterRepository()
        sec = repo.add_or_update(1, "sz", security_name="test")  # int code, lowercase exchange
        assert sec.symbol == "000001"
        assert sec.exchange == "SZ"
