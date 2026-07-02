"""
Quality report generator — aggregate all checks into a structured report.

V0.1: skeleton only.
"""

from __future__ import annotations


def generate_quality_report(stock_code: str | None = None) -> dict:
    """Run all quality checks and persist results to ``data_quality_report``.

    TODO(V0.5): call duplicate, missing-date, price checkers and write summary.

    Parameters
    ----------
    stock_code : str, optional
        If ``None``, run for all active stocks.

    Returns
    -------
    dict
        Summary counts (total_issues, by_level, by_type).
    """
    raise NotImplementedError("Quality report generation is a V0.5 feature.")
