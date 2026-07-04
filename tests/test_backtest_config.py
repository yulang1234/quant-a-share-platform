import pytest
from src.backtest.backtest_config import create_default_backtest_config, validate_backtest_config


class TestConfig:
    def test_default(self) -> None:
        c = create_default_backtest_config("test")
        assert c["initial_cash"] == 1_000_000

    def test_invalid_frequency(self) -> None:
        with pytest.raises(ValueError):
            validate_backtest_config({"backtest_name": "x", "strategy_name": "y", "initial_cash": 100, "top_k": 5, "rebalance_frequency": "yearly"})

    def test_invalid_cash(self) -> None:
        with pytest.raises(ValueError):
            validate_backtest_config({"backtest_name": "x", "strategy_name": "y", "initial_cash": 0, "top_k": 5, "rebalance_frequency": "monthly"})
