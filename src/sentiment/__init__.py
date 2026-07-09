"""sentiment package — market sentiment cycle judgment (V1.5.2).

V1.5.2 provides:
- Sentiment indicator computation from ``stock_daily_raw``
- Rule-based sentiment cycle judgment (ice_point / repair / warming /
  climax / cooling / retreat / chaotic / unknown)
- Structured output with action hints, risk levels, and reasons

Backward compatible with V1.5.0 ``SentimentSnapshot`` and
``build_sentiment_snapshot()``.

See :mod:`src.sentiment.sentiment_cycle` for the main entry point.
"""