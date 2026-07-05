"""Test gap detector."""
from src.data_quality.gap_detector import detect_gaps


class TestGapDetector:
    def test_no_gaps(self) -> None:
        gaps = detect_gaps(["2020-01-02", "2020-01-03", "2020-01-06"], {"2020-01-02", "2020-01-03", "2020-01-06"})
        assert len(gaps) == 0

    def test_single_day(self) -> None:
        gaps = detect_gaps(["2020-01-02", "2020-01-03", "2020-01-06"], {"2020-01-02", "2020-01-06"})
        assert len(gaps) == 1
        assert gaps[0]["gap_type"] == "single_day"

    def test_date_range(self) -> None:
        gaps = detect_gaps(["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"],
                           {"2020-01-02", "2020-01-07"})
        assert any(g["gap_type"] == "date_range" for g in gaps)

    def test_no_data(self) -> None:
        gaps = detect_gaps(["2020-01-02", "2020-01-03"], set())
        assert gaps[0]["gap_type"] == "no_data"

    def test_calendar_missing(self) -> None:
        gaps = detect_gaps([], {"2020-01-02"})
        assert any(g["gap_type"] == "calendar_missing" for g in gaps)

    def test_friday_monday_continuous(self) -> None:
        """Friday 01-10 and Monday 01-13 should be adjacent in expected_dates."""
        expected = ["2020-01-09", "2020-01-10", "2020-01-13", "2020-01-14"]
        actual = {"2020-01-09", "2020-01-13"}  # missing 01-10 and 01-14
        gaps = detect_gaps(expected, actual)
        assert len(gaps) == 2  # two separate gaps

    def test_multi_segment(self) -> None:
        expected = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08"]
        actual = {"2020-01-02", "2020-01-07"}  # missing 01-03, 01-06, 01-08
        gaps = detect_gaps(expected, actual)
        assert len(gaps) >= 2

    def test_severity(self) -> None:
        gaps = detect_gaps([f"2020-01-{i:02d}" for i in range(2, 28)], set())
        assert gaps[0]["severity"] == "high"  # 26 days missing
