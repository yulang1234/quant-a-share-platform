"""
Tests for the stock pool module (src/universe/stock_pool.py).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.storage.duckdb_repo import close_connection, init_database, query_df
from src.universe.stock_pool import (
    activate_stock,
    add_stock_to_pool,
    blacklist_stock,
    deactivate_stock,
    delete_stock_from_pool,
    get_active_stock_pool,
    get_stock_pool,
    infer_exchange,
    load_stock_pool_from_csv,
    remove_blacklist,
    save_stock_pool_to_db,
    validate_stock_code,
)

# ── Fixtures ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point DuckDB to a temp file and init tables before each test."""
    db_path = tmp_path / "test_stock_pool.duckdb"

    import config.settings as settings_mod
    import importlib
    monkeypatch.setattr(settings_mod, "get_duckdb_path", lambda: db_path)
    importlib.reload(settings_mod)

    # Re-init the repo module to pick up the new path
    import src.storage.duckdb_repo as repo
    importlib.reload(repo)
    repo.init_database(db_path)
    yield
    repo.close_connection()


# ======================================================================
#  validate_stock_code
# ======================================================================

class TestValidateStockCode:
    def test_normal_6_digit(self) -> None:
        assert validate_stock_code("000001") == "000001"
        assert validate_stock_code("600519") == "600519"
        assert validate_stock_code("300750") == "300750"

    def test_int_input(self) -> None:
        assert validate_stock_code(1) == "000001"
        assert validate_stock_code(600519) == "600519"
        assert validate_stock_code(858) == "000858"

    def test_raises_on_non_numeric(self) -> None:
        with pytest.raises(ValueError, match="numeric"):
            validate_stock_code("abc")
        with pytest.raises(ValueError, match="numeric"):
            validate_stock_code("00000a")
        with pytest.raises(ValueError, match="numeric"):
            validate_stock_code("")

    def test_raises_on_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="too long|6 digits"):
            validate_stock_code("1234567")
        with pytest.raises(ValueError, match="6 digits"):
            validate_stock_code("12345")  # 5 digits even after zfill -> "012345" is fine? No, 5 digits -> zfill -> "012345" = 6 digits!
            # Actually "12345" zfilled is "012345" which is 6 digits, so it should work.
            # Let me check the spec: "12345" -> ValueError (spec says 不满足6位)

    def test_raises_on_5_digit(self) -> None:
        """5 digits should fail after zfill -> actually zfill makes it 6"""
        with pytest.raises(ValueError):
            validate_stock_code("12345")

    def test_strip_whitespace(self) -> None:
        assert validate_stock_code(" 000001 ") == "000001"
        assert validate_stock_code(" 600519 ") == "600519"


# ======================================================================
#  infer_exchange
# ======================================================================

class TestInferExchange:
    def test_sh(self) -> None:
        assert infer_exchange("600519") == "SH"
        assert infer_exchange("601318") == "SH"
        assert infer_exchange("688001") == "SH"

    def test_sz_0xxx(self) -> None:
        assert infer_exchange("000001") == "SZ"
        assert infer_exchange("002415") == "SZ"

    def test_sz_3xxx(self) -> None:
        assert infer_exchange("300750") == "SZ"
        assert infer_exchange("301001") == "SZ"

    def test_bj(self) -> None:
        assert infer_exchange("830000") == "BJ"
        assert infer_exchange("430000") == "BJ"
        assert infer_exchange("888888") == "BJ"

    def test_unknown(self) -> None:
        assert infer_exchange("999999") == "UNKNOWN"
        assert infer_exchange("1234") == "UNKNOWN"
        assert infer_exchange("") == "UNKNOWN"
        assert infer_exchange("abc") == "UNKNOWN"


# ======================================================================
#  load_stock_pool_from_csv
# ======================================================================

class TestLoadCSV:
    def test_load_default_csv(self) -> None:
        df = load_stock_pool_from_csv()
        assert len(df) >= 10
        assert "stock_code" in df.columns
        assert "stock_name" in df.columns

    def test_stock_code_is_6_digit_string(self) -> None:
        df = load_stock_pool_from_csv()
        for code in df["stock_code"]:
            assert isinstance(code, str), f"Expected str, got {type(code)}"
            assert len(code) == 6, f"Expected 6 digits, got '{code}'"
            assert code.isdigit(), f"Expected numeric, got '{code}'"

    def test_bool_fields(self) -> None:
        df = load_stock_pool_from_csv()
        for col in ("is_active", "is_blacklisted"):
            assert col in df.columns
            assert df[col].dtype == bool, f"{col} is {df[col].dtype}, expected bool"

    def test_required_fields_exist(self) -> None:
        df = load_stock_pool_from_csv()
        required = {"stock_code", "stock_name", "market", "exchange",
                    "pool_name", "source", "is_active", "is_blacklisted"}
        assert required.issubset(set(df.columns)), f"Missing: {required - set(df.columns)}"

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_stock_pool_from_csv("nonexistent.csv")

    def test_infer_exchange_on_load(self) -> None:
        df = load_stock_pool_from_csv()
        # 000001 (SZ), 600519 (SH), 300750 (SZ)
        codes = dict(zip(df["stock_code"], df["exchange"]))
        assert codes.get("000001") == "SZ", f"Got {codes.get('000001')}"
        assert codes.get("600519") == "SH", f"Got {codes.get('600519')}"
        assert codes.get("300750") == "SZ", f"Got {codes.get('300750')}"


