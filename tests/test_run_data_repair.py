"""Tests for src/data_repair/run_data_repair.py"""

from __future__ import annotations

from src.data_repair.run_data_repair import main


class TestRunDataRepairCLI:
    def test_plan_action(self) -> None:
        rc = main(["--pool", "core_500", "--limit", "1", "--action", "plan", "--dry-run"])
        assert rc == 0

    def test_deduplicate_action(self) -> None:
        rc = main(["--pool", "core_500", "--limit", "1", "--action", "deduplicate", "--adj", "all", "--dry-run"])
        assert rc == 0

    def test_refetch_dry_run(self) -> None:
        rc = main([
            "--pool", "core_500", "--stock-code", "000001",
            "--adj", "raw", "--action", "refetch",
            "--start-date", "20260701", "--end-date", "20260703",
            "--dry-run",
        ])
        assert rc == 0

    def test_refetch_missing_args(self) -> None:
        rc = main(["--action", "refetch", "--dry-run"])
        assert rc == 1  # should error gracefully

    def test_rebuild_parquet_dry_run(self) -> None:
        rc = main([
            "--pool", "core_500", "--stock-code", "000001",
            "--adj", "all", "--action", "rebuild-parquet", "--dry-run",
        ])
        assert rc == 0

    def test_auto_action(self) -> None:
        rc = main(["--pool", "core_500", "--limit", "1", "--action", "auto", "--dry-run"])
        assert rc == 0

    def test_confirm_without_no_dry_run_ok(self) -> None:
        """--confirm alone is fine (dry-run still True by default)."""
        rc = main(["--action", "plan", "--confirm"])
        assert rc == 0
