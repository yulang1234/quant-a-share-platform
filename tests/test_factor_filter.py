from src.scoring.factor_filter import filter_factors_by_analysis


class TestFilter:
    def test_no_summary_returns_all(self) -> None:
        r = filter_factors_by_analysis(["a", "b"])
        assert r == ["a", "b"]
