"""
Performance metrics — evaluate backtest results.

Metrics include: total return, annualised return, Sharpe ratio, max drawdown,
win rate, and turnover.

V0.1: skeleton only.
"""

from __future__ import annotations


def compute_total_return(nav_series: list[float]) -> float:
    """``(final_nav / initial_nav) - 1``.

    TODO(V1.2): implement.
    """
    raise NotImplementedError("Metrics are a V1.2 feature.")


def compute_sharpe_ratio(daily_returns: list[float], risk_free: float = 0.0) -> float:
    """Annualised Sharpe ratio from daily return series.

    TODO(V1.2): implement.
    """
    raise NotImplementedError("Sharpe ratio is a V1.2 feature.")


def compute_max_drawdown(nav_series: list[float]) -> float:
    """Maximum peak-to-trough drawdown.

    TODO(V1.2): implement.
    """
    raise NotImplementedError("Max drawdown is a V1.2 feature.")
