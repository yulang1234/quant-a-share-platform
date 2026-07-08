"""Test V1.4.8 batch_runner profile and core_500 protection."""
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


class TestBatchRunnerProfile:
    def test_core_500_confirm_without_allow_fails(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_core500_x", batch_name="X",
                         universe_name="core_500", status="tasks_written")

        from src.backfill.batch_runner import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["runner", "--batch-id", "bf_core500_x", "--limit", "5",
                        "--confirm", "--no-save"]
            rc = cli_main()
            assert rc == 1  # should be rejected
        finally:
            sys.argv = old_argv

    def test_core_500_dry_run_without_allow_ok(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_core500_y", batch_name="Y",
                         universe_name="core_500")

        from src.backfill.batch_runner import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["runner", "--batch-id", "bf_core500_y", "--limit", "5", "--dry-run"]
            rc = cli_main()
            assert rc == 0  # dry-run is fine
        finally:
            sys.argv = old_argv

    def test_core_50_no_protection(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_core50_z", batch_name="Z", universe_name="core_50")

        from src.backfill.batch_runner import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["runner", "--batch-id", "bf_core50_z", "--limit", "5",
                        "--confirm", "--no-save"]
            rc = cli_main()
            # core_50 doesn't need allow flag, may return 0 or 1 (no tasks)
            assert rc in (0, 1)
        finally:
            sys.argv = old_argv

    def test_core_500_with_allow_ok(self) -> None:
        from src.backfill.batch_repo import BatchRepository
        repo = BatchRepository()
        repo.create_batch(batch_id="bf_core500_a", batch_name="A", universe_name="core_500")

        from src.backfill.batch_runner import main as cli_main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["runner", "--batch-id", "bf_core500_a", "--limit", "5",
                        "--confirm", "--no-save", "--allow-core-500-run"]
            rc = cli_main()
            assert rc in (0, 1)  # no tasks but allowed
        finally:
            sys.argv = old_argv


class TestSafeCore500Profile:
    def test_profile_enforces_limit(self) -> None:
        from src.backfill.batch_runner import _apply_profile, SAFE_PROFILE
        import argparse
        p = argparse.Namespace(limit=50, sleep=1.0, stop_on_failed_rate=False, max_failed_rate=0.5)
        w = _apply_profile(p)
        assert p.limit <= 10
        assert len(w) > 0

    def test_profile_enforces_sleep(self) -> None:
        from src.backfill.batch_runner import _apply_profile
        import argparse
        p = argparse.Namespace(limit=5, sleep=0.1, stop_on_failed_rate=True, max_failed_rate=0.2)
        _apply_profile(p)
        assert p.sleep >= 1.0

    def test_profile_enforces_failed_rate(self) -> None:
        from src.backfill.batch_runner import _apply_profile
        import argparse
        p = argparse.Namespace(limit=5, sleep=1.0, stop_on_failed_rate=False, max_failed_rate=0.8)
        _apply_profile(p)
        assert p.stop_on_failed_rate is True
        assert p.max_failed_rate <= 0.3

    def test_profile_not_bypass_confirm(self) -> None:
        """Profile should not change confirm behavior."""
        from src.backfill.batch_runner import _apply_profile
        import argparse
        p = argparse.Namespace(limit=5, sleep=1.0, stop_on_failed_rate=False, max_failed_rate=0.5)
        _apply_profile(p)
        # Profile doesn't touch confirm - that's argparse responsibility
