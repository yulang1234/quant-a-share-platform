"""V1.4.4 Coverage before/after comparison."""

from __future__ import annotations


def compare_coverage(security_ids: list[str], adj_type: str,
                     start_date: str, end_date: str) -> dict:
    """Compare coverage before/after a backfill operation.

    Returns dict with before/after stats or empty if no coverage reports exist.
    """
    from src.data_quality.coverage_repo import CoverageReportRepository
    repo = CoverageReportRepository()
    reports = repo.list_all(limit=5000)

    matching = [r for r in reports if r.adj_type == adj_type
                and r.start_date == start_date and r.end_date == end_date]

    before = {"count": len(matching), "avg_rate": None, "total_missing": 0}
    if matching:
        rates = [r.coverage_rate for r in matching if r.coverage_rate is not None]
        before["avg_rate"] = sum(rates) / len(rates) if rates else None
        before["total_missing"] = sum(r.missing_trade_days for r in matching)

    return {"before": before, "after": None}  # after requires re-scan
