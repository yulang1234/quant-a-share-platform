"""
Backtesting engine — simulate trading a strategy over historical data.

V0.1: skeleton only.
"""

from __future__ import annotations


class BacktestEngine:
    """Core loop: for each trading day, execute the strategy and record results.

    TODO(V1.1): implement event loop, portfolio state tracking, trade recording.
    """

    def run(self) -> None:
        """Run the backtest end-to-end."""
        raise NotImplementedError("BacktestEngine is a V1.1 feature.")
