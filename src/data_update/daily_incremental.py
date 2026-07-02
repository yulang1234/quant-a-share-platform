"""
Daily incremental updater — fetch the latest trading day's data.

V0.1: skeleton only.
"""

from __future__ import annotations


class DailyIncrementalUpdater:
    """Check what the latest trading day is and pull fresh data.

    TODO(V0.4): determine latest date in DB → fetch delta → append.
    """

    def run(self) -> None:
        """Fetch and persist data for the most recent trading day(s)."""
        raise NotImplementedError("DailyIncrementalUpdater is a V0.4 feature.")
