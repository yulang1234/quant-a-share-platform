"""Test core_universe_builder."""
from __future__ import annotations

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    """Patch meta DB to use a temp SQLite file for each test."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestCoreUniverseBuilder:
    """Tests for core_universe_builder module."""

    def test_core_size_validation(self) -> None:
        """core_size must be 50 or 100."""
        from src.backfill.core_universe_builder import build_core_universe

        # Valid sizes should not raise
        for size in (50, 100):
            result = build_core_universe(core_size=size, dry_run=True, limit=0)
            # May return error about no candidates, but should not raise ValueError
            assert isinstance(result, dict)

        # Invalid size should raise
        with pytest.raises(ValueError, match="core_size must be 50, 100, or 500"):
            build_core_universe(core_size=200, dry_run=True)

        with pytest.raises(ValueError, match="core_size must be 50, 100, or 500"):
            build_core_universe(core_size=0, dry_run=True)

    def test_dry_run_does_not_write(self) -> None:
        """dry_run=True should not write any data."""
        from src.backfill.core_universe_builder import build_core_universe
        from src.repositories.universe_repo import UniverseRepository

        result = build_core_universe(core_size=50, dry_run=True, limit=0)
        assert result.get("written") is False

        # No universe should have been created in DB
        urepo = UniverseRepository()
        unis = urepo.list_universes()
        uni_names = [u.universe_name for u in unis]
        assert "core_50" not in uni_names

    def test_confirm_writes_universe(self) -> None:
        """confirm=True should write to the database if candidates exist."""
        from src.backfill.core_universe_builder import build_core_universe
        from src.repositories.security_master_repo import SecurityMasterRepository
        from src.repositories.universe_repo import UniverseRepository

        # Seed some test stocks
        sec_repo = SecurityMasterRepository()
        for i in range(60):
            sym = f"{100000 + i:06d}"
            exch = "SZ" if i < 30 else "SH"
            sec_repo.add_or_update(sym, exch, security_name=f"Test{i}", asset_type="stock", status="active")

        result = build_core_universe(core_size=50, dry_run=False, source="security_master")
        assert result.get("written") is True
        assert result.get("selected_count", 0) >= 0

        # Check universe was created
        urepo = UniverseRepository()
        unis = urepo.list_universes()
        uni_names = [u.universe_name for u in unis]
        assert "core_50" in uni_names

    def test_excludes_st_stocks(self) -> None:
        """ST stocks should be excluded."""
        from src.backfill.core_universe_builder import _is_valid_stock

        # ST in name
        assert not _is_valid_stock("000001", "SZ", "active", "*ST测试")
        assert not _is_valid_stock("000001", "SZ", "active", "ST测试")
        assert not _is_valid_stock("000001", "SZ", "active", "PT测试")

        # Normal stock should pass
        assert _is_valid_stock("000001", "SZ", "active", "平安银行")

        # is_st flag
        assert not _is_valid_stock("000001", "SZ", "active", "测试", is_st=True)

    def test_excludes_delisted(self) -> None:
        """Delisted/inactive stocks should be excluded."""
        from src.backfill.core_universe_builder import _is_valid_stock

        assert not _is_valid_stock("000001", "SZ", "delisted")
        assert not _is_valid_stock("000001", "SZ", "inactive")
        assert not _is_valid_stock("000001", "SZ", "removed")
        assert _is_valid_stock("000001", "SZ", "active")

    def test_excludes_invalid_codes(self) -> None:
        """Invalid/empty codes should be excluded."""
        from src.backfill.core_universe_builder import _is_valid_stock

        assert not _is_valid_stock("", "", "active")
        assert not _is_valid_stock("000000", "SZ", "active")
        assert not _is_valid_stock("abc", "SZ", "active")
        assert not _is_valid_stock("000001", "XX", "active")  # unknown exchange

    def test_limit_effect(self) -> None:
        """--limit should cap the number of stocks selected."""
        from src.backfill.core_universe_builder import build_core_universe
        from src.repositories.security_master_repo import SecurityMasterRepository

        sec_repo = SecurityMasterRepository()
        for i in range(60):
            sym = f"{100000 + i:06d}"
            exch = "SZ" if i < 30 else "SH"
            sec_repo.add_or_update(sym, exch, security_name=f"Test{i}", asset_type="stock", status="active")

        result = build_core_universe(core_size=50, dry_run=True, limit=5, source="security_master")
        assert result.get("selected_count") <= 5

    def test_handles_empty_data(self) -> None:
        """Should handle empty candidate pool gracefully."""
        from src.backfill.core_universe_builder import build_core_universe

        # With no data seeded, source=security_master returns empty
        result = build_core_universe(core_size=50, dry_run=True, source="security_master")
        # Should not crash
        assert isinstance(result, dict)
        # May have error or 0 candidates
        assert result.get("candidates_total", 0) >= 0

    def test_cli_dry_run(self) -> None:
        """CLI dry-run should return 0."""
        import sys
        from src.backfill.core_universe_builder import main

        old_argv = sys.argv
        try:
            sys.argv = ["core_universe_builder", "--core-size", "50", "--dry-run"]
            rc = main()
            assert rc == 0
        finally:
            sys.argv = old_argv
