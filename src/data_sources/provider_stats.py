"""V1.4.1 Provider call statistics.

Usage::

    python -m src.data_sources.provider_stats
"""

from __future__ import annotations

import sys


def main() -> int:
    from src.data_sources.market_data_service import MarketDataService

    svc = MarketDataService()
    df = svc.get_call_stats()

    if df.empty:
        print("No call logs found.")
        return 0

    print(f"Total calls: {len(df)}")
    print()
    if "provider_name" in df.columns and "status" in df.columns:
        summary = df.groupby(["provider_name", "status"]).size().unstack(fill_value=0)
        print(summary.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