# ======================================================================
#  save_stock_pool_to_db / query
# ======================================================================

class TestSaveAndQuery:
    def test_save_and_query(self) -> None:
        df = load_stock_pool_from_csv()
        result = save_stock_pool_to_db(df)
        assert result["total_count"] >= 10
        assert result["inserted_count"] >= 10

        # Query back
        qdf = get_stock_pool()
        assert len(qdf) >= 10

    def test_no_duplicates_on_reimport(self) -> None:
        df = load_stock_pool_from_csv()
        save_stock_pool_to_db(df)  # first
        result = save_stock_pool_to_db(df)  # second
        # Identical data -> all skipped
        assert result["inserted_count"] == 0
        assert result["updated_count"] == 0
        assert result["skipped_count"] >= 10

        # Only one copy in DB
        qdf = get_stock_pool()
        codes = qdf["stock_code"].tolist()
        assert len(codes) == len(set(codes))  # no duplicate codes

    def test_active_pool_only(self) -> None:
        df = load_stock_pool_from_csv()
        save_stock_pool_to_db(df)

        active = get_active_stock_pool()
        assert len(active) >= 10
        for _, row in active.iterrows():
            assert row["stock_code"] is not None

    def test_get_stock_pool_filters(self) -> None:
        df = load_stock_pool_from_csv()
        save_stock_pool_to_db(df)

        # Activate-only filter
        active = get_stock_pool(include_inactive=False, include_blacklisted=False)
        assert len(active) >= 10

    def test_add_single_stock(self) -> None:
        result = add_stock_to_pool("000002", "万科A")
        assert result["success"]
        assert result["action"] == "inserted"

        qdf = get_stock_pool()
        assert "000002" in qdf["stock_code"].values

    def test_add_stock_reactivates(self) -> None:
        add_stock_to_pool("000002", "万科A")
        deactivate_stock("000002")
        result = add_stock_to_pool("000002", "万科A")
        assert result["action"] == "updated"

        active = get_active_stock_pool()
        assert "000002" in active["stock_code"].values


# ======================================================================
#  Status management
# ======================================================================

class TestStatusManagement:
    @pytest.fixture(autouse=True)
    def _seed(self) -> None:
        df = load_stock_pool_from_csv()
        save_stock_pool_to_db(df)

    def test_deactivate(self) -> None:
        ok = deactivate_stock("000001")
        assert ok

        qdf = get_stock_pool(include_inactive=True)
        row = qdf[qdf["stock_code"] == "000001"].iloc[0]
        assert not row["is_active"]  # noqa: E712

    def test_activate(self) -> None:
        deactivate_stock("000001")
        ok = activate_stock("000001")
        assert ok

        qdf = get_stock_pool(include_inactive=True)
        row = qdf[qdf["stock_code"] == "000001"].iloc[0]
        assert row["is_active"]  # noqa: E712

    def test_blacklist(self) -> None:
        ok = blacklist_stock("000001")
        assert ok

        qdf = get_stock_pool(include_inactive=True, include_blacklisted=True)
        row = qdf[qdf["stock_code"] == "000001"].iloc[0]
        assert row["is_blacklisted"]  # noqa: E712
        assert not row["is_active"]  # noqa: E712

    def test_remove_blacklist(self) -> None:
        blacklist_stock("000001")
        ok = remove_blacklist("000001")
        assert ok

        qdf = get_stock_pool(include_inactive=True, include_blacklisted=True)
        row = qdf[qdf["stock_code"] == "000001"].iloc[0]
        assert not row["is_blacklisted"]  # noqa: E712
        # Should NOT auto-activate
        assert not row["is_active"]  # noqa: E712

    def test_blacklist_excludes_from_active(self) -> None:
        blacklist_stock("600519")
        active = get_active_stock_pool()
        assert "600519" not in active["stock_code"].values

    def test_deactivate_unknown_code(self) -> None:
        ok = deactivate_stock("999999")
        assert ok is False

    def test_activate_unknown_code(self) -> None:
        ok = activate_stock("999999")
        assert ok is False

    def test_blacklist_unknown_code(self) -> None:
        ok = blacklist_stock("999999")
        assert ok is False


# ======================================================================
#  Delete
# ======================================================================

class TestDelete:
    @pytest.fixture(autouse=True)
    def _seed(self) -> None:
        df = load_stock_pool_from_csv()
        save_stock_pool_to_db(df)

    def test_delete_existing(self) -> None:
        ok = delete_stock_from_pool("000001")
        assert ok

        qdf = get_stock_pool()
        assert "000001" not in qdf["stock_code"].values

    def test_delete_nonexistent(self) -> None:
        ok = delete_stock_from_pool("999999")
        assert ok is False
