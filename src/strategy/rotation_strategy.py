"""
Rotation strategy — rotate positions among top-ranked stocks over time.

V0.1: skeleton only.
"""

from __future__ import annotations


class RotationStrategy:
    """Periodically re-balance into the current top-K universe.

    TODO(V1.2): implement re-balance calendar, slippage, position sizing.
    """

    def run(self) -> None:
        """Execute one full re-balance cycle."""
        raise NotImplementedError("RotationStrategy is a V1.2 feature.")
