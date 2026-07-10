"""Test portfolio_position_view — data helpers (no streamlit dependency)."""

import json

import pandas as pd
import pytest

from ui.components.portfolio_position_view import (
    position_csv_bytes,
    position_detail_markdown_bytes,
    position_markdown_bytes,
    position_mode_to_cn,
    position_status_to_cn,
    positions_to_df,
)


def _sample_positions():
    return [
        {
            "position_id": 1,
            "portfolio_name": "default",
            "stock_code": "000001",
            "exchange": "SZ",
            "stock_name": "平安银行",
            "buy_date": "2026-06-01",
            "avg_cost": 12.50,
            "quantity": 1000,
            "position_pct": 10.0,
            "buy_reason": "测试",
            "sector_name": "银行",
            "original_strategy": "manual",
            "user_note": None,
            "is_simulated": False,
            "status": "active",
            "entry_snapshot_json": None,
            "snapshot_version": None,
            "created_at": "2026-06-01T10:00:00",
            "updated_at": "2026-06-01T10:00:00",
        },
        {
            "position_id": 2,
            "portfolio_name": "default",
            "stock_code": "600519",
            "exchange": "SH",
            "stock_name": "贵州茅台",
            "buy_date": "2026-05-15",
            "avg_cost": 1800.00,
            "quantity": None,
            "position_pct": 20.0,
            "buy_reason": "核心资产配置",
            "sector_name": "白酒",
            "original_strategy": None,
            "user_note": "长期持有",
            "is_simulated": True,
            "status": "active",
            "entry_snapshot_json": json.dumps({"version": "v1.6.3"}),
            "snapshot_version": "v1.6.3",
            "created_at": "2026-05-15T10:00:00",
            "updated_at": "2026-05-15T10:00:00",
        },
    ]


class TestPositionsToDf:
    def test_converts_to_dataframe(self) -> None:
        df = positions_to_df(_sample_positions())
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_empty_list_returns_empty_df(self) -> None:
        df = positions_to_df([])
        assert df.empty

    def test_none_returns_empty_df(self) -> None:
        df = positions_to_df(None)
        assert df.empty

    def test_columns_exist(self) -> None:
        df = positions_to_df(_sample_positions())
        expected_cols = [
            "position_id", "portfolio_name", "持仓类型", "stock_code",
            "stock_name", "exchange", "buy_date", "avg_cost", "quantity",
            "position_pct", "sector_name", "original_strategy", "status",
            "has_snapshot", "updated_at",
        ]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_mode_cn_mapping(self) -> None:
        df = positions_to_df(_sample_positions())
        assert df.loc[0, "持仓类型"] == "真实"
        assert df.loc[1, "持仓类型"] == "模拟"

    def test_status_cn_mapping(self) -> None:
        df = positions_to_df(_sample_positions())
        assert df.loc[0, "status"] == "活跃"

    def test_snapshot_indicator(self) -> None:
        df = positions_to_df(_sample_positions())
        assert df.loc[0, "has_snapshot"] == "无快照"
        assert df.loc[1, "has_snapshot"] == "有快照"


class TestCsvBytes:
    def test_generates_csv(self) -> None:
        data = position_csv_bytes(_sample_positions())
        assert data.startswith(b"\xef\xbb\xbf")  # utf-8 BOM
        assert b"stock_code" in data

    def test_empty_list_csv(self) -> None:
        data = position_csv_bytes([])
        assert len(data) >= 0  # should not crash

    def test_none_csv(self) -> None:
        data = position_csv_bytes(None)
        assert data is not None


class TestMarkdownBytes:
    def test_generates_markdown(self) -> None:
        data = position_markdown_bytes(_sample_positions())
        assert "# \u6301\u4ed3\u8bb0\u5f55".encode("utf-8") in data

    def test_empty_list_markdown(self) -> None:
        data = position_markdown_bytes([])
        assert "# \u6301\u4ed3\u8bb0\u5f55".encode("utf-8") in data

    def test_detail_markdown(self) -> None:
        data = position_detail_markdown_bytes(_sample_positions()[0])
        assert "# \u6301\u4ed3\u8be6\u60c5".encode("utf-8") in data

    def test_none_detail(self) -> None:
        data = position_detail_markdown_bytes(None)
        assert data == b""


class TestCnMapping:
    def test_position_mode_to_cn(self) -> None:
        assert position_mode_to_cn(True) == "模拟"
        assert position_mode_to_cn(False) == "真实"

    def test_position_status_to_cn(self) -> None:
        assert position_status_to_cn("active") == "活跃"
        assert position_status_to_cn("closed") == "已关闭"
