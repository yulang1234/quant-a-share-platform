"""Test V1.4.10 data_quality_view UI data helpers (no Streamlit)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'meta.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    duck_path = tmp_path / "duckdb" / "test.duckdb"
    monkeypatch.setattr("config.settings.get_duckdb_path", lambda: duck_path)
    monkeypatch.setattr("src.storage.duckdb_repo.get_duckdb_path", lambda: duck_path)
    monkeypatch.setattr("config.settings.get_parquet_root", lambda: tmp_path / "parquet")
    reset_meta_engine()
    init_meta_db()
    from src.storage.duckdb_repo import close_connection, get_connection
    from src.storage.schema import CREATE_TABLE_SQL
    import os
    os.makedirs(tmp_path / "duckdb", exist_ok=True)
    close_connection()
    con = get_connection(duck_path)
    for ddl in CREATE_TABLE_SQL:
        con.execute(ddl)
    close_connection()
    yield
    reset_meta_engine()
    close_connection()


class TestStatusToCn:
    def test_known_statuses(self) -> None:
        from ui.components.data_quality_view import status_to_cn, HEALTH_STATUS_CN
        assert status_to_cn("healthy") == "健康"
        assert status_to_cn("usable_with_gaps") == "可用但有缺口"
        assert status_to_cn("risky") == "风险较高"
        assert status_to_cn("not_recommended") == "不建议分析"
        assert status_to_cn("unavailable") == "不可用"
        assert status_to_cn("unknown") == "未知"

    def test_unknown_falls_back_to_label(self) -> None:
        from ui.components.data_quality_view import status_to_cn
        assert status_to_cn("weird") == "weird"

    def test_none_is_unknown(self) -> None:
        from ui.components.data_quality_view import status_to_cn
        assert status_to_cn(None) == "未知"


class TestToCsvBytes:
    def test_bom_utf8(self) -> None:
        from ui.components.data_quality_view import to_csv_bytes
        b = to_csv_bytes(pd.DataFrame({"a": [1], "b": ["中文"]}))
        assert b.startswith(b"\xef\xbb\xbf")
        assert b"a,b" in b
        assert "中文".encode("utf-8") in b

    def test_empty_df(self) -> None:
        from ui.components.data_quality_view import to_csv_bytes
        b = to_csv_bytes(pd.DataFrame())
        assert isinstance(b, bytes)
        assert b.startswith(b"\xef\xbb\xbf")


class TestLoadersEmptyNoCrash:
    def test_load_quality_overview(self) -> None:
        from ui.components.data_quality_view import load_quality_overview
        o = load_quality_overview()
        assert "overall_status_cn" in o
        assert "top_issues" in o

    def test_load_coverage_table_empty(self) -> None:
        # Without coverage data, the dashboard still emits "unknown" rows for
        # the default universes (core_50/100/500 × raw/qfq). The point of this
        # test is: the loader never crashes and yields a well-formed DataFrame,
        # with all coverage_level values translated to "未知".
        from ui.components.data_quality_view import (
            load_coverage_table, COVERAGE_COLUMNS,
        )
        df = load_coverage_table()
        assert list(df.columns) == list(COVERAGE_COLUMNS)
        assert (df["coverage_level"] == "未知").all()
        assert (df["expected_count"] == 0).all()

    def test_load_calendar_summary(self) -> None:
        from ui.components.data_quality_view import load_calendar_summary
        h = load_calendar_summary()
        assert "health_status_cn" in h
        assert h["health_status_cn"] in ("未知", "不建议分析", "风险较高")

    def test_load_security_master_summary(self) -> None:
        from ui.components.data_quality_view import load_security_master_summary
        h = load_security_master_summary()
        assert "health_status_cn" in h

    def test_load_provider_table_empty(self) -> None:
        from ui.components.data_quality_view import (
            load_provider_table, PROVIDER_COLUMNS,
        )
        df = load_provider_table()
        assert df.empty
        assert list(df.columns) == list(PROVIDER_COLUMNS)

    def test_load_batch_health_summary(self) -> None:
        from ui.components.data_quality_view import load_batch_health_summary
        h = load_batch_health_summary()
        assert "health_status_cn" in h
        assert h["total_batches"] == 0

    def test_load_storage_table(self) -> None:
        from ui.components.data_quality_view import (
            load_storage_table, STORAGE_COLUMNS,
        )
        df = load_storage_table()
        assert list(df.columns) == list(STORAGE_COLUMNS)


class TestOverviewMetrics:
    def test_empty_overview(self) -> None:
        from ui.components.data_quality_view import overview_metrics
        m = overview_metrics({
            "overall_status_cn": "未知", "overall_score": None,
            "generated_at": None, "status_reason": "",
        })
        assert m["overall_status_cn"] == "未知"
        # Coverage rates default to None for empty data.
        assert m["core_50_coverage_rate"] is None
        assert m["raw_coverage_rate"] is None

    def test_with_coverage_data(self) -> None:
        # Seed a universe + coverage row.
        from src.repositories.universe_repo import UniverseRepository
        from src.data_quality.coverage_repo import CoverageReportRepository
        repo = UniverseRepository()
        u = repo.add_universe(name="core_50")
        uid = u.universe_id
        CoverageReportRepository().upsert(
            universe_id=uid, security_id=1, symbol="000001",
            exchange="SZ", asset_type="stock", data_type="daily_bar",
            adj_type="raw", start_date="20240101", end_date="20240131",
            expected_trade_days=100, actual_trade_days=90, missing_trade_days=10,
            coverage_rate=0.9, status="partial",
            first_data_date="2024-01-01", last_data_date="2024-01-31",
            source="coverage_scanner", generated_at=datetime.now(),
        )
        from ui.components.data_quality_view import overview_metrics
        m = overview_metrics({
            "overall_status_cn": "未知", "overall_score": None,
            "generated_at": None, "status_reason": "",
        })
        assert abs(m["core_50_coverage_rate"] - 0.9) < 1e-6
        assert abs(m["raw_coverage_rate"] - 0.9) < 1e-6


class TestOverviewToCn:
    def test_translates_sub_statuses(self) -> None:
        from ui.components.data_quality_view import overview_to_cn
        o = overview_to_cn({
            "overall_status": "healthy",
            "coverage_status": "risky",
            "calendar_status": "healthy",
            "security_master_status": "usable_with_gaps",
            "provider_status": "unavailable",
            "batch_status": "unknown",
            "storage_status": "not_recommended",
        })
        assert o["overall_status_cn"] == "健康"
        assert o["coverage_status_cn"] == "风险较高"
        assert o["provider_status_cn"] == "不可用"
        assert o["batch_status_cn"] == "未知"
        assert o["storage_status_cn"] == "不建议分析"
        assert o["security_master_status_cn"] == "可用但有缺口"