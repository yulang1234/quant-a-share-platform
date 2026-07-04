"""Tests for src/factor_rank/factor_config.py"""
from src.factor_rank.factor_config import get_factor_config, get_factor_direction, list_supported_factors


class TestFactorConfig:
    def test_positive_factor(self) -> None:
        assert get_factor_direction("return_20d") == "positive"

    def test_negative_factor(self) -> None:
        assert get_factor_direction("volatility_20d") == "negative"

    def test_neutral_factor(self) -> None:
        assert get_factor_direction("ma20") == "neutral"

    def test_unknown_factor_defaults_neutral(self) -> None:
        assert get_factor_direction("unknown_factor_xyz") == "neutral"

    def test_list_non_empty(self) -> None:
        factors = list_supported_factors()
        assert len(factors) >= 40
        assert "return_20d" in factors

    def test_get_config_returns_dict(self) -> None:
        cfg = get_factor_config("return_20d")
        assert cfg["direction"] == "positive"
        assert "category" in cfg
