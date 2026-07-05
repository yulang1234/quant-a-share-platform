"""Test sample_backfill_validate CLI."""
import pytest
from src.data_quality.sample_backfill_validate import main


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
    ])
    yield
    reset_meta_engine()


class TestSampleBackfill:
    def test_default_dry_run(self) -> None:
        rc = main(["--limit", "2"])
        assert rc == 0

    def test_save_local_requires_confirm(self) -> None:
        rc = main(["--save-local", "--limit", "2"])
        assert rc == 1

    def test_limit_zero_rejected(self) -> None:
        rc = main(["--limit", "0"])
        assert rc == 1

    def test_source_gaps(self) -> None:
        rc = main(["--source", "gaps", "--limit", "2"])
        assert rc == 0

    def test_source_tasks(self) -> None:
        rc = main(["--source", "tasks", "--limit", "2"])
        assert rc == 0

    def test_source_universe(self) -> None:
        rc = main(["--source", "universe", "--limit", "2"])
        assert rc == 0

    def test_no_market_service_in_dry_run(self) -> None:
        """dry-run must not call MarketDataService."""
        from unittest.mock import patch

        with patch("src.data_sources.market_data_service.MarketDataService") as mocked:
            rc = main(["--source", "gaps", "--limit", "2", "--dry-run"])
        assert rc == 0
        mocked.assert_not_called()

    def test_confirm_no_save_can_call_market_service(self) -> None:
        from unittest.mock import patch

        class _Svc:
            def get_daily_bars(self, *_args, **_kwargs):
                import pandas as pd
                return pd.DataFrame({"close": [1]}), "mock"

        with patch("src.data_sources.market_data_service.MarketDataService", return_value=_Svc()) as mocked:
            rc = main(["--source", "gaps", "--limit", "1", "--confirm", "--no-save"])
        assert rc == 0
        mocked.assert_called_once()

    def test_save_local_limit_capped(self) -> None:
        rc = main(["--limit", "10", "--confirm", "--save-local", "--max-tasks", "3"])
        assert rc == 1
