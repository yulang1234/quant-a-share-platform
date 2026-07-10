"""Test position_diagnosis_report — Markdown generation."""

import json

from src.portfolio.position_diagnosis_report import (
    build_daily_position_diagnosis_markdown,
    build_position_diagnosis_markdown,
)

DISCLAIMER = "不构成投资建议"


def _result(**overrides):
    d = {
        "position_id": 1,
        "trade_date": "2026-07-01",
        "portfolio_name": "default",
        "stock_code": "000001",
        "stock_name": "平安银行",
        "sector_name": "银行",
        "diagnosis_status": "healthy",
        "suggested_action": "continue_hold",
        "thesis_status": "valid",
        "health_score": 85.0,
        "data_coverage_ratio": 0.9,
        "market_support_score": 80.0,
        "sentiment_support_score": 75.0,
        "sector_support_score": 90.0,
        "leader_support_score": 85.0,
        "trend_health_score": 88.0,
        "condition_support_score": 80.0,
        "thesis_score": 80.0,
        "unrealized_return_pct": 5.23,
        "latest_close": 13.15,
        "drawdown_20d": 3.5,
        "position_pct": 10.0,
        "position_size_status": "normal",
        "risk_warnings": ["market is heating"],
        "observation_conditions": ["wait for sentiment repair"],
        "invalidation_conditions": ["leader score drops"],
        "data_quality_status": "ok",
        "issue_summary": [],
    }
    d.update(overrides)
    return d


class TestSingleDiagnosisReport:
    def test_healthy_report(self) -> None:
        md = build_position_diagnosis_markdown(_result())
        assert "持仓体检报告" in md
        assert "平安银行" in md
        assert DISCLAIMER in md

    def test_shows_scores(self) -> None:
        md = build_position_diagnosis_markdown(_result())
        assert "85" in md
        assert "5.23" in md

    def test_empty_result_does_not_crash(self) -> None:
        md = build_position_diagnosis_markdown({})
        assert "持仓体检报告" in md

    def test_missing_data(self) -> None:
        md = build_position_diagnosis_markdown(_result(
            unrealized_return_pct=None, latest_close=None, sector_name=None,
        ))
        assert "暂无数据" in md or "N/A" in md

    def test_no_trading_commands(self) -> None:
        md = build_position_diagnosis_markdown(_result())
        for forbidden in ["立即卖出", "立即买入", "必须清仓", "满仓", "梭哈", "稳赚"]:
            assert forbidden not in md, f"Found '{forbidden}' in report"

    def test_includes_disclaimer(self) -> None:
        md = build_position_diagnosis_markdown({})
        assert DISCLAIMER in md


class TestDailyDiagnosisReport:
    def test_generates_summary(self) -> None:
        results = [
            _result(position_id=1, suggested_action="continue_hold"),
            _result(position_id=2, stock_code="600519", suggested_action="light_hold", health_score=65),
            _result(position_id=3, stock_code="000002", suggested_action="exit_conditionally", diagnosis_status="dangerous", health_score=20),
        ]
        md = build_daily_position_diagnosis_markdown(results)
        assert "每日持仓体检汇总" in md
        assert "继续持有" in md
        assert "触发清仓条件" in md
        assert DISCLAIMER in md

    def test_empty_results(self) -> None:
        md = build_daily_position_diagnosis_markdown([])
        assert "每日持仓体检汇总" in md

    def test_with_summary(self) -> None:
        results = [_result()]
        summary = {"total": 1, "healthy": 1}
        md = build_daily_position_diagnosis_markdown(results, summary)
        assert "健康: 1" in md

    def test_no_trading_commands(self) -> None:
        md = build_daily_position_diagnosis_markdown([_result()])
        for forbidden in ["立即卖出", "立即买入", "必须清仓", "满仓", "梭哈"]:
            assert forbidden not in md.split("## 9")[-1]
