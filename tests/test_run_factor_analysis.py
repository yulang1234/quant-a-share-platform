"""Tests for src/factor_analysis/run_factor_analysis.py"""
from src.factor_analysis.run_factor_analysis import main


class TestRunFactorAnalysisCLI:
    def test_limit_1(self) -> None:
        rc = main(["--pool", "core_500", "--limit", "1"])
        assert rc == 0

    def test_factor_name(self) -> None:
        rc = main(["--factor-name", "return_20d", "--forward-days", "5", "--limit", "1"])
        assert rc == 0
