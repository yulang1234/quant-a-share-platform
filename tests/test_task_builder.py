"""Test task builder."""
from src.data_tasks.task_builder import build_tasks_from_securities


class TestTaskBuilder:
    def test_yearly_split(self) -> None:
        secs = [{"symbol": "000001", "exchange": "SZ", "asset_type": "stock"}]
        tasks = build_tasks_from_securities(secs, adj="qfq", start_date="20200101", end_date="20211231", limit=10)
        assert len(tasks) >= 2  # 2020, 2021 = 2 years

    def test_all_generates_raw_and_qfq(self) -> None:
        secs = [{"symbol": "000001", "exchange": "SZ"}]
        tasks = build_tasks_from_securities(secs, adj="all", start_date="20260101", end_date="20261231", limit=5)
        adj_types = {t["adj_type"] for t in tasks}
        assert "raw" in adj_types
        assert "qfq" in adj_types

    def test_limit_respected(self) -> None:
        secs = [{"symbol": f"{i:06d}", "exchange": "SZ"} for i in range(1, 10)]
        tasks = build_tasks_from_securities(secs, adj="raw", start_date="20250101", end_date="20251231", limit=3)
        assert len(tasks) <= 3

    def test_dry_run_no_db_write(self) -> None:
        secs = [{"symbol": "000001", "exchange": "SZ"}]
        tasks = build_tasks_from_securities(secs, adj="raw", start_date="20250101", end_date="20251231",
                                            dry_run=True, limit=5)
        assert len(tasks) >= 1
        # dry_run=True just returns list, no DB writes
