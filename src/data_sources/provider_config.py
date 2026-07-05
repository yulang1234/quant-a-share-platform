"""V1.4.1 provider configuration and default priorities."""

# Default provider priority for daily_raw data
DAILY_RAW_PRIORITY = ["local_cache", "miniqmt", "tushare", "akshare"]

# daily_qfq: MiniQMT复权口径待验证, 暂不优先
DAILY_QFQ_PRIORITY = ["local_cache", "tushare", "akshare", "miniqmt"]

REALTIME_QUOTE_PRIORITY = ["miniqmt", "akshare"]
TRADING_CALENDAR_PRIORITY = ["miniqmt", "tushare", "akshare"]
STOCK_BASIC_PRIORITY = ["miniqmt", "tushare", "akshare"]

DEFAULT_PROVIDERS = [
    {"provider_name": "local_cache", "provider_type": "local", "priority": 1, "enabled": True},
    {"provider_name": "miniqmt", "provider_type": "remote", "priority": 2, "enabled": True},
    {"provider_name": "tushare", "provider_type": "remote", "priority": 3, "enabled": True},
    {"provider_name": "akshare", "provider_type": "remote", "priority": 4, "enabled": True},
]
