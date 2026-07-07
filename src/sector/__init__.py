"""sector package — minimal sector-strength skeleton (V1.5.0).

Sectors are derived *on the fly* by joining ``security_master.industry``
with ``stock_daily_raw.pct_change`` for the latest trade date — there is no
pre-computed sector daily-return table. When either side is missing,
:func:`src.sector.sector_snapshot.build_sector_snapshot` returns an empty
list rather than raising.
"""