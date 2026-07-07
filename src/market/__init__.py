"""market package — minimal market-state skeleton (V1.5.0).

This package produces a structured but deliberately *conservative* market
state snapshot. With no broad-market index table and no limit-up/down data
in the current substrate, ``market_state`` defaults to ``unknown`` and the
three positioning switches default to ``unknown``. See
:mod:`src.market.market_state`.
"""