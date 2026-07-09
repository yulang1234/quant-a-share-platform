"""
Project configuration module.

Reads settings from .env file and provides typed access to all project paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


# ── Project root detection ──────────────────────────────────────────────
# The root is two levels up from this file (config/settings.py → project root).
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# Load .env from project root
load_dotenv(_PROJECT_ROOT / ".env")


# ── Environment ─────────────────────────────────────────────────────────
APP_ENV: str = os.getenv("APP_ENV", "dev")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


# ── Paths ───────────────────────────────────────────────────────────────
def get_project_root() -> Path:
    """Return the absolute Path of the project root directory."""
    return _PROJECT_ROOT


def get_duckdb_path() -> Path:
    """Return the absolute Path to the DuckDB database file."""
    rel = os.getenv("DUCKDB_PATH", "data/duckdb/quant_a_share.duckdb")
    return _ensure_absolute(rel)


def get_parquet_root() -> Path:
    """Return the absolute Path to the Parquet storage root."""
    rel = os.getenv("PARQUET_ROOT", "data/parquet")
    return _ensure_absolute(rel)


def get_stock_pool_path() -> Path:
    """Return the absolute Path to the stock pool CSV file."""
    rel = os.getenv("STOCK_POOL_PATH", "data/stock_pool/universe_all_a.csv")
    return _ensure_absolute(rel)


def get_meta_db_url() -> str:
    """Return the meta-database connection URL (SQLite).

    Priority:
    1. ``DATABASE_URL`` env var (kept for backward compat, can be SQLite).
    2. ``META_DB_PATH`` env var.
    3. Local SQLite fallback: ``data/meta/quant_meta.db``.

    No PostgreSQL required — project runs on SQLite + DuckDB + Parquet.
    """
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        return db_url
    meta_path = os.getenv("META_DB_PATH", "data/meta/quant_meta.db")
    meta_abs = _ensure_absolute(meta_path)
    meta_abs.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{meta_abs}"


# ── Helpers ─────────────────────────────────────────────────────────────
def _ensure_absolute(rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p
    return _PROJECT_ROOT / p


def ensure_dirs() -> None:
    """Create all directories required by the project configuration."""
    dirs = [
        get_duckdb_path().parent,
        get_parquet_root(),
        get_parquet_root() / "ods",
        get_parquet_root() / "dwd" / "daily_raw",
        get_parquet_root() / "dwd" / "daily_qfq",
        get_parquet_root() / "ads" / "factors",
        get_parquet_root() / "ads" / "scores",
        get_parquet_root() / "ads" / "backtest",
        get_stock_pool_path().parent,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
