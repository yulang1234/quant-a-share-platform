"""Test coverage_report CLI."""
import json
import pytest
from src.data_quality.coverage_report import main


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    from src.db.meta_engine import reset_meta_engine
    from src.db.migrations import init_meta_db
    reset_meta_engine(); init_meta_db()
    # Insert sample data
    from src.data_quality.coverage_repo import CoverageReportRepository
    repo = CoverageReportRepository()
    repo.upsert(symbol="000001", exchange="SZ", adj_type="qfq", start_date="20200101", end_date="20201231",
                expected_trade_days=250, actual_trade_days=200, missing_trade_days=50,
                coverage_rate=0.8, status="partial")
    repo.upsert(symbol="600519", exchange="SH", adj_type="qfq", start_date="20200101", end_date="20201231",
                expected_trade_days=250, actual_trade_days=250, missing_trade_days=0,
                coverage_rate=1.0, status="complete")
    yield
    reset_meta_engine()


class TestCoverageReportCLI:
    def test_basic(self) -> None:
        rc = main(["--limit", "5"])
        assert rc == 0

    def test_status_filter(self) -> None:
        rc = main(["--status", "complete", "--limit", "5"])
        assert rc == 0

    def test_json_output(self) -> None:
        rc = main(["--json", "--limit", "5"])
        assert rc == 0

    def test_top_missing(self) -> None:
        rc = main(["--top-missing", "--limit", "5"])
        assert rc == 0

    def test_limit_zero_rejected(self) -> None:
        rc = main(["--limit", "0"])
        assert rc == 1

    def test_empty_table_no_crash(self, monkeypatch, tmp_path) -> None:
        url2 = f"sqlite:///{tmp_path / 'empty.db'}"
        monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url2)
        from src.db.meta_engine import reset_meta_engine
        from src.db.migrations import init_meta_db
        reset_meta_engine(); init_meta_db()
        rc = main(["--limit", "5"])
        assert rc == 0
