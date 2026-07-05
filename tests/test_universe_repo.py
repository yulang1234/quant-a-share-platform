"""Test UniverseRepository."""
import pytest
from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.repositories.universe_repo import UniverseRepository


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


class TestUniverse:
    def test_add_and_list(self) -> None:
        repo = UniverseRepository()
        repo.add_universe("universe_test", "test universe")
        unis = repo.list_universes()
        names = [u.universe_name for u in unis]
        assert "universe_test" in names

    def test_add_member(self) -> None:
        repo = UniverseRepository()
        u = repo.add_universe("test_u2b", "desc")
        repo.add_member(u.universe_id, "000001", "SZ")
        assert repo.count_members(u.universe_id) >= 1

    def test_add_duplicate_universe(self) -> None:
        repo = UniverseRepository()
        u1 = repo.add_universe("dup_test")
        u2 = repo.add_universe("dup_test")
        assert u1.universe_id == u2.universe_id
