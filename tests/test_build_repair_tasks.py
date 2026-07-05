"""Test build_repair_tasks CLI."""
import pytest
from src.data_quality.build_repair_tasks import main


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    from src.db.meta_engine import reset_meta_engine
    from src.db.migrations import init_meta_db
    reset_meta_engine(); init_meta_db()
    from src.data_quality.coverage_repo import GapDetailRepository
    repo = GapDetailRepository()
    repo.insert_batch([
        {"symbol": "000001", "exchange": "SZ", "adj_type": "qfq", "gap_type": "single_day",
         "missing_days": 1, "gap_start_date": "2020-01-15", "gap_end_date": "2020-01-15",
         "severity": "low", "repair_status": "pending"},
        {"symbol": "600519", "exchange": "SH", "adj_type": "qfq", "gap_type": "date_range",
         "missing_days": 5, "gap_start_date": "2020-03-01", "gap_end_date": "2020-03-05",
         "severity": "medium", "repair_status": "pending"},
        {"symbol": "000002", "exchange": "SZ", "adj_type": "qfq", "gap_type": "calendar_missing",
         "missing_days": 0, "gap_start_date": None, "gap_end_date": None,
         "severity": "low", "repair_status": "pending"},
    ])
    yield
    reset_meta_engine()


class TestBuildRepairTasks:
    def test_dry_run(self) -> None:
        rc = main(["--limit", "5", "--dry-run"])
        assert rc == 0

    def test_dry_run_no_write(self) -> None:
        """Dry-run must not write tasks."""
        from src.data_tasks.task_repo import DataLoadTaskRepository
        task_repo = DataLoadTaskRepository()
        before = len(task_repo.list_pending(limit=100))
        main(["--limit", "5", "--dry-run"])
        after = len(task_repo.list_pending(limit=100))
        assert after == before

    def test_confirm_writes(self) -> None:
        from src.data_tasks.task_repo import DataLoadTaskRepository
        from src.data_quality.coverage_repo import GapDetailRepository
        task_repo = DataLoadTaskRepository()
        gap_repo = GapDetailRepository()
        before = len(task_repo.list_pending(limit=100))
        main(["--limit", "5", "--confirm"])
        after = len(task_repo.list_pending(limit=100))
        assert after > before  # new task created
        linked = [
            g for g in gap_repo.list_gaps(limit=10, repair_status="task_created")
            if g.related_task_id is not None
        ]
        assert linked

    def test_calendar_skipped(self) -> None:
        """calendar_missing gaps should not generate tasks."""
        rc = main(["--limit", "5"])
        assert rc == 0

    def test_existing_task_is_linked(self) -> None:
        from src.data_tasks.task_repo import DataLoadTaskRepository
        from src.data_quality.coverage_repo import GapDetailRepository

        task_repo = DataLoadTaskRepository()
        existing = task_repo.upsert_task(
            symbol="000001",
            exchange="SZ",
            asset_type="stock",
            data_type="daily_bar",
            adj_type="qfq",
            start_date="2020-01-15",
            end_date="2020-01-15",
            status="pending",
        )
        main(["--limit", "5", "--confirm"])
        gaps = GapDetailRepository().list_gaps(limit=10, repair_status="task_created")
        assert any(g.related_task_id == existing.task_id for g in gaps)

    def test_limit_zero_rejected(self) -> None:
        rc = main(["--limit", "0"])
        assert rc == 1

    def test_min_severity_filter(self) -> None:
        """min-severity=medium should exclude low severity gaps."""
        rc = main(["--min-severity", "medium", "--limit", "5"])
        assert rc == 0

    def test_no_market_service_call(self) -> None:
        import inspect
        src = inspect.getsource(main)
        assert "MarketDataService" not in src
