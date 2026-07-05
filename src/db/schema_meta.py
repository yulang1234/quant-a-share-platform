"""V1.4.1 Meta-database ORM models (SQLAlchemy).

Compatible with PostgreSQL and SQLite.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ── 1. security_master ────────────────────────────────────────────────────

class SecurityMaster(Base):
    __tablename__ = "security_master"

    security_id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(12), nullable=False)
    exchange = Column(String(8), nullable=False)
    asset_type = Column(String(24), default="stock")
    security_name = Column(String(64))
    list_date = Column(DateTime)
    delist_date = Column(DateTime)
    market_board = Column(String(32))
    industry = Column(String(64))
    is_st = Column(Boolean, default=False)
    status = Column(String(16), default="active")
    currency = Column(String(8), default="CNY")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (UniqueConstraint("symbol", "exchange", name="uq_security"),)


# ── 2. universe_config ────────────────────────────────────────────────────

class UniverseConfig(Base):
    __tablename__ = "universe_config"

    universe_id = Column(Integer, primary_key=True, autoincrement=True)
    universe_name = Column(String(64), unique=True, nullable=False)
    description = Column(Text)
    asset_type = Column(String(24), default="stock")
    rule_type = Column(String(32), default="custom")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── 3. universe_member ────────────────────────────────────────────────────

class UniverseMember(Base):
    __tablename__ = "universe_member"

    id = Column(Integer, primary_key=True, autoincrement=True)
    universe_id = Column(Integer, nullable=False)
    security_id = Column(Integer)
    symbol = Column(String(12), nullable=False)
    exchange = Column(String(8), nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    weight = Column(Float, default=1.0)
    status = Column(String(16), default="active")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── 4. data_provider_config ───────────────────────────────────────────────

class DataProviderConfig(Base):
    __tablename__ = "data_provider_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(32), unique=True, nullable=False)
    provider_type = Column(String(16), default="remote")
    priority = Column(Integer, default=10)
    enabled = Column(Boolean, default=True)
    supports_daily = Column(Boolean, default=True)
    supports_minute = Column(Boolean, default=False)
    supports_realtime = Column(Boolean, default=False)
    supports_calendar = Column(Boolean, default=False)
    supports_stock_basic = Column(Boolean, default=False)
    rate_limit_per_minute = Column(Integer, default=0)
    timeout_seconds = Column(Integer, default=30)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── 5. data_provider_health ───────────────────────────────────────────────

class DataProviderHealth(Base):
    __tablename__ = "data_provider_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(32), unique=True, nullable=False)
    health_status = Column(String(16), default="down")
    last_check_at = Column(DateTime)
    latency_ms = Column(Integer)
    success_rate_1d = Column(Float)
    success_rate_7d = Column(Float)
    last_error_type = Column(String(64))
    last_error_message = Column(Text)


# ── 6. data_provider_call_log ─────────────────────────────────────────────

class DataProviderCallLog(Base):
    __tablename__ = "data_provider_call_log"

    call_id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(32), nullable=False)
    method_name = Column(String(64))
    security_id = Column(Integer)
    symbol = Column(String(12))
    exchange = Column(String(8))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    adj_type = Column(String(8))
    status = Column(String(16), default="success")
    row_count = Column(Integer, default=0)
    duration_ms = Column(Integer)
    error_type = Column(String(64))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


# ── All tables list ───────────────────────────────────────────────────────

ALL_TABLES = [
    SecurityMaster, UniverseConfig, UniverseMember,
    DataProviderConfig, DataProviderHealth, DataProviderCallLog,
]
