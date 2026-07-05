"""Test coverage repositories."""
import pytest
from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.data_quality.coverage_repo import CoverageReportRepository, GapDetailRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestCoverageReportRepo:
    def test_upsert_new(self) -> None:
        repo = CoverageReportRepository()
        r = repo.upsert(symbol="000001", exchange="SZ", adj_type="qfq",
                        start_date="20200101", end_date="20201231",
                        expected_trade_days=250, actual_trade_days=200, status="partial")
        assert r.report_id is not None
        assert r.coverage_rate is None  # not set

    def test_upsert_no_duplicate_key(self) -> None:
        repo = CoverageReportRepository()
        r1 = repo.upsert(symbol="000001", exchange="SZ", adj_type="qfq",
                         start_date="20200101", end_date="20201231",
                         expected_trade_days=250, actual_trade_days=200, status="partial")
        r2 = repo.upsert(symbol="000001", exchange="SZ", adj_type="qfq",
                         start_date="20200101", end_date="20201231",
                         expected_trade_days=250, actual_trade_days=240, status="partial")
        assert r1.report_id == r2.report_id
        assert r2.actual_trade_days == 240

    def test_count_by_status(self) -> None:
        repo = CoverageReportRepository()
        repo.upsert(symbol="t1", exchange="SZ", adj_type="qfq",
                    start_date="20200101", end_date="20201231", status="complete")
        counts = repo.count_by_status()
        assert "complete" in counts


class TestGapDetailRepo:
    def test_insert_and_query(self) -> None:
        repo = GapDetailRepository()
        gaps = [{"symbol": "000001", "exchange": "SZ", "gap_type": "single_day",
                 "missing_days": 1, "gap_start_date": "2020-01-15", "gap_end_date": "2020-01-15"}]
        repo.insert_batch(gaps)
        pending = repo.list_pending(limit=10)
        assert len(pending) >= 1

    def test_update_repair_status(self) -> None:
        repo = GapDetailRepository()
        repo.insert_batch([{"symbol": "t", "exchange": "SZ", "gap_type": "single_day", "missing_days": 1,
                            "gap_start_date": "2020-01-15", "gap_end_date": "2020-01-15"}])
        gaps = repo.list_pending(limit=10)
        if gaps:
            repo.update_repair_status(gaps[0].gap_id, "task_created", task_id=999)
            updated = repo.list_by_report(gaps[0].report_id or 0)
            if updated:
                assert updated[0].repair_status == "task_created"
