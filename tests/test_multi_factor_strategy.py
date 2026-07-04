"""Tests for src/strategy/multi_factor_strategy.py"""
import pytest
import pandas as pd
from src.strategy.multi_factor_strategy import normalize_factor_weights, calculate_composite_scores


class TestNormalize:
    def test_normalizes(self) -> None:
        r = normalize_factor_weights({"a": 1, "b": 1})
        assert r == {"a": 0.5, "b": 0.5}

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="zero"):
            normalize_factor_weights({"a": 0})

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="Negative"):
            normalize_factor_weights({"a": -1})


class TestCompositeScores:
    def test_basic(self) -> None:
        rank = pd.DataFrame({
            "stock_code": ["000001", "000001", "000002", "000002"],
            "trade_date": pd.to_datetime(["2026-01-02"] * 4),
            "factor_name": ["ret20", "mom20", "ret20", "mom20"],
            "percentile_rank": [0.8, 0.6, 0.4, 0.2],
        })
        sel, det = calculate_composite_scores(rank, {"ret20": 0.5, "mom20": 0.5})
        assert not sel.empty
        assert "composite_score" in sel.columns
        assert len(det) == 4

    def test_missing_factor_skipped(self) -> None:
        rank = pd.DataFrame({
            "stock_code": ["000001"], "trade_date": ["2026-01-02"],
            "factor_name": ["ret20"], "percentile_rank": [0.8],
        })
        sel, det = calculate_composite_scores(rank, {"ret20": 0.5, "missing": 0.5})
        assert len(det) == 1
