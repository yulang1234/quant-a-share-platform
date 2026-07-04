import pandas as pd
from src.backtest.equity_curve import calculate_equity_curve


class TestEquity:
    def test_basic(self) -> None:
        df = pd.DataFrame({"trade_date": pd.to_datetime(["2026-01-02", "2026-01-03"]), "portfolio_return": [0.01, 0.02]})
        r = calculate_equity_curve(df, 1000000)
        assert r["equity"].iloc[0] == 1010000
        assert abs(r["equity"].iloc[1] - 1030200) < 1
