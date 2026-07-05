"""V1.4.2 Retry policy for data load tasks."""

from datetime import datetime, timedelta


def calculate_next_retry(attempt_count: int) -> datetime | None:
    """Return next retry datetime or None if max attempts exceeded."""
    delays = {
        1: timedelta(minutes=5),
        2: timedelta(minutes=30),
        3: timedelta(hours=2),
        4: timedelta(hours=12),
    }
    if attempt_count <= 0:
        return datetime.now() + delays[1]
    if attempt_count >= 5:
        return None  # no more retries
    return datetime.now() + delays.get(attempt_count, timedelta(hours=24))
