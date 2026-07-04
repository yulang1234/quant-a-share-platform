import pandas as pd
from src.backtest.return_calculator import calculate_portfolio_daily_returns, calculate_stock_returns


class TestReturns:
    def test_stock_return(self) -> None:
        df = pd.DataFrame({"stock_code": ["000001"] * 3, "trade_date": pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-06"]), "close": [100, 101, 102]})
        r = calculate_stock_returns(df)
        assert abs(r["stock_return"].iloc[1] - 0.01) < 0.001

    def test_portfolio_return(self) -> None:
        pos = pd.DataFrame({"trade_date": ["2026-01-03"], "stock_code": ["000001"], "weight": [1.0]})
        ret = pd.DataFrame({"stock_code": ["000001"], "trade_date": ["2026-01-03"], "stock_return": [0.01]})
        r = calculate_portfolio_daily_returns(pos, ret)
        assert r["portfolio_return"].iloc[0] == 0.01
