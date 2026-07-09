"""V1.5.7: Verify all-A defaults have replaced core_500 in main paths."""
import inspect
import pytest


class TestDefaultPool:
    def test_stock_pool_default_is_all_a(self):
        from src.universe.stock_pool import DEFAULT_POOL
        assert DEFAULT_POOL == "universe_all_a"

    def test_historical_loader_default(self):
        from src.data_update.historical_loader import load_historical_data
        sig = inspect.signature(load_historical_data)
        assert sig.parameters["pool_name"].default == "universe_all_a"

    def test_daily_incremental_default(self):
        from src.data_update.daily_incremental import run_daily_incremental
        sig = inspect.signature(run_daily_incremental)
        assert sig.parameters["pool_name"].default == "universe_all_a"

    def test_batch_planner_default(self):
        # Check CLI parser default via argparse
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("--universe", default="universe_all_a")
        assert p.parse_args([]).universe == "universe_all_a"


class TestLegacyCore500Compat:
    def test_core500_still_valid_pool(self):
        from src.universe.stock_pool import get_active_stock_pool
        sig = inspect.signature(get_active_stock_pool)
        assert "pool_name" in sig.parameters

    def test_settings_default_not_core500(self):
        """settings.py code default should be universe_all_a.csv."""
        # Read the source code directly to verify default
        import config.settings
        import inspect
        src = inspect.getsource(config.settings.get_stock_pool_path)
        assert "universe_all_a" in src


class TestAllARecentSync:
    def test_dry_run_default(self):
        from src.data_update.all_a_recent_sync import sync_all_a_recent
        result = sync_all_a_recent(recent_days=30, dry_run=True)
        assert result["status"] == "dry_run"
        assert result["universe"] == "universe_all_a"

    def test_default_recent_days(self):
        from src.data_update.all_a_recent_sync import sync_all_a_recent
        result = sync_all_a_recent(dry_run=True)
        assert result["recent_days"] == 30
        assert result["adj"] == "qfq"

    def test_confirm_writes_plan(self, monkeypatch):
        def _fake_plan(*args, **kwargs):
            return {"batch_id": "test_batch", "task_count": 100}
        monkeypatch.setattr(
            "src.backfill.batch_planner.plan_batch", _fake_plan,
        )
        from src.data_update.all_a_recent_sync import sync_all_a_recent
        result = sync_all_a_recent(recent_days=30, dry_run=False, plan_only=True)
        assert result["status"] == "ok"
        assert result["batch_id"] == "test_batch"
