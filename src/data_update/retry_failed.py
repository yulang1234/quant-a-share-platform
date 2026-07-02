"""
Retry failed data updates — re-attempt previously errored downloads.

V0.1: skeleton only.
"""

from __future__ import annotations


class RetryFailed:
    """Read ``data_update_log`` for failed tasks and re-run them.

    TODO(V0.6): iterate over ERROR-status log entries, re-fetch, update log.
    """

    def run(self) -> None:
        """Re-attempt all failed update tasks."""
        raise NotImplementedError("RetryFailed is a V0.6 feature.")
