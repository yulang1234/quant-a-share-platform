"""
Project initialisation tests — verify that the V0.1 skeleton is correctly set up.

Run with::

    pytest tests/test_project_init.py -v
"""

from pathlib import Path

import pytest


# ── Helpers ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def assert_path(*parts: str) -> Path:
    p = PROJECT_ROOT.joinpath(*parts)
    assert p.exists(), f"Expected path does not exist: {p}"
    return p


# ── Directory existence tests ──────────────────────────────────────────

class TestDirectories:
    """Key directories must exist."""

    def test_config_dir(self) -> None:
        assert_path("config")

    def test_data_duckdb_dir(self) -> None:
        assert_path("data", "duckdb")

    def test_data_parquet_dir(self) -> None:
        assert_path("data", "parquet")

    def test_parquet_ods(self) -> None:
        assert_path("data", "parquet", "ods")

    def test_parquet_dwd_daily_raw(self) -> None:
        assert_path("data", "parquet", "dwd", "daily_raw")

    def test_parquet_dwd_daily_qfq(self) -> None:
        assert_path("data", "parquet", "dwd", "daily_qfq")

    def test_parquet_ads_factors(self) -> None:
        assert_path("data", "parquet", "ads", "factors")

    def test_parquet_ads_scores(self) -> None:
        assert_path("data", "parquet", "ads", "scores")

    def test_parquet_ads_backtest(self) -> None:
        assert_path("data", "parquet", "ads", "backtest")

    def test_stock_pool_dir(self) -> None:
        assert_path("data", "stock_pool")

    def test_src_package(self) -> None:
        assert_path("src")

    def test_ui_dir(self) -> None:
        assert_path("ui")

    def test_tests_dir(self) -> None:
        assert_path("tests")

    def test_docs_dir(self) -> None:
        assert_path("docs")


# ── File existence tests ────────────────────────────────────────────────

class TestCoreFiles:
    """Core project files must exist."""

    def test_env_example(self) -> None:
        assert_path(".env.example")

    def test_requirements(self) -> None:
        assert_path("requirements.txt")

    def test_readme(self) -> None:
        assert_path("README.md")

    def test_main_py(self) -> None:
        assert_path("main.py")

    def test_core_500_csv(self) -> None:
        assert_path("data", "stock_pool", "core_500.csv")

    def test_streamlit_app(self) -> None:
        assert_path("ui", "streamlit_app.py")


# ── Config tests ───────────────────────────────────────────────────────

class TestSettings:
    """The settings module must import and provide correct default paths."""

    def test_settings_import(self) -> None:
        from config.settings import (
            APP_ENV,
            get_duckdb_path,
            get_parquet_root,
            get_project_root,
            get_stock_pool_path,
        )
        assert APP_ENV == "dev"
        assert get_project_root() == PROJECT_ROOT
        assert get_duckdb_path().suffix == ".duckdb"
        assert get_stock_pool_path().name == "core_500.csv"

    def test_env_example_parse(self) -> None:
        """The .env.example file should be parseable as key=value lines."""
        content = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
        for line in content.strip().splitlines():
            if "=" in line:
                key, val = line.split("=", 1)
                assert key.strip(), f"Empty key in line: {line}"
                assert val.strip(), f"Empty value in line: {line}"


# ── Stock pool CSV tests ───────────────────────────────────────────────

class TestStockPool:
    """The core_500 CSV must be well-formed."""

    def test_csv_headers(self) -> None:
        import pandas as pd
        df = pd.read_csv(PROJECT_ROOT / "data" / "stock_pool" / "core_500.csv")
        required = {"stock_code", "stock_name", "market", "exchange",
                    "pool_name", "source", "is_active", "is_blacklisted"}
        assert required.issubset(df.columns), f"Missing columns: {required - set(df.columns)}"

    def test_csv_stock_code_format(self) -> None:
        import pandas as pd
        df = pd.read_csv(
            PROJECT_ROOT / "data" / "stock_pool" / "core_500.csv",
            dtype={"stock_code": str},
        )
        for code in df["stock_code"]:
            assert len(str(code)) == 6, f"Stock code not 6 chars: {code}"
            assert str(code).isdigit(), f"Stock code not numeric: {code}"


# ── Storage tests ──────────────────────────────────────────────────────

