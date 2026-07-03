"""
Shared pytest fixtures for the quant-a-share-platform test suite.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.storage.duckdb_repo import close_connection, get_connection
from src.storage.schema import CREATE_TABLE_SQL


@pytest.fixture
def fresh_db() -> Generator[Path, None, None]:
    """Create a temporary DuckDB database with the full schema.

    Yields the path to the temporary database.  The connection singleton is
    reset before and after each test so that tests are isolated from the
    project's real ``data/duckdb/quant_a_share.duckdb``.
    """
    close_connection()
    tmp_dir = Path(tempfile.mkdtemp())
    db_path = tmp_dir / "test.duckdb"

    con = get_connection(db_path)
    for ddl in CREATE_TABLE_SQL:
        con.execute(ddl)

    yield db_path

    close_connection()
    shutil.rmtree(tmp_dir, ignore_errors=True)
