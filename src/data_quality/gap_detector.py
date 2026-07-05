"""V1.4.3 Gap detector — pure function, no DB dependencies."""

from __future__ import annotations


def _severity(missing_days: int) -> str:
    if missing_days <= 3: return "low"
    if missing_days <= 20: return "medium"
    return "high"


def detect_gaps(
    expected_dates: list[str],
    actual_dates: set[str],
) -> list[dict]:
    """Detect gaps between expected (open) trade dates and actual data dates.

    *expected_dates* must be sorted.  Continuity is determined by adjacent
    positions in *expected_dates*, NOT by calendar day arithmetic.
    """
    if not expected_dates:
        return [{"gap_type": "calendar_missing", "missing_days": 0, "severity": "low",
                 "gap_start_date": None, "gap_end_date": None}]

    if not actual_dates:
        return [{"gap_type": "no_data", "missing_days": len(expected_dates),
                 "severity": _severity(len(expected_dates)),
                 "gap_start_date": expected_dates[0], "gap_end_date": expected_dates[-1]}]

    gaps: list[dict] = []
    in_gap = False
    gap_start = ""

    for i, d in enumerate(expected_dates):
        has_data = d in actual_dates
        if not has_data and not in_gap:
            in_gap = True
            gap_start = d
        elif has_data and in_gap:
            in_gap = False
            gap_end = expected_dates[i - 1]
            missing = expected_dates.index(gap_end) - expected_dates.index(gap_start) + 1
            gaps.append({
                "gap_type": "single_day" if missing == 1 else "date_range",
                "missing_days": missing,
                "severity": _severity(missing),
                "gap_start_date": gap_start,
                "gap_end_date": gap_end,
            })
    if in_gap:
        gap_end = expected_dates[-1]
        missing = expected_dates.index(gap_end) - expected_dates.index(gap_start) + 1
        gaps.append({
            "gap_type": "single_day" if missing == 1 else "date_range",
            "missing_days": missing,
            "severity": _severity(missing),
            "gap_start_date": gap_start,
            "gap_end_date": gap_end,
        })
    return gaps
