"""Test position_report — Markdown generation with edge cases."""

import json

from src.portfolio.position_report import (
    build_position_detail_markdown,
    build_position_list_markdown,
)

DISCLAIMER = "不构成投资建议"


def _sample_position(**overrides):
    d = {
        "position_id": 1,
        "portfolio_name": "default",
        "stock_code": "000001",
        "exchange": "SZ",
        "stock_name": "平安银行",
        "buy_date": "2026-06-01",
        "avg_cost": 12.50,
        "quantity": 1000,
        "position_pct": 10.0,
        "buy_reason": "测试买入理由",
        "sector_name": "银行",
        "original_strategy": "manual",
        "user_note": "备注",
        "is_simulated": False,
        "status": "active",
        "created_at": "2026-06-01T10:00:00",
        "updated_at": "2026-06-01T10:00:00",
    }
    d.update(overrides)
    return d


class TestPositionListMarkdown:
    def test_generates_for_active_positions(self) -> None:
        positions = [_sample_position(), _sample_position(position_id=2, stock_code="600519")]
        md = build_position_list_markdown(positions)
        assert "持仓记录" in md
        assert "活跃持仓" in md
        assert "000001" in md
        assert "600519" in md

    def test_generates_for_closed_positions(self) -> None:
        positions = [_sample_position(status="closed", closed_at="2026-07-01")]
        md = build_position_list_markdown(positions)
        assert "已关闭持仓" in md

    def test_empty_positions(self) -> None:
        md = build_position_list_markdown([])
        assert "暂无活跃持仓" in md
        assert "暂无已关闭持仓" in md

    def test_includes_summary_when_provided(self) -> None:
        summary = {"active_count": 5, "closed_count": 2, "real_count": 3, "simulated_count": 2, "total_position_pct": 80.0, "position_pct_ok": True}
        md = build_position_list_markdown([_sample_position()], summary)
        assert "活跃持仓数量: 5" in md
        assert "已填写仓位合计: 80.0%" in md

    def test_includes_disclaimer(self) -> None:
        md = build_position_list_markdown([_sample_position()])
        assert "免责声明" in md
        assert DISCLAIMER in md

    def test_no_trading_advice(self) -> None:
        """Report must not contain buy/sell signals."""
        md = build_position_list_markdown([_sample_position()])
        for forbidden in ["买入", "卖出", "减仓", "加仓", "清仓", "止盈", "止损"]:
            assert forbidden not in md.split("## 4")[-1], f"Found '{forbidden}' in report"


class TestPositionDetailMarkdown:
    def test_generates_detail(self) -> None:
        md = build_position_detail_markdown(_sample_position())
        assert "持仓详情" in md
        assert "000001" in md
        assert "平安银行" in md

    def test_shows_missing_data_placeholder(self) -> None:
        pos = _sample_position(sector_name=None, user_note=None, quantity=None)
        md = build_position_detail_markdown(pos)
        assert "暂无数据" in md
        assert "未填写" in md

    def test_corrupted_snapshot_does_not_crash(self) -> None:
        pos = _sample_position(entry_snapshot_json="{corrupted")
        md = build_position_detail_markdown(pos)
        assert "持仓详情" in md  # must still render basic info

    def test_valid_snapshot_displays(self) -> None:
        snap = json.dumps({
            "version": "v1.6.3",
            "trade_date": "2026-06-01",
            "market_environment": {"market_state": "attack"},
            "sentiment_cycle": {"sentiment_cycle": "warming"},
        }, ensure_ascii=False)
        pos = _sample_position(entry_snapshot_json=snap, snapshot_version="v1.6.3")
        md = build_position_detail_markdown(pos)
        assert "v1.6.3" in md
        assert "attack" in md

    def test_includes_disclaimer(self) -> None:
        md = build_position_detail_markdown(_sample_position())
        assert DISCLAIMER in md

    def test_no_trading_advice(self) -> None:
        md = build_position_detail_markdown(_sample_position())
        for forbidden in ["买入", "卖出", "减仓", "加仓", "清仓", "止盈", "止损"]:
            assert forbidden not in md.split("## 9")[-1], f"Found '{forbidden}' in report"