class TestDatabaseInit:
    """DuckDB initialisation must work correctly."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        """Use a temporary DuckDB so tests are isolated."""
        self.db_path = tmp_path / "test_quant.duckdb"
        # Patch get_duckdb_path before importing the module
        import config.settings as settings_mod
        import os
        os.environ["DUCKDB_PATH"] = str(self.db_path)
        # Reload settings to pick up the env override
        import importlib
        importlib.reload(settings_mod)

    def test_init_database(self) -> None:
        import importlib
        import src.storage.duckdb_repo as repo
        importlib.reload(repo)
        repo.init_database(self.db_path)

        # Verify tables exist
        con = repo.get_connection(self.db_path)
        result = con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        ).fetchdf()
        assert not result.empty, "No tables created"
        table_names = set(result["table_name"])
        expected = {
            "stock_pool", "stock_basic", "stock_daily_raw", "stock_daily_qfq",
            "stock_adj_factor", "data_update_log", "data_quality_report",
            "factor_daily", "factor_rank_daily", "stock_score_daily",
            "stock_candidate_daily", "backtest_run", "backtest_nav",
            "backtest_trade", "qlib_model_score_daily",
        }
        missing = expected - table_names
        assert not missing, f"Tables missing after init: {missing}"

        repo.close_connection()

    def test_insert_and_query(self) -> None:
        import pandas as pd
        import importlib
        import src.storage.duckdb_repo as repo
        importlib.reload(repo)
        repo.init_database(self.db_path)

        df = pd.DataFrame({
            "stock_code": ["000001"],
            "stock_name": ["平安银行"],
            "pool_name": ["core_500"],
            "market": ["A股"],
            "exchange": ["SZ"],
            "source": ["test"],
            "is_active": [True],
            "is_blacklisted": [False],
            "note": [""],
        })
        repo.insert_df("stock_pool", df)

        out = repo.query_df("SELECT * FROM stock_pool")
        assert len(out) == 1
        assert out.iloc[0]["stock_code"] == "000001"

        repo.close_connection()

    def test_parquet_repo_roundtrip(self) -> None:
        import pandas as pd
        from src.storage.parquet_repo import save_df, read_df, path_exists

        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        path = save_df(df, "test_roundtrip.parquet")
        assert path.exists()

        loaded = read_df("test_roundtrip.parquet")
        assert loaded.shape == (3, 2)
        assert loaded["a"].tolist() == [1, 2, 3]


# ── Main entry point tests ─────────────────────────────────────────────

class TestMainEntryPoint:
    """The main() function must execute without error."""

    def test_main_runs(self) -> None:
        """Importing and calling main() should succeed."""
        import importlib
        import main as main_mod
        importlib.reload(main_mod)
        try:
            main_mod.main()
        except Exception as e:
            pytest.fail(f"main() raised an exception: {e}")


# ── Module existence tests ─────────────────────────────────────────────

class TestModulePlaceholders:
    """All expected source modules must be importable."""

    MODULES = [
        "config.settings",
        "config.logging_config",
        "src.data_source.akshare_client",
        "src.universe.stock_pool",
        "src.universe.filters",
        "src.storage.schema",
        "src.storage.duckdb_repo",
        "src.storage.parquet_repo",
        "src.data_update.historical_loader",
        "src.data_update.daily_incremental",
        "src.data_update.retry_failed",
        "src.data_update.update_log",
        "src.data_quality.duplicate_checker",
        "src.data_quality.missing_date_checker",
        "src.data_quality.price_checker",
        "src.data_quality.quality_report",
        "src.factors.base_factor",
        "src.factors.price_factors",
        "src.factors.volume_factors",
        "src.factors.momentum_factors",
        "src.factors.volatility_factors",
        "src.scoring.factor_standardizer",
        "src.scoring.stock_ranker",
        "src.strategy.topk_strategy",
        "src.strategy.rotation_strategy",
        "src.backtest.engine",
        "src.backtest.metrics",
        "src.qlib_lab.data_converter",
        "src.qlib_lab.run_alpha158",
        "src.qlib_lab.run_alpha360",
        "src.report.daily_report",
        "src.llm.analysis_agent",
        "src.utils.logger",
        "src.utils.date_utils",
    ]

    @pytest.mark.parametrize("module_name", MODULES)
    def test_module_importable(self, module_name: str) -> None:
        import importlib
        try:
            importlib.import_module(module_name)
        except Exception as e:
            pytest.fail(f"Failed to import {module_name}: {e}")
