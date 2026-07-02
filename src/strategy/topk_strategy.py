"""
TopK selection strategy — buy the top-K ranked stocks each period.

V0.1: skeleton only.
"""

from __future__ import annotations


class TopKStrategy:
    """Select the top-K stocks by composite score.

    TODO(V1.0): implement period re-balance logic.

    Parameters
    ----------
    k : int
        Number of stocks to select.
    """

    def __init__(self, k: int = 10) -> None:
        self.k = k

    def select(self, ranked_stocks: list[tuple]) -> list[tuple]:
        """Return the top-K entries from a ranked list.

        TODO(V1.0): implement.
        """
        raise NotImplementedError("TopKStrategy is a V1.0 feature.")
