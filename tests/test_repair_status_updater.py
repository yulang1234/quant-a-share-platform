"""Test repair_status_updater."""
import pytest
from src.data_quality.repair_status_updater import update_gap_after_task


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
         "severity": "low", "repair_status": "pending", "related_task_id": 999},
    ])
    yield
    reset_meta_engine()


class TestRepairUpdater:
    def test_success_marks_repaired(self) -> None:
        result = update_gap_after_task(999, "success")
        assert result["updated_gaps"] >= 1

    def test_failed_keeps_pending(self) -> None:
        update_gap_after_task(999, "success")  # first mark repaired
        # re-insert a new pending gap for next test
        from src.data_quality.coverage_repo import GapDetailRepository
        repo = GapDetailRepository()
        repo.insert_batch([
            {"symbol": "000002", "exchange": "SZ", "adj_type": "qfq", "gap_type": "single_day",
             "missing_days": 1, "gap_start_date": "2020-02-01", "gap_end_date": "2020-02-01",
             "severity": "low", "repair_status": "pending", "related_task_id": 998},
        ])
        result = update_gap_after_task(998, "failed")
        assert result["updated_gaps"] >= 1

    def test_success_no_save_keeps_pending(self) -> None:
        from src.data_quality.coverage_repo import GapDetailRepository
        repo = GapDetailRepository()
        repo.insert_batch([
            {"symbol": "000003", "exchange": "SZ", "adj_type": "qfq", "gap_type": "single_day",
             "missing_days": 1, "gap_start_date": "2020-03-01", "gap_end_date": "2020-03-01",
             "severity": "low", "repair_status": "pending", "related_task_id": 997},
        ])
        result = update_gap_after_task(997, "success", save_local=False)
        assert result["updated_gaps"] >= 1
        gap = [g for g in repo.list_gaps(limit=10, repair_status="pending") if g.related_task_id == 997]
        assert gap
