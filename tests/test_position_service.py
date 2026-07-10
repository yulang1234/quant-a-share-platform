"""Test position_service — validation, normalization, enrichment, snapshot."""

import json

import pytest

from src.db.meta_engine import reset_meta_engine
from src.db.migrations import init_meta_db
from src.portfolio.position_service import (
    build_entry_snapshot,
    normalize_stock_code,
    parse_snapshot_safe,
    resolve_security_info,
    resolve_sector_name,
    validate_position_input,
)
from src.portfolio.position_types import PositionValidationError


@pytest.fixture(autouse=True)
def _setup(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test_svc.db'}"
    monkeypatch.setattr("config.settings.get_meta_db_url", lambda: url)
    reset_meta_engine()
    init_meta_db()
    yield
    reset_meta_engine()


def _valid_data(**overrides):
    d = {
        "portfolio_name": "default",
        "stock_code": "000001",
        "exchange": "SZ",
        "stock_name": "平安银行",
        "buy_date": "2026-06-01",
        "avg_cost": 12.50,
        "quantity": 1000,
        "position_pct": 10.0,
        "buy_reason": "测试买入理由",
        "is_simulated": False,
    }
    d.update(overrides)
    return d.copy()


class TestNormalizeStockCode:
    def test_zfill_short_code(self) -> None:
        assert normalize_stock_code("1") == "000001"

    def test_keep_full_code(self) -> None:
        assert normalize_stock_code("600519") == "600519"

    def test_strip_whitespace(self) -> None:
        assert normalize_stock_code(" 000001 ") == "000001"

    def test_reject_letters(self) -> None:
        with pytest.raises(PositionValidationError):
            normalize_stock_code("abc123")

    def test_reject_empty(self) -> None:
        with pytest.raises(PositionValidationError):
            normalize_stock_code("")

    def test_reject_too_long(self) -> None:
        with pytest.raises(PositionValidationError):
            normalize_stock_code("1234567")


class TestValidatePositionInput:
    def test_valid_data_passes(self) -> None:
        data = _valid_data()
        validate_position_input(data)  # should not raise

    def test_stock_code_normalized(self) -> None:
        data = _valid_data(stock_code="1")
        validate_position_input(data)
        assert data["stock_code"] == "000001"

    def test_buy_date_invalid(self) -> None:
        with pytest.raises(PositionValidationError):
            validate_position_input(_valid_data(buy_date="bad"))

    def test_avg_cost_zero_rejected(self) -> None:
        with pytest.raises(PositionValidationError):
            validate_position_input(_valid_data(avg_cost=0))

    def test_avg_cost_negative_rejected(self) -> None:
        with pytest.raises(PositionValidationError):
            validate_position_input(_valid_data(avg_cost=-5))

    def test_quantity_negative_rejected(self) -> None:
        with pytest.raises(PositionValidationError):
            validate_position_input(_valid_data(quantity=-100))

    def test_quantity_none_allowed(self) -> None:
        data = _valid_data(quantity=None)
        validate_position_input(data)  # should not raise

    def test_position_pct_below_zero_rejected(self) -> None:
        with pytest.raises(PositionValidationError):
            validate_position_input(_valid_data(position_pct=-1))

    def test_position_pct_above_100_rejected(self) -> None:
        with pytest.raises(PositionValidationError):
            validate_position_input(_valid_data(position_pct=101))

    def test_buy_reason_empty_rejected(self) -> None:
        with pytest.raises(PositionValidationError):
            validate_position_input(_valid_data(buy_reason="   "))

    def test_invalid_exchange_rejected(self) -> None:
        with pytest.raises(PositionValidationError):
            validate_position_input(_valid_data(exchange="HK"))

    def test_empty_stock_name_rejected(self) -> None:
        with pytest.raises(PositionValidationError):
            validate_position_input(_valid_data(stock_name=""))


class TestResolveSecurityInfo:
    def test_returns_none_when_no_data(self) -> None:
        result = resolve_security_info("000001")
        assert result["exchange"] is None
        assert result["stock_name"] is None
        assert result["resolution_issue"] is not None

    def test_uses_user_input(self) -> None:
        result = resolve_security_info("000001", exchange="SZ", stock_name="平安")
        assert result["exchange"] == "SZ"
        assert result["stock_name"] == "平安"

    def test_no_network_calls(self) -> None:
        """This test only verifies the function doesn't crash on missing data."""
        result = resolve_security_info("999999")
        assert isinstance(result, dict)
        assert "exchange" in result


class TestResolveSectorName:
    def test_user_input_takes_priority(self) -> None:
        result = resolve_sector_name("000001", sector_name="自定义板块")
        assert result["sector_name"] == "自定义板块"
        assert result["sector_issue"] is None

    def test_no_data_returns_issue(self) -> None:
        result = resolve_sector_name("000001")
        assert result["sector_issue"] is not None


class TestBuildEntrySnapshot:
    def test_builds_without_crashing(self) -> None:
        """Snapshot should handle partial data gracefully."""
        result = build_entry_snapshot(
            trade_date="2026-06-01",
            sector_name="银行",
            stock_code="000001",
        )
        assert "snapshot_json" in result
        assert "snapshot_version" in result
        # snapshot_json may be None if all modules fail, but the function must not raise
        assert result["snapshot_issue"] is not None or result["snapshot_json"] is not None

    def test_partial_module_failure_does_not_block(self) -> None:
        """Snapshot must not raise even if V1.6 modules are unavailable."""
        result = build_entry_snapshot(
            trade_date="2026-06-01",
            sector_name="",
            stock_code="000001",
        )
        assert isinstance(result, dict)


class TestParseSnapshotSafe:
    def test_parses_valid_json(self) -> None:
        data = {"key": "value", "nested": {"a": 1}}
        result = parse_snapshot_safe(json.dumps(data))
        assert result == data

    def test_empty_string(self) -> None:
        assert parse_snapshot_safe("") == {}

    def test_none_input(self) -> None:
        assert parse_snapshot_safe(None) == {}

    def test_corrupted_json(self) -> None:
        result = parse_snapshot_safe("{bad json")
        assert "parse_error" in result
