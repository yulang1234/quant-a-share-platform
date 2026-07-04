import pandas as pd
import numpy as np
from src.backtest_evaluation.drawdown import calculate_max_drawdown, calculate_drawdown_series


class TestDrawdown:
    def test_basic(self) -> None:
        df = pd.DataFrame({"trade_date": ["2026-01-02", "2026-01-03", "2026-01-06"], "equity": [100, 90, 95]})
        r = calculate_drawdown_series(df)
        assert abs(r["drawdown"].min() - -0.1) < 0.001

    def test_max_dd(self) -> None:
        df = pd.DataFrame({"trade_date": ["2026-01-02", "2026-01-03"], "equity": [100, 80]})
        assert abs(calculate_max_drawdown(df) - -0.2) < 0.001

    def test_empty(self) -> None:
        assert np.isnan(calculate_max_drawdown(pd.DataFrame()))
