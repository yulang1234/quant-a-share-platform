"""Tests for src/strategy/strategy_config.py"""
import pytest
from src.strategy.strategy_config import get_default_strategy, list_default_strategies, validate_strategy_config


class TestConfig:
    def test_defaults_exist(self) -> None:
        assert len(list_default_strategies()) >= 4

    def test_get_known(self) -> None:
        cfg = get_default_strategy("single_return_20d_top20")
        assert cfg is not None
        assert cfg["strategy_type"] == "single_factor"

    def test_validate_invalid_type(self) -> None:
        with pytest.raises(ValueError, match="strategy_type"):
            validate_strategy_config({"strategy_name": "x", "strategy_type": "invalid", "top_k": 10})

    def test_validate_missing_factor_name(self) -> None:
        with pytest.raises(ValueError, match="factor_name"):
            validate_strategy_config({"strategy_name": "x", "strategy_type": "single_factor", "top_k": 10})

    def test_validate_missing_weights(self) -> None:
        with pytest.raises(ValueError, match="factor_weights"):
            validate_strategy_config({"strategy_name": "x", "strategy_type": "multi_factor", "top_k": 10})

    def test_validate_top_k_zero(self) -> None:
        with pytest.raises(ValueError, match="top_k"):
            validate_strategy_config({"strategy_name": "x", "strategy_type": "single_factor", "factor_name": "ret", "top_k": 0})
