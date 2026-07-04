"""Tests for src/data_repair/repair_log.py"""

from __future__ import annotations

import pytest

from src.data_repair.repair_log import (
    get_recent_repair_logs,
    get_repair_summary,
    write_repair_log,
)


class TestRepairLog:
    @pytest.fixture(autouse=True)
    def _setup(self, fresh_db) -> None:  # noqa: F811
        self._db = fresh_db

    def test_write_and_read(self) -> None:
        rid = write_repair_log(
            stock_code="000001", repair_action="deduplicate",
            status="dry_run", dry_run=True,
        )
        assert rid is not None
        assert len(rid) == 36  # UUID

        logs = get_recent_repair_logs(limit=10)
        assert not logs.empty
        assert "000001" in logs["stock_code"].values

    def test_write_auto_uuid(self) -> None:
        rid = write_repair_log(repair_action="plan", status="planned")
        assert rid is not None
        assert len(rid) > 0

    def test_summary_empty_table(self) -> None:
        summary = get_repair_summary()
        assert isinstance(summary, dict)
        assert "total_logs" in summary
        assert "by_status" in summary

    def test_summary_with_data(self) -> None:
        write_repair_log(stock_code="000001", repair_action="deduplicate", status="success")
        write_repair_log(stock_code="000002", repair_action="refetch_range", status="dry_run")
        summary = get_repair_summary()
        assert summary["total_logs"] >= 2

    def test_dry_run_field(self) -> None:
        write_repair_log(repair_action="plan", dry_run=True, confirm=False)
        logs = get_recent_repair_logs(1)
        assert bool(logs.iloc[0]["dry_run"]) is True
        assert bool(logs.iloc[0]["confirm"]) is False
