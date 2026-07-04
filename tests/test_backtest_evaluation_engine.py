import pandas as pd

from src.backtest_evaluation.evaluation_engine import run_backtest_evaluation
from src.storage.duckdb_repo import get_connection, query_df


def _insert_backtest_series(backtest_name: str) -> None:
    con = get_connection()
    con.execute(
        """
        INSERT INTO backtest_equity_curve
            (backtest_name, trade_date, initial_cash, portfolio_return, equity, universe_name)
        VALUES
            (?, DATE '2026-01-02', 1000000, 0.0000, 1000000, 'core_500'),
            (?, DATE '2026-01-05', 1000000, 0.0100, 1010000, 'core_500'),
            (?, DATE '2026-02-02', 1000000, -0.0050, 1004950, 'core_500'),
            (?, DATE '2026-02-03', 1000000, 0.0200, 1025049, 'core_500')
        """,
        [backtest_name, backtest_name, backtest_name, backtest_name],
    )
    con.execute(
        """
        INSERT INTO backtest_daily_return
            (backtest_name, trade_date, portfolio_return, holding_count, universe_name)
        VALUES
            (?, DATE '2026-01-02', 0.0000, 20, 'core_500'),
            (?, DATE '2026-01-05', 0.0100, 20, 'core_500'),
            (?, DATE '2026-02-02', -0.0050, 20, 'core_500'),
            (?, DATE '2026-02-03', 0.0200, 20, 'core_500')
        """,
        [backtest_name, backtest_name, backtest_name, backtest_name],
    )


class TestBacktestEvaluationEngine:
    def test_real_evaluation_writes_all_v12_tables_idempotently(self, fresh_db) -> None:  # noqa: F811
        backtest_name = "eval_engine_test"
        _insert_backtest_series(backtest_name)

        before_eq = query_df("SELECT COUNT(*) AS c FROM backtest_equity_curve").iloc[0]["c"]
        before_ret = query_df("SELECT COUNT(*) AS c FROM backtest_daily_return").iloc[0]["c"]

        first = run_backtest_evaluation(backtest_name, risk_free_rate=0.02)
        second = run_backtest_evaluation(backtest_name, risk_free_rate=0.02)

        assert first["status"] == "success"
        assert second["status"] == "success"

        summary = query_df(
            "SELECT * FROM backtest_performance_summary WHERE backtest_name = ?",
            [backtest_name],
        )
        drawdown = query_df(
            "SELECT * FROM backtest_drawdown_series WHERE backtest_name = ?",
            [backtest_name],
        )
        monthly = query_df(
            "SELECT * FROM backtest_monthly_return WHERE backtest_name = ?",
            [backtest_name],
        )
        yearly = query_df(
            "SELECT * FROM backtest_yearly_return WHERE backtest_name = ?",
            [backtest_name],
        )

        assert len(summary) == 1
        assert len(drawdown) == 4
        assert len(monthly) == 2
        assert len(yearly) == 1
        assert monthly["year_month"].notna().all()
        assert yearly["year"].notna().all()
        assert set(monthly["year_month"]) == {"2026-01", "2026-02"}
        assert set(yearly["year"]) == {"2026"}

        after_eq = query_df("SELECT COUNT(*) AS c FROM backtest_equity_curve").iloc[0]["c"]
        after_ret = query_df("SELECT COUNT(*) AS c FROM backtest_daily_return").iloc[0]["c"]
        assert after_eq == before_eq
        assert after_ret == before_ret

    def test_monthly_yearly_period_key_mapping(self) -> None:
        from src.backtest_evaluation.evaluation_engine import (
            _prepare_monthly_return_df,
            _prepare_yearly_return_df,
        )

        monthly = _prepare_monthly_return_df(
            pd.DataFrame({"period_key": ["2026-01"], "period_return": [0.01], "backtest_name": ["bt"]})
        )
        yearly = _prepare_yearly_return_df(
            pd.DataFrame({"period_key": ["2026"], "period_return": [0.02], "backtest_name": ["bt"]})
        )

        assert monthly.loc[0, "year_month"] == "2026-01"
        assert monthly.loc[0, "monthly_return"] == 0.01
        assert yearly.loc[0, "year"] == "2026"
        assert yearly.loc[0, "yearly_return"] == 0.02
