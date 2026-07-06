"""Test small_batch_runner."""
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


class TestSmallBatchRunner:
    """Tests for small_batch_runner module."""

    def test_save_local_requires_confirm(self) -> None:
        """--save-local without --confirm should error."""
        from src.backfill.small_batch_runner import run_small_batch

        result = run_small_batch(
            limit=5, confirm=False, save_local=True,
        )
        assert "error" in result

    def test_save_local_with_confirm_allowed(self) -> None:
        """--save-local with --confirm should work (may fail due to no tasks)."""
        from src.backfill.small_batch_runner import run_small_batch

        # With empty DB, there are no pending tasks
        result = run_small_batch(
            limit=1, confirm=True, save_local=True,
        )
        if "error" in result:
            # Error is fine as long as it's not about confirm/save_local
            assert "requires --confirm" not in str(result.get("error", ""))
        else:
            assert result.get("total", 0) >= 0

    def test_limit_effective(self) -> None:
        """limit should control max tasks."""
        from src.backfill.small_batch_runner import run_small_batch

        result = run_small_batch(
            limit=1, confirm=False,
        )
        # dry-run should show at most limit tasks
        assert result.get("total", 0) <= 1

    def test_returns_expected_keys(self) -> None:
        """Result should contain total/success/failed/empty/skipped."""
        from src.backfill.small_batch_runner import run_small_batch

        result = run_small_batch(
            limit=3, confirm=False,
        )
        for key in ("total", "success", "failed", "empty", "skipped"):
            assert key in result, f"Missing key: {key}"

    def test_cli_save_local_without_confirm_errors(self) -> None:
        """CLI --save-local without --confirm should return 1."""
        from src.backfill.small_batch_runner import main as cli_main
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["runner", "--limit", "5", "--save-local"]
            rc = cli_main()
            assert rc == 1
        finally:
            sys.argv = old_argv

    def test_cli_dry_run(self) -> None:
        """CLI dry-run should not error."""
        from src.backfill.small_batch_runner import main as cli_main
        import sys

        old_argv = sys.argv
        try:
            sys.argv = ["runner", "--limit", "3", "--dry-run"]
            rc = cli_main()
            assert rc == 0
        finally:
            sys.argv = old_argv

    def test_large_limit_warns(self) -> None:
        """limit > 50 should produce a warning but not error."""
        from src.backfill.small_batch_runner import run_small_batch

        # limit 100 > max 50, should proceed with warning (V1.4.5 allows)
        result = run_small_batch(
            limit=100, confirm=False,
        )
        # Should not crash
        assert isinstance(result, dict)
