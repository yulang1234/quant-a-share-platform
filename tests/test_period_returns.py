import pandas as pd
import pytest
from src.backtest_evaluation.period_returns import calculate_period_returns


class TestPeriodReturns:
    def test_monthly(self) -> None:
        df = pd.DataFrame({"trade_date": pd.to_datetime(["2026-01-02", "2026-01-15", "2026-02-01", "2026-02-15"]), "equity": [100, 110, 110, 121]})
        r = calculate_period_returns(df, "monthly")
        assert len(r) == 2

    def test_yearly(self) -> None:
        df = pd.DataFrame({"trade_date": pd.to_datetime(["2026-01-02", "2026-12-15"]), "equity": [100, 120]})
        r = calculate_period_returns(df, "yearly")
        assert len(r) == 1

    def test_invalid_period(self) -> None:
        with pytest.raises(ValueError):
            calculate_period_returns(pd.DataFrame(), "quarterly")
