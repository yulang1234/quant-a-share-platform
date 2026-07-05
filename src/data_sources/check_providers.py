"""V1.4.1 Check all provider health statuses.

Usage::

    python -m src.data_sources.check_providers
"""

from __future__ import annotations

import sys


def main() -> int:
    from src.data_sources.market_data_service import MarketDataService

    svc = MarketDataService()
    results = svc.check_all_providers()

    print(f"{'Provider':<16} {'Status':<12} {'Latency':>8}  Message")
    print("-" * 70)
    for r in results:
        print(f"{r['provider_name']:<16} {r['status']:<12} {str(r.get('latency_ms',''))+'ms':>8}  {r.get('error_message','')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
