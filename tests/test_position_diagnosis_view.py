"""Test position_diagnosis_view — data helpers (no streamlit dependency)."""

import pandas as pd

from ui.components.position_diagnosis_view import (
    daily_diagnosis_markdown_bytes,
    diagnoses_to_df,
    diagnosis_csv_bytes,
    diagnosis_markdown_bytes,
    diagnosis_status_to_cn,
    diagnosis_summary,
    position_size_status_to_cn,
    suggested_action_to_cn,
    thesis_status_to_cn,
)


def _results():
    return [
        {
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
            "latest_close": 13.15,
            "unrealized_return_pct": 5.23,
            "drawdown_20d": 3.5,
            "position_pct": 10.0,
            "position_size_status": "normal",
            "risk_warnings": [],
            "observation_conditions": [],
            "invalidation_conditions": [],
            "data_quality_status": "ok",
            "issue_summary": [],
        },
        {
            "position_id": 2,
            "trade_date": "2026-07-01",
            "portfolio_name": "default",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "sector_name": "白酒",
            "diagnosis_status": "dangerous",
            "suggested_action": "exit_conditionally",
            "thesis_status": "invalid",
            "health_score": 25.0,
            "data_coverage_ratio": 0.5,
            "market_support_score": 20.0,
            "sentiment_support_score": 20.0,
            "sector_support_score": 30.0,
            "leader_support_score": 20.0,
            "trend_health_score": 15.0,
            "condition_support_score": 20.0,
            "thesis_score": 10.0,
            "latest_close": None,
            "unrealized_return_pct": None,
            "drawdown_20d": None,
            "position_pct": None,
            "position_size_status": "unknown",
            "risk_warnings": [],
            "observation_conditions": [],
            "invalidation_conditions": [],
            "data_quality_status": "degraded",
            "issue_summary": [],
        },
    ]


class TestDiagnosesToDf:
    def test_converts(self) -> None:
        df = diagnoses_to_df(_results())
        assert len(df) == 2

    def test_empty(self) -> None:
        assert diagnoses_to_df([]).empty

    def test_none(self) -> None:
        assert diagnoses_to_df(None).empty

    def test_columns(self) -> None:
        df = diagnoses_to_df(_results())
        assert "diagnosis_status" in df.columns
        assert "suggested_action" in df.columns

    def test_status_cn(self) -> None:
        df = diagnoses_to_df(_results())
        assert df.loc[0, "diagnosis_status"] == "健康"


class TestCnMapping:
    def test_diagnosis_status(self) -> None:
        assert diagnosis_status_to_cn("healthy") == "健康"
        assert diagnosis_status_to_cn("dangerous") == "危险"

    def test_suggested_action(self) -> None:
        assert suggested_action_to_cn("continue_hold") == "继续持有"
        assert suggested_action_to_cn("exit_conditionally") == "触发清仓条件"

    def test_thesis_status(self) -> None:
        assert thesis_status_to_cn("valid") == "有效"
        assert thesis_status_to_cn("manual_review_required") == "需人工复核"

    def test_position_size(self) -> None:
        assert position_size_status_to_cn("normal") == "正常"
        assert position_size_status_to_cn("high") == "过重"


class TestSummary:
    def test_computes_summary(self) -> None:
        s = diagnosis_summary(_results())
        assert s["total"] == 2
        assert s["healthy"] == 1
        assert s["dangerous"] == 1
        assert s["action_exit_conditionally"] == 1

    def test_empty_summary(self) -> None:
        s = diagnosis_summary([])
        assert s["total"] == 0


class TestExport:
    def test_csv_bytes(self) -> None:
        data = diagnosis_csv_bytes(_results())
        assert data.startswith(b"\xef\xbb\xbf")
        assert b"stock_code" in data

    def test_markdown_bytes(self) -> None:
        data = diagnosis_markdown_bytes(_results()[0])
        assert b"# " in data

    def test_daily_md_bytes(self) -> None:
        data = daily_diagnosis_markdown_bytes(_results())
        assert b"# " in data

    def test_empty_csv(self) -> None:
        data = diagnosis_csv_bytes([])
        assert len(data) >= 0

    def test_none_markdown(self) -> None:
        data = diagnosis_markdown_bytes(None)
        assert data == b""
