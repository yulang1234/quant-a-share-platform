"""Test provider config and priorities."""
from src.data_sources.provider_config import DAILY_RAW_PRIORITY, DAILY_QFQ_PRIORITY, DEFAULT_PROVIDERS


class TestProviderConfig:
    def test_default_providers_exist(self) -> None:
        assert len(DEFAULT_PROVIDERS) == 4

    def test_local_cache_first(self) -> None:
        assert DAILY_RAW_PRIORITY[0] == "local_cache"
        assert DAILY_QFQ_PRIORITY[0] == "local_cache"

    def test_akshare_last(self) -> None:
        assert DAILY_RAW_PRIORITY[-1] == "akshare"
        assert DAILY_QFQ_PRIORITY[-1] == "miniqmt"
