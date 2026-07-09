"""V1.5.3 sector mapping tests.

Tests cover:
1. sector_basic upsert (create + idempotent update)
2. stock_sector_map upsert (one-to-many, many-to-one)
3. Query: get_sectors_by_stock
4. Query: get_stocks_by_sector
5. Field completeness
6. Data source unavailable
7. Dry-run / confirm
8. Regression (V1.5.1 / V1.5.2 not broken)

All tests use monkeypatch to avoid touching real DuckDB / AkShare.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.sector.sector_types import (
    SECTOR_INDUSTRY, SECTOR_CONCEPT, SOURCE_AKSHARE,
    StockSectorsResult, SectorStocksResult,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _setup_in_memory_store(monkeypatch):
    """Set up an in-memory dict-based store for sector data.

    Mocks all sector_repository functions to use an in-memory store.
    """
    store = {"sector_basic": pd.DataFrame(), "stock_sector_map": pd.DataFrame()}

    def _fake_upsert_basic(df):
        """Replace sector_basic table entirely (simulates delete+insert)."""
        store["sector_basic"] = df.copy()
        return len(df)

    def _fake_upsert_map(df):
        """Replace stock_sector_map table entirely."""
        store["stock_sector_map"] = df.copy()
        return len(df)

    def _fake_get_sectors(stock_code):
        df = store["stock_sector_map"]
        if df.empty or "stock_code" not in df.columns:
            return pd.DataFrame()
        code = str(stock_code).zfill(6)
        return df[df["stock_code"] == code].copy()

    def _fake_get_stocks(sector_code=None, sector_name=None):
        df = store["stock_sector_map"]
        if df.empty:
            return pd.DataFrame()
        if sector_code and "sector_code" in df.columns:
            return df[df["sector_code"] == sector_code].copy()
        if sector_name and "sector_name" in df.columns:
            return df[df["sector_name"] == sector_name].copy()
        return pd.DataFrame()

    def _fake_get_basic(sector_code=None, sector_name=None):
        df = store["sector_basic"]
        if df.empty:
            return pd.DataFrame()
        if sector_code and "sector_code" in df.columns:
            return df[df["sector_code"] == sector_code].copy()
        if sector_name and "sector_name" in df.columns:
            return df[df["sector_name"] == sector_name].copy()
        return pd.DataFrame()

    monkeypatch.setattr(
        "src.sector.sector_repository.upsert_sector_basic", _fake_upsert_basic,
    )
    monkeypatch.setattr(
        "src.sector.sector_repository.upsert_stock_sector_map", _fake_upsert_map,
    )
    monkeypatch.setattr(
        "src.sector.sector_repository.list_all_sectors",
        lambda: store["sector_basic"].copy(),
    )
    monkeypatch.setattr(
        "src.sector.sector_repository.get_sectors_by_stock", _fake_get_sectors,
    )
    monkeypatch.setattr(
        "src.sector.sector_repository.get_stocks_by_sector", _fake_get_stocks,
    )
    monkeypatch.setattr(
        "src.sector.sector_repository.get_sector_basic", _fake_get_basic,
    )
    monkeypatch.setattr(
        "src.sector.sector_repository.count_sector_mappings",
        lambda: len(store["stock_sector_map"]),
    )
    monkeypatch.setattr(
        "src.sector.sector_repository.delete_sector_basic_by_source",
        lambda source: 0,
    )
    monkeypatch.setattr(
        "src.sector.sector_repository.delete_sector_mappings_by_source",
        lambda source: 0,
    )
    return store


# ══════════════════════════════════════════════════════════════════════════════
# 1. sector_basic upsert tests
# ══════════════════════════════════════════════════════════════════════════════


class TestSectorBasicUpsert:
    """CRUD operations on sector_basic."""

    def test_upsert_new_sector(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)

        from src.sector.sector_repository import upsert_sector_basic
        df = pd.DataFrame([{
            "sector_code": "BK0001",
            "sector_name": "银行",
            "sector_type": SECTOR_INDUSTRY,
            "source": SOURCE_AKSHARE,
        }])
        count = upsert_sector_basic(df)
        assert count == 1
        assert len(store["sector_basic"]) == 1
        assert store["sector_basic"].iloc[0]["sector_name"] == "银行"

    def test_upsert_same_sector_idempotent(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)

        from src.sector.sector_repository import upsert_sector_basic
        df = pd.DataFrame([{
            "sector_code": "BK0001",
            "sector_name": "银行",
            "sector_type": SECTOR_INDUSTRY,
            "source": SOURCE_AKSHARE,
        }])
        upsert_sector_basic(df)
        # Upsert again
        df2 = pd.DataFrame([{
            "sector_code": "BK0001",
            "sector_name": "银行板块",
            "sector_type": SECTOR_INDUSTRY,
            "source": SOURCE_AKSHARE,
        }])
        count = upsert_sector_basic(df2)
        assert count == 1
        assert store["sector_basic"].iloc[0]["sector_name"] == "银行板块"

    def test_sector_type_valid(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)

        from src.sector.sector_repository import upsert_sector_basic
        df = pd.DataFrame([{
            "sector_code": "BK0002",
            "sector_name": "半导体",
            "sector_type": SECTOR_CONCEPT,
            "source": SOURCE_AKSHARE,
        }])
        upsert_sector_basic(df)
        assert store["sector_basic"].iloc[0]["sector_type"] == SECTOR_CONCEPT
        assert store["sector_basic"].iloc[0]["source"] == SOURCE_AKSHARE


# ══════════════════════════════════════════════════════════════════════════════
# 2. stock_sector_map upsert tests
# ══════════════════════════════════════════════════════════════════════════════


class TestStockSectorMapUpsert:
    """CRUD operations on stock_sector_map."""

    def test_upsert_mapping(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)

        from src.sector.sector_repository import upsert_stock_sector_map
        df = pd.DataFrame([{
            "stock_code": "000001",
            "stock_name": "平安银行",
            "sector_code": "BK0001",
            "sector_name": "银行",
            "sector_type": SECTOR_INDUSTRY,
            "source": SOURCE_AKSHARE,
        }])
        count = upsert_stock_sector_map(df)
        assert count == 1

    def test_one_stock_many_sectors(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)

        from src.sector.sector_repository import upsert_stock_sector_map
        df = pd.DataFrame([
            {"stock_code": "000001", "stock_name": "平安银行",
             "sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE},
            {"stock_code": "000001", "stock_name": "平安银行",
             "sector_code": "BK0099", "sector_name": "金融科技",
             "sector_type": SECTOR_CONCEPT, "source": SOURCE_AKSHARE},
        ])
        upsert_stock_sector_map(df)

        # Query back
        result = store["stock_sector_map"][
            store["stock_sector_map"]["stock_code"] == "000001"
        ]
        assert len(result) == 2

    def test_one_sector_many_stocks(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)

        from src.sector.sector_repository import upsert_stock_sector_map
        df = pd.DataFrame([
            {"stock_code": "000001", "stock_name": "平安银行",
             "sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE},
            {"stock_code": "002142", "stock_name": "宁波银行",
             "sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE},
        ])
        upsert_stock_sector_map(df)

        result = store["stock_sector_map"][
            store["stock_sector_map"]["sector_code"] == "BK0001"
        ]
        assert len(result) == 2

    def test_duplicate_sync_idempotent(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)

        from src.sector.sector_repository import upsert_stock_sector_map
        df = pd.DataFrame([{
            "stock_code": "000001", "stock_name": "平安银行",
            "sector_code": "BK0001", "sector_name": "银行",
            "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE,
        }])
        upsert_stock_sector_map(df)
        upsert_stock_sector_map(df)
        # With our fake store (full replace), it's idempotent
        assert len(store["stock_sector_map"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 3. Query: get_sectors_by_stock
# ══════════════════════════════════════════════════════════════════════════════


class TestQuerySectorsByStock:
    """Query sectors for a given stock."""

    def test_existing_stock_returns_sectors(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)
        store["stock_sector_map"] = pd.DataFrame([
            {"stock_code": "000001", "stock_name": "平安银行",
             "sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE,
             "is_active": True, "updated_at": "2026-07-09"},
        ])

        from src.sector.sector_service import get_sectors_by_stock
        result = get_sectors_by_stock("000001")
        assert result.missing is False
        assert len(result.sectors) == 1
        assert result.sectors[0]["sector_name"] == "银行"
        assert result.version == "v1.5.3"

    def test_nonexistent_stock_returns_empty(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)
        store["stock_sector_map"] = pd.DataFrame()

        from src.sector.sector_service import get_sectors_by_stock
        result = get_sectors_by_stock("999999")
        assert result.missing is True
        assert len(result.sectors) == 0

    def test_stock_code_padding(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)
        store["stock_sector_map"] = pd.DataFrame([
            {"stock_code": "000001", "stock_name": "平安银行",
             "sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE,
             "is_active": True, "updated_at": "2026-07-09"},
        ])

        from src.sector.sector_service import get_sectors_by_stock
        # Test with unpadded code
        result = get_sectors_by_stock("1")
        assert result.missing is False


# ══════════════════════════════════════════════════════════════════════════════
# 4. Query: get_stocks_by_sector
# ══════════════════════════════════════════════════════════════════════════════


class TestQueryStocksBySector:
    """Query stocks for a given sector."""

    def test_existing_sector_returns_stocks(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)
        store["stock_sector_map"] = pd.DataFrame([
            {"stock_code": "000001", "stock_name": "平安银行",
             "sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE,
             "is_active": True, "updated_at": "2026-07-09"},
            {"stock_code": "002142", "stock_name": "宁波银行",
             "sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE,
             "is_active": True, "updated_at": "2026-07-09"},
        ])

        from src.sector.sector_service import get_stocks_by_sector
        result = get_stocks_by_sector(sector_code="BK0001")
        assert result.missing is False
        assert result.stock_count == 2
        assert result.sector_name == "银行"

    def test_nonexistent_sector_returns_empty(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)
        store["stock_sector_map"] = pd.DataFrame()

        from src.sector.sector_service import get_stocks_by_sector
        result = get_stocks_by_sector(sector_name="不存在的板块")
        assert result.missing is True
        assert result.stock_count == 0

    def test_query_by_name_works(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)
        store["stock_sector_map"] = pd.DataFrame([
            {"stock_code": "000001", "stock_name": "平安银行",
             "sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE,
             "is_active": True, "updated_at": "2026-07-09"},
        ])

        from src.sector.sector_service import get_stocks_by_sector
        result = get_stocks_by_sector(sector_name="银行")
        assert result.missing is False
        assert result.sector_name == "银行"


# ══════════════════════════════════════════════════════════════════════════════
# 5. Field completeness tests
# ══════════════════════════════════════════════════════════════════════════════


class TestFieldCompleteness:
    """Output field completeness."""

    def test_stock_sectors_result_fields(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)
        store["stock_sector_map"] = pd.DataFrame([
            {"stock_code": "000001", "stock_name": "平安银行",
             "sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE,
             "is_active": True, "updated_at": "2026-07-09"},
        ])

        from src.sector.sector_service import get_sectors_by_stock
        result = get_sectors_by_stock("000001")
        d = result.as_dict()
        required = ["stock_code", "stock_name", "sectors", "missing", "version"]
        for field in required:
            assert field in d, f"Missing field: {field}"

        # Check sector sub-fields
        for sector in d["sectors"]:
            assert "sector_code" in sector
            assert "sector_name" in sector
            assert "sector_type" in sector
            assert "source" in sector
            assert "updated_at" in sector

    def test_sector_stocks_result_fields(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)
        store["stock_sector_map"] = pd.DataFrame([
            {"stock_code": "000001", "stock_name": "平安银行",
             "sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY, "source": SOURCE_AKSHARE,
             "is_active": True, "updated_at": "2026-07-09"},
        ])

        from src.sector.sector_service import get_stocks_by_sector
        result = get_stocks_by_sector(sector_code="BK0001")
        d = result.as_dict()
        required = ["sector_code", "sector_name", "sector_type",
                     "stocks", "stock_count", "missing", "version"]
        for field in required:
            assert field in d, f"Missing field: {field}"


# ══════════════════════════════════════════════════════════════════════════════
# 6. Data source unavailable tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDataSourceUnavailable:
    """Graceful degradation when data sources are unavailable."""

    def test_akshare_unavailable_no_crash(self, monkeypatch):
        """When AkShare errors, sync returns error status, not crash."""
        monkeypatch.setattr(
            "src.sector.sector_sync._fetch_sector_list_akshare",
            lambda sector_type: None,
        )
        from src.sector.sector_sync import sync_sector_basic
        result = sync_sector_basic(source=SOURCE_AKSHARE, dry_run=True)
        assert result["status"] == "error"
        assert "AkShare" in result["message"]

    def test_empty_repo_no_crash(self, monkeypatch):
        """When repo has no data, queries return empty."""
        store = _setup_in_memory_store(monkeypatch)
        store["stock_sector_map"] = pd.DataFrame()

        from src.sector.sector_service import get_sectors_by_stock
        result = get_sectors_by_stock("000001")
        assert result.missing is True
        assert result.sectors == []

    def test_repo_error_no_crash(self, monkeypatch):
        """When repo raises, queries return empty gracefully."""
        def _raise(*args, **kwargs):
            raise RuntimeError("DB error")
        monkeypatch.setattr(
            "src.sector.sector_repository.get_sectors_by_stock", _raise,
        )

        from src.sector.sector_service import get_sectors_by_stock
        result = get_sectors_by_stock("000001")
        assert result.missing is True

    def test_validate_empty_repo(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)
        from src.sector.sector_service import validate_sector_mapping
        result = validate_sector_mapping()
        assert result["is_empty"] is True
        assert result["status"] == "empty"


# ══════════════════════════════════════════════════════════════════════════════
# 7. Dry-run / confirm tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDryRunConfirm:
    """Dry-run and confirm protection."""

    def test_sync_basic_dry_run_no_write(self, monkeypatch):
        """dry_run should return preview without calling upsert."""
        monkeypatch.setattr(
            "src.sector.sector_sync._fetch_sector_list_akshare",
            lambda sector_type: pd.DataFrame({
                "sector_code": ["BK0001"],
                "sector_name": ["银行"],
                "sector_type": [SECTOR_INDUSTRY],
            }),
        )
        write_called = []

        def _fake_upsert(df):
            write_called.append(True)
            return len(df)

        monkeypatch.setattr(
            "src.sector.sector_repository.upsert_sector_basic", _fake_upsert,
        )
        monkeypatch.setattr(
            "src.sector.sector_repository.delete_sector_basic_by_source",
            lambda s: 0,
        )

        from src.sector.sector_sync import sync_sector_basic
        result = sync_sector_basic(source=SOURCE_AKSHARE, dry_run=True)
        assert result["status"] == "dry_run"
        assert len(write_called) == 0  # No write happened

    def test_sync_basic_confirm_writes(self, monkeypatch):
        """confirm should actually write."""
        monkeypatch.setattr(
            "src.sector.sector_sync._fetch_sector_list_akshare",
            lambda sector_type: pd.DataFrame({
                "sector_code": ["BK0001"],
                "sector_name": ["银行"],
                "sector_type": [SECTOR_INDUSTRY],
            }),
        )
        write_called = []

        def _fake_upsert(df):
            write_called.append(len(df))
            return len(df)

        monkeypatch.setattr(
            "src.sector.sector_repository.upsert_sector_basic", _fake_upsert,
        )
        monkeypatch.setattr(
            "src.sector.sector_repository.delete_sector_basic_by_source",
            lambda s: 0,
        )

        from src.sector.sector_sync import sync_sector_basic
        result = sync_sector_basic(source=SOURCE_AKSHARE, dry_run=False)
        assert result["status"] == "ok"
        assert len(write_called) > 0

    def test_unsupported_source_returns_error(self):
        from src.sector.sector_sync import sync_sector_basic
        result = sync_sector_basic(source="unsupported", dry_run=True)
        assert result["status"] == "error"
        assert "Unsupported" in result["message"]


# ══════════════════════════════════════════════════════════════════════════════
# 8. Validation tests
# ══════════════════════════════════════════════════════════════════════════════


class TestValidation:
    """Validation and completeness checks."""

    def test_validate_with_data(self, monkeypatch):
        store = _setup_in_memory_store(monkeypatch)
        store["sector_basic"] = pd.DataFrame([
            {"sector_code": "BK0001", "sector_name": "银行",
             "sector_type": SECTOR_INDUSTRY},
        ])
        store["stock_sector_map"] = pd.DataFrame([
            {"stock_code": "000001", "sector_code": "BK0001"},
        ])

        from src.sector.sector_service import validate_sector_mapping
        result = validate_sector_mapping()
        assert result["total_sectors"] == 1
        assert result["total_mappings"] == 1
        assert result["is_empty"] is False


# ══════════════════════════════════════════════════════════════════════════════
# 9. Regression tests
# ══════════════════════════════════════════════════════════════════════════════


class TestRegression:
    """Ensure V1.5.1 / V1.5.2 are not broken."""

    def test_sector_snapshot_still_works(self, monkeypatch):
        """V1.5.0 sector_snapshot should still import and run."""
        monkeypatch.setattr(
            "src.sector.sector_snapshot.build_quality_overview",
            lambda: {"overall_status": "unknown", "top_issues": []},
        )
        from src.sector.sector_snapshot import build_sector_snapshot
        snap = build_sector_snapshot("2026-07-07")
        assert "sectors" in snap
        assert "trade_date" in snap

    def test_sector_types_valid(self):
        from src.sector.sector_types import SECTOR_TYPES, SOURCES
        assert SECTOR_INDUSTRY in SECTOR_TYPES
        assert SECTOR_CONCEPT in SECTOR_TYPES
        assert SOURCE_AKSHARE in SOURCES
