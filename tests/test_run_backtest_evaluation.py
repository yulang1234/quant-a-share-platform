from src.backtest_evaluation.run_backtest_evaluation import main
from src.storage.duckdb_repo import get_connection, query_df


def _seed_cli_backtest(backtest_name: str) -> None:
    con = get_connection()
    con.execute(
        """
        INSERT INTO backtest_equity_curve
            (backtest_name, trade_date, initial_cash, portfolio_return, equity, universe_name)
        VALUES
            (?, DATE '2026-03-02', 1000000, 0.0000, 1000000, 'core_500'),
            (?, DATE '2026-03-03', 1000000, 0.0100, 1010000, 'core_500'),
            (?, DATE '2026-03-04', 1000000, 0.0050, 1015050, 'core_500')
        """,
        [backtest_name, backtest_name, backtest_name],
    )
    con.execute(
        """
        INSERT INTO backtest_daily_return
            (backtest_name, trade_date, portfolio_return, holding_count, universe_name)
        VALUES
            (?, DATE '2026-03-02', 0.0000, 20, 'core_500'),
            (?, DATE '2026-03-03', 0.0100, 20, 'core_500'),
            (?, DATE '2026-03-04', 0.0050, 20, 'core_500')
        """,
        [backtest_name, backtest_name, backtest_name],
    )


class TestRunBacktestEvaluationCli:
    def test_cli_with_data_writes_evaluation_tables(self, fresh_db, capsys) -> None:  # noqa: F811
        backtest_name = "cli_eval_test"
        _seed_cli_backtest(backtest_name)

        rc = main(["--backtest-name", backtest_name])
        out = capsys.readouterr().out

        assert rc == 0
        assert "status: success" in out
        assert query_df("SELECT COUNT(*) AS c FROM backtest_performance_summary").iloc[0]["c"] == 1
        assert query_df("SELECT COUNT(*) AS c FROM backtest_drawdown_series").iloc[0]["c"] == 3
        assert query_df("SELECT COUNT(*) AS c FROM backtest_monthly_return").iloc[0]["c"] == 1
        assert query_df("SELECT COUNT(*) AS c FROM backtest_yearly_return").iloc[0]["c"] == 1
