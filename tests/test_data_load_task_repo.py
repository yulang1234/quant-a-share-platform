"""Test DataLoadTask repository."""
import pytest
from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.data_tasks.task_repo import DataLoadTaskRepository, DataLoadTaskLogRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestTaskRepo:
    def test_create_and_list(self) -> None:
        repo = DataLoadTaskRepository()
        repo.create(symbol="000001", exchange="SZ", data_type="daily_bar",
                    adj_type="qfq", start_date="20200101", end_date="20201231")
        pending = repo.list_pending(limit=10)
        assert len(pending) >= 1

    def test_upsert_no_duplicate(self) -> None:
        repo = DataLoadTaskRepository()
        t1 = repo.upsert_task("000001", "SZ", "daily_bar", "qfq", "20200101", "20201231")
        t2 = repo.upsert_task("000001", "SZ", "daily_bar", "qfq", "20200101", "20201231")
        assert t1.task_id == t2.task_id

    def test_update_status(self) -> None:
        repo = DataLoadTaskRepository()
        t = repo.create(symbol="000002", exchange="SZ", data_type="daily_bar",
                        adj_type="raw", start_date="20200101", end_date="20201231")
        repo.update_status(t.task_id, "success", row_count=250, attempt_count=1)
        updated = repo.get_by_id(t.task_id)
        assert updated.status == "success"
        assert updated.row_count == 250

    def test_count_by_status(self) -> None:
        repo = DataLoadTaskRepository()
        repo.create(symbol="t1", exchange="SZ", data_type="daily_bar", adj_type="qfq",
                    start_date="20200101", end_date="20201231")
        counts = repo.count_by_status()
        assert "pending" in counts


class TestTaskLogRepo:
    def test_log(self) -> None:
        repo = DataLoadTaskRepository()
        t = repo.create(symbol="test", exchange="SZ", data_type="daily_bar",
                        adj_type="qfq", start_date="20200101", end_date="20201231")
        log_repo = DataLoadTaskLogRepository()
        entry = log_repo.log(t.task_id, "pending", "success", provider_used="local_cache",
                             row_count=100, duration_ms=500)
        assert entry.status_after == "success"
