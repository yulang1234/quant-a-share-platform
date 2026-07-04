import pandas as pd
import numpy as np
from src.backtest_evaluation.performance_metrics import calculate_total_return, calculate_sharpe_ratio, calculate_win_rate


class TestMetrics:
    def test_total_return(self) -> None:
        df = pd.DataFrame({"trade_date": ["2026-01-02", "2026-01-03"], "equity": [1000000, 1010000]})
        assert abs(calculate_total_return(df) - 0.01) < 0.001

    def test_sharpe_nan_on_zero_vol(self) -> None:
        df = pd.DataFrame({"portfolio_return": [0.01, 0.01]})
        assert np.isnan(calculate_sharpe_ratio(df))

    def test_win_rate(self) -> None:
        df = pd.DataFrame({"portfolio_return": [0.01, -0.01, 0.02]})
        assert calculate_win_rate(df) == 2 / 3

    def test_empty(self) -> None:
        assert np.isnan(calculate_total_return(pd.DataFrame()))
