"""Test coverage_compare."""
import pytest
from src.data_quality.coverage_compare import compare_coverage


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    from src.db.meta_engine import reset_meta_engine
    from src.db.migrations import init_meta_db
    reset_meta_engine(); init_meta_db()
    from src.data_quality.coverage_repo import CoverageReportRepository
    repo = CoverageReportRepository()
    repo.upsert(symbol="000001", exchange="SZ", adj_type="qfq", start_date="20200101", end_date="20201231",
                expected_trade_days=250, actual_trade_days=200, missing_trade_days=50,
                coverage_rate=0.8, status="partial")
    yield
    reset_meta_engine()


class TestCoverageCompare:
    def test_before_data_exists(self) -> None:
        result = compare_coverage(["000001"], "qfq", "20200101", "20201231")
        assert result["before"]["count"] >= 1
        assert result["before"]["avg_rate"] is not None

    def test_no_data_no_crash(self) -> None:
        result = compare_coverage([], "raw", "20200101", "20201231")
        assert result["before"]["count"] == 0

    def test_before_has_correct_keys(self) -> None:
        result = compare_coverage(["000001"], "qfq", "20200101", "20201231")
        assert "avg_rate" in result["before"]
        assert "total_missing" in result["before"]

    def test_improved_true_with_after_reports(self) -> None:
        from src.data_quality.coverage_repo import CoverageReportRepository
        repo = CoverageReportRepository()
        after = [
            repo.upsert(symbol="000002", exchange="SZ", adj_type="qfq",
                        start_date="20200101", end_date="20201231",
                        expected_trade_days=250, actual_trade_days=240,
                        missing_trade_days=10, coverage_rate=0.96,
                        status="partial")
        ]
        result = compare_coverage(["000001"], "qfq", "20200101", "20201231", after_reports=after)
        assert result["after"]["avg_rate"] == 0.96
        assert result["improved"] is True
