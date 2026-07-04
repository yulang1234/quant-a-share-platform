"""Tests for src/data_repair/repair_planner.py"""

from __future__ import annotations

import pandas as pd
import pytest

from src.data_repair.repair_planner import (
    build_repair_plan,
    infer_repair_range,
    load_quality_reports,
)


class TestLoadQualityReports:
    def test_empty_when_no_table(self, fresh_db) -> None:  # noqa: F811
        df = load_quality_reports()
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_stock_code_6_digit(self) -> None:
        df = load_quality_reports(stock_code="000001")
        assert isinstance(df, pd.DataFrame)


class TestBuildRepairPlan:
    def test_empty_plan_when_no_reports(self, fresh_db) -> None:  # noqa: F811
        plan = build_repair_plan(limit=5)
        assert plan.empty
        assert "stock_code" in plan.columns
        assert "repair_action" in plan.columns

    def test_invalid_adj_raises(self, fresh_db) -> None:  # noqa: F811
        with pytest.raises(ValueError, match="adj must be"):
            build_repair_plan(adj="invalid")

    def test_plan_columns(self, fresh_db) -> None:  # noqa: F811
        plan = build_repair_plan()
        expected = {"stock_code", "pool_name", "adj_type", "issue_type",
                    "repair_action", "start_date", "end_date", "reason"}
        assert expected.issubset(set(plan.columns))


class TestInferRepairRange:
    def test_from_check_date(self) -> None:
        row = pd.Series({"check_date": "2026-07-01"})
        s, e = infer_repair_range(row)
        assert s is not None
        assert e is not None

    def test_from_explicit_range(self) -> None:
        row = pd.Series({"start_date": "2026-01-01", "end_date": "2026-06-30"})
        s, e = infer_repair_range(row)
        assert s == "2026-01-01"
        assert e == "2026-06-30"

    def test_empty_row_returns_none(self) -> None:
        row = pd.Series({})
        s, e = infer_repair_range(row)
        assert s is None
        assert e is None
