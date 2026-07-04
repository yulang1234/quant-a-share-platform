"""Tests for src/factor_rank/run_factor_ranking.py"""
from src.factor_rank.run_factor_ranking import main


class TestRunFactorRankingCLI:
    def test_limit_1(self) -> None:
        rc = main(["--pool", "core_500", "--limit", "1"])
        assert rc == 0

    def test_factor_name(self) -> None:
        rc = main(["--factor-name", "return_20d", "--limit", "1"])
        assert rc == 0

    def test_trade_date(self) -> None:
        rc = main(["--trade-date", "20260703", "--limit", "1"])
        assert rc == 0
