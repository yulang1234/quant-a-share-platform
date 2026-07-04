"""Tests for src/strategy/single_factor_strategy.py"""
import pandas as pd
from src.strategy.single_factor_strategy import select_topk_single_factor


class TestSingleFactor:
    def test_basic(self) -> None:
        rank = pd.DataFrame({
            "stock_code": ["000001", "000002", "000003", "000004", "000005"],
            "trade_date": pd.to_datetime(["2026-01-02"] * 5),
            "factor_name": ["ret20"] * 5,
            "percentile_rank": [0.1, 0.5, 0.9, 0.3, 0.7],
        })
        r = select_topk_single_factor(rank, "ret20", top_k=3)
        assert len(r) == 3
        assert r["rank_in_strategy"].iloc[0] == 1

    def test_top_k_limits(self) -> None:
        rank = pd.DataFrame({
            "stock_code": [f"{i:06d}" for i in range(1, 51)],
            "trade_date": ["2026-01-02"] * 50,
            "factor_name": ["ret20"] * 50,
            "percentile_rank": [i / 50 for i in range(50)],
        })
        r = select_topk_single_factor(rank, "ret20", top_k=10)
        assert len(r) == 10

    def test_empty(self) -> None:
        r = select_topk_single_factor(pd.DataFrame(), "x")
        assert r.empty
