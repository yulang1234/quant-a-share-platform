"""Tests for src/strategy/run_topk_strategy.py"""
from src.strategy.run_topk_strategy import main


class TestCLI:
    def test_default_strategy(self) -> None:
        rc = main(["--strategy", "single_return_20d_top20", "--limit", "1"])
        assert rc == 0

    def test_adhoc_single(self) -> None:
        rc = main(["--factor-name", "return_20d", "--top-k", "5", "--limit", "1"])
        assert rc == 0

    def test_no_args_error(self) -> None:
        rc = main([])
        assert rc == 1

    def test_adhoc_multi(self) -> None:
        rc = main(["--factor-weights", '{"return_20d":0.5,"momentum_20d":0.5}', "--top-k", "5", "--limit", "1"])
        assert rc == 0
