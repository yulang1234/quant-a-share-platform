"""sector package — sector management and stock-sector mapping (V1.5.3).

V1.5.3 provides:
- Sector basic info storage (sector_basic table)
- Stock-sector mapping storage (stock_sector_map table)
- AkShare-based sector data sync with dry-run/confirm protection
- Query APIs: get sectors by stock, get stocks by sector
- Graceful degradation when data sources are unavailable

V1.5.0 snapshot (sector_snapshot) is preserved for backward compatibility.

See :mod:`src.sector.sector_service` for query APIs.
See :mod:`src.sector.sector_sync` for data sync CLI.
"""