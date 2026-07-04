import pandas as pd
from src.scoring.score_calculator import calculate_composite_scores


class TestCalculator:
    def test_percentile_rank_mode(self) -> None:
        rank = pd.DataFrame({"stock_code": ["000001", "000001", "000002", "000002"], "trade_date": pd.to_datetime(["2026-01-02"] * 4), "factor_name": ["ret20", "mom20", "ret20", "mom20"], "percentile_rank": [0.8, 0.6, 0.4, 0.2]})
        comp, det = calculate_composite_scores(rank, "test", {"ret20": 0.5, "mom20": 0.5})
        assert not comp.empty
        assert comp["score_rank"].iloc[0] == 1

    def test_direction_value_mode(self) -> None:
        rank = pd.DataFrame({"stock_code": ["000001", "000002"], "trade_date": ["2026-01-02"] * 2, "factor_name": ["ret20"] * 2, "direction_value": [0.8, 0.4], "percentile_rank": [0.8, 0.4]})
        comp, det = calculate_composite_scores(rank, "test", {"ret20": 1.0}, "direction_value_weighted_sum")
        assert not comp.empty

    def test_no_cross_date(self) -> None:
        rank = pd.DataFrame({"stock_code": ["000001", "000001"], "trade_date": pd.to_datetime(["2026-01-02", "2026-01-03"]), "factor_name": ["ret20", "ret20"], "percentile_rank": [0.8, 0.8]})
        comp, _ = calculate_composite_scores(rank, "test", {"ret20": 1.0})
        assert (comp["score_rank"] == 1).all()

    def test_coverage_counts(self) -> None:
        rank = pd.DataFrame({"stock_code": ["000001"], "trade_date": ["2026-01-02"], "factor_name": ["ret20"], "percentile_rank": [0.8]})
        comp, _ = calculate_composite_scores(rank, "test", {"ret20": 0.5, "mom20": 0.5})
        assert comp["missing_factor_count"].iloc[0] == 1
