"""Tests for src/factors/run_factor_calculation.py"""
from src.factors.run_factor_calculation import main


class TestRunFactorCalcCLI:
    def test_limit_1(self) -> None:
        rc = main(["--pool", "core_500", "--limit", "1"])
        assert rc == 0

    def test_single_stock(self) -> None:
        rc = main(["--stock-code", "000001"])
        assert rc == 0

    def test_date_range(self) -> None:
        rc = main(["--stock-code", "000001", "--start-date", "20200101", "--end-date", "20231231"])
        assert rc == 0

    def test_no_qfq_data_skipped(self) -> None:
        rc = main(["--stock-code", "999999"])
        assert rc == 0
