"""Test retry policy."""
from src.data_tasks.retry_policy import calculate_next_retry


class TestRetryPolicy:
    def test_first_retry_5min(self) -> None:
        r = calculate_next_retry(1)
        assert r is not None

    def test_second_retry_30min(self) -> None:
        r2 = calculate_next_retry(2)
        r1 = calculate_next_retry(1)
        assert r2 is not None
        assert (r2 - r1).total_seconds() > 0  # later than first

    def test_fifth_fails_no_retry(self) -> None:
        assert calculate_next_retry(5) is None

    def test_sixth_no_retry(self) -> None:
        assert calculate_next_retry(6) is None
