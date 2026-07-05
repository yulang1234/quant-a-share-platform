"""Test gap_report CLI."""
import pytest
from src.data_quality.gap_report import main


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
    ])
    yield
    reset_meta_engine()


class TestGapReportCLI:
    def test_basic(self) -> None:
        rc = main(["--limit", "5"])
        assert rc == 0

    def test_severity_filter(self) -> None:
        rc = main(["--severity", "low", "--limit", "5"])
        assert rc == 0

    def test_json_output(self) -> None:
        rc = main(["--json", "--limit", "5"])
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
