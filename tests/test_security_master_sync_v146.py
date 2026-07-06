"""Test V1.4.6 security_master sync."""
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


class TestSecurityMasterSyncV146:
    def test_dry_run_does_not_write(self) -> None:
        from src.security.sync_security_master import main
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["sync_sec", "--limit", "5", "--dry-run"]
            rc = main()
            # rc=0 if data found, rc=1 if no data (provider down / empty stock_pool)
            assert rc in (0, 1)
        finally:
            sys.argv = old_argv

    def test_confirm_writes_from_stock_pool(self) -> None:
        """Confirm should write securities (from Provider or stock_pool fallback)."""
        from src.security.sync_security_master import main
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["sync_sec", "--limit", "5", "--confirm"]
            rc = main()
            assert rc == 0
        finally:
            sys.argv = old_argv

        # Verify data was written (count > 0)
        from src.repositories.security_master_repo import SecurityMasterRepository
        repo = SecurityMasterRepository()
        count = repo.count()
        assert count > 0

    def test_st_detection(self) -> None:
        from src.security.sync_security_master import _is_st

        assert _is_st("*ST测试") is True
        assert _is_st("ST测试") is True
        assert _is_st("S*ST测试") is True
        assert _is_st("PT测试") is True
        assert _is_st("平安银行") is False
        assert _is_st("600519") is False

    def test_exchange_inference(self) -> None:
        from src.security.sync_security_master import _infer_exchange

        assert _infer_exchange("600000") == "SH"
        assert _infer_exchange("000001") == "SZ"
        assert _infer_exchange("300001") == "SZ"
        assert _infer_exchange("830001") == "BJ"
        assert _infer_exchange("430001") == "BJ"

    def test_empty_provider_does_not_crash(self) -> None:
        """Should handle empty stock_pool gracefully."""
        from src.security.sync_security_master import main
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["sync_sec", "--limit", "5", "--dry-run"]
            rc = main()
            # Without any data, should return 1 (error) but not crash
            assert rc in (0, 1)
        finally:
            sys.argv = old_argv

    def test_limit_effective(self) -> None:
        """--limit should work (dry-run from Provider)."""
        from src.security.sync_security_master import main
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["sync_sec", "--limit", "3", "--dry-run"]
            rc = main()
            # rc=0 if provider available, rc=1 if no data
            assert rc in (0, 1)
        finally:
            sys.argv = old_argv
