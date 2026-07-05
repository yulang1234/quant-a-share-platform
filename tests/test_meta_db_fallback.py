"""Test meta DB SQLite fallback and engine."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text

from src.db.meta_engine import get_meta_engine, reset_meta_engine
from src.db.schema_meta import ALL_TABLES, Base


@pytest.fixture(autouse=True)
def _override_meta_url(monkeypatch, tmp_path):
    db_path = tmp_path / "test_meta.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    yield
    reset_meta_engine()


class TestMetaEngine:
    def test_engine_creates_tables(self) -> None:
        engine = get_meta_engine()
        Base.metadata.create_all(engine)
        with engine.connect() as conn:
            tables = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )).fetchall()
            names = [r[0] for r in tables]
            assert "security_master" in names
            assert "universe_config" in names
            assert "data_provider_config" in names

    def test_sqlite_fallback_used_without_env(self) -> None:
        engine = get_meta_engine()
        assert "sqlite" in str(engine.url)

    def test_init_meta_db_cli(self) -> None:
        from src.db.migrations import init_meta_db
        init_meta_db()
        engine = get_meta_engine()
        with engine.connect() as conn:
            cnt = conn.execute(text("SELECT COUNT(*) FROM data_provider_config")).fetchone()[0]
            assert cnt == 4
