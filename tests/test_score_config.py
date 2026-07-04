import pytest
from src.scoring.score_config import get_default_score_model, list_default_score_models, normalize_factor_weights, validate_score_model_config


class TestConfig:
    def test_defaults_exist(self) -> None: assert len(list_default_score_models()) >= 3
    def test_get_known(self) -> None: assert get_default_score_model("momentum_quality_score") is not None
    def test_invalid_method(self) -> None:
        with pytest.raises(ValueError): validate_score_model_config({"model_name": "x", "factor_weights": {"a": 1}, "score_method": "invalid"})
    def test_empty_weights(self) -> None:
        with pytest.raises(ValueError): validate_score_model_config({"model_name": "x", "factor_weights": {}})
    def test_zero_sum_weights(self) -> None:
        with pytest.raises(ValueError, match="must be > 0"): validate_score_model_config({"model_name": "x", "factor_weights": {"a": 0}})
        with pytest.raises(ValueError, match="must be > 0"): validate_score_model_config({"model_name": "x", "factor_weights": {"a": 0, "b": 0}})
    def test_normalize(self) -> None:
        r = normalize_factor_weights({"a": 1, "b": 1}); assert r == {"a": 0.5, "b": 0.5}
    def test_normalize_zero_sum(self) -> None:
        with pytest.raises(ValueError): normalize_factor_weights({"a": 0})
    def test_negative_weight(self) -> None:
        with pytest.raises(ValueError): normalize_factor_weights({"a": -1})
    def test_no_modify_input(self) -> None:
        inp = {"a": 2, "b": 2}; normalize_factor_weights(inp); assert inp == {"a": 2, "b": 2}
