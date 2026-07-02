"""
Historical data loader — batch-load up to 20 years of daily data per stock.

V0.1: skeleton only.
"""

from __future__ import annotations


class HistoricalLoader:
    """Orchestrates the initial bulk-load of historical market data.

    TODO(V0.3): iterate over stock pool, fetch raw + qfq, write to DuckDB.
    """

    def run(self) -> None:
        """Execute the full historical data initialisation."""
        raise NotImplementedError("HistoricalLoader is a V0.3 feature.")
