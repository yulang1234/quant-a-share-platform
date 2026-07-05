"""Test provider health view helpers."""
from ui.components.provider_health_view import (
    get_meta_db_status, load_provider_health, load_provider_config,
    load_provider_stats, load_recent_errors,
)


class TestHealthView:
    def test_meta_status(self) -> None:
        s = get_meta_db_status()
        assert s["db_type"] in ("PostgreSQL", "SQLite", "Unknown")

    def test_health_empty(self) -> None:
        df = load_provider_health()
        assert df is not None

    def test_config_empty(self) -> None:
        df = load_provider_config()
        assert df is not None

    def test_stats_empty(self) -> None:
        df = load_provider_stats()
        assert df is not None

    def test_errors_empty(self) -> None:
        df = load_recent_errors(10)
        assert df is not None

    def test_no_sensitive_info(self) -> None:
        s = get_meta_db_status()
        # Never expose password
        status_str = str(s)
        assert "199431" not in status_str
        assert "postgresql" not in status_str.lower() or "connected" in str(s).lower()
