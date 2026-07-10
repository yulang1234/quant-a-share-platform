"""Meta-database ORM models (SQLAlchemy) — SQLite local single-machine.

All tables live in a single SQLite file (data/meta/quant_meta.db).
No PostgreSQL dependency.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
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
    # V1.4.6: enhanced status fields
    is_suspended = Column(Boolean, default=False)
    data_source = Column(String(32))  # which provider populated this row
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

# ── 7. trading_calendar (V1.4.2) ───────────────────────────────────────────

class TradingCalendar(Base):
    __tablename__ = "trading_calendar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(DateTime, nullable=False)
    exchange = Column(String(8), default="CN")
    is_open = Column(Boolean, default=True)
    is_weekend = Column(Boolean, default=False)
    is_holiday = Column(Boolean, default=False)
    pre_trade_date = Column(DateTime)
    next_trade_date = Column(DateTime)
    source = Column(String(32), default="manual")
    # V1.4.6: real calendar tracking
    calendar_source = Column(String(32), default="generated")  # akshare / generated / manual
    is_real_calendar = Column(Boolean, default=False)          # True = real exchange calendar
    source_provider = Column(String(32))                        # provider name (akshare/tushare)
    source_updated_at = Column(DateTime)                        # when provider data was fetched
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_at = Column(DateTime, default=datetime.now)


# ── 8. data_load_task (V1.4.2) ─────────────────────────────────────────────

class DataLoadTask(Base):
    __tablename__ = "data_load_task"

    task_id = Column(Integer, primary_key=True, autoincrement=True)
    universe_id = Column(Integer)
    security_id = Column(Integer)
    symbol = Column(String(12))
    exchange = Column(String(8))
    asset_type = Column(String(24), default="stock")
    data_type = Column(String(16), default="daily_bar")
    adj_type = Column(String(8))
    start_date = Column(String(16))
    end_date = Column(String(16))
    provider_preference = Column(String(64))
    # V1.4.7: batch tracking
    batch_id = Column(String(64))
    status = Column(String(16), default="pending")
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    row_count = Column(Integer, default=0)
    error_type = Column(String(64))
    error_message = Column(Text)
    next_retry_at = Column(DateTime)
    last_attempt_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── 9. data_load_task_log (V1.4.2) ─────────────────────────────────────────

class DataLoadTaskLog(Base):
    __tablename__ = "data_load_task_log"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, nullable=False)
    status_before = Column(String(16))
    status_after = Column(String(16))
    provider_used = Column(String(32))
    row_count = Column(Integer, default=0)
    duration_ms = Column(Integer)
    error_type = Column(String(64))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


# ── 10. data_coverage_report (V1.4.3) ──────────────────────────────────────

class DataCoverageReport(Base):
    __tablename__ = "data_coverage_report"

    report_id = Column(Integer, primary_key=True, autoincrement=True)
    universe_id = Column(Integer)
    security_id = Column(Integer)
    symbol = Column(String(12))
    exchange = Column(String(8))
    asset_type = Column(String(24), default="stock")
    data_type = Column(String(16), default="daily_bar")
    adj_type = Column(String(8))
    start_date = Column(String(16))
    end_date = Column(String(16))
    expected_trade_days = Column(Integer, default=0)
    actual_trade_days = Column(Integer, default=0)
    missing_trade_days = Column(Integer, default=0)
    coverage_rate = Column(Float)
    first_data_date = Column(String(16))
    last_data_date = Column(String(16))
    status = Column(String(24), default="unknown")
    source = Column(String(32), default="coverage_scanner")
    calendar_version = Column(String(16))
    generated_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── 11. data_gap_detail (V1.4.3) ───────────────────────────────────────────

class DataGapDetail(Base):
    __tablename__ = "data_gap_detail"

    gap_id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer)
    universe_id = Column(Integer)
    security_id = Column(Integer)
    symbol = Column(String(12))
    exchange = Column(String(8))
    data_type = Column(String(16), default="daily_bar")
    adj_type = Column(String(8))
    gap_start_date = Column(String(16))
    gap_end_date = Column(String(16))
    missing_days = Column(Integer, default=0)
    gap_type = Column(String(24))
    severity = Column(String(16), default="low")
    repair_status = Column(String(16), default="pending")
    related_task_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── 12. backfill_batch (V1.4.7) ──────────────────────────────────────────────

class BackfillBatch(Base):
    __tablename__ = "backfill_batch"

    batch_id = Column(String(64), primary_key=True)
    batch_name = Column(String(128))
    universe_name = Column(String(64))
    adj_type = Column(String(8))
    start_date = Column(String(16))
    end_date = Column(String(16))
    split = Column(String(16), default="yearly")
    planned_task_count = Column(Integer, default=0)
    written_task_count = Column(Integer, default=0)
    executed_task_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    empty_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    status = Column(String(24), default="planned")
    dry_run = Column(Boolean, default=True)
    confirm = Column(Boolean, default=False)
    save_local = Column(Boolean, default=False)
    max_limit = Column(Integer, default=20)
    provider_name = Column(String(32))
    sleep_seconds = Column(Float, default=1.0)
    error_message = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── 13. backfill_batch_snapshot (V1.4.7) ─────────────────────────────────────

class BackfillBatchSnapshot(Base):
    __tablename__ = "backfill_batch_snapshot"

    snapshot_id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(64), nullable=False)
    snapshot_type = Column(String(16), nullable=False)  # "before" or "after"
    universe_name = Column(String(64))
    adj_type = Column(String(8))
    start_date = Column(String(16))
    end_date = Column(String(16))
    stock_count = Column(Integer, default=0)
    complete_count = Column(Integer, default=0)
    partial_count = Column(Integer, default=0)
    empty_count = Column(Integer, default=0)
    calendar_missing_count = Column(Integer, default=0)
    avg_coverage_rate = Column(Float)
    min_coverage_rate = Column(Float)
    max_coverage_rate = Column(Float)
    calendar_source = Column(String(32))
    is_real_calendar = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)


# ── 14. portfolio_position (V1.7.1) ─────────────────────────────────────────

class PortfolioPosition(Base):
    """Local portfolio position record — real or simulated.

    Stores cost basis, quantity, position percentage, buy rationale,
    original strategy and an optional V1.6 entry snapshot.
    No automatic trading or live pricing — purely a record-keeping table.
    """

    __tablename__ = "portfolio_position"

    position_id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_name = Column(String(64), nullable=False, default="default", index=True)
    stock_code = Column(String(12), nullable=False, index=True)
    exchange = Column(String(8), nullable=False)
    stock_name = Column(String(64), nullable=False)
    buy_date = Column(Date, nullable=False, index=True)
    avg_cost = Column(Float, nullable=False)
    quantity = Column(Float, nullable=True)
    position_pct = Column(Float, nullable=False)
    buy_reason = Column(Text, nullable=False)
    sector_name = Column(String(128), nullable=True)
    original_strategy = Column(String(128), nullable=True)
    entry_snapshot_json = Column(Text, nullable=True)
    snapshot_version = Column(String(32), nullable=True)
    user_note = Column(Text, nullable=True)
    is_simulated = Column(Boolean, nullable=False, default=True, index=True)
    source = Column(String(32), default="manual")
    status = Column(String(16), nullable=False, default="active", index=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ── 15. portfolio_position_diagnosis (V1.7.2) ────────────────────────────────

class PortfolioPositionDiagnosis(Base):
    """Daily position diagnosis result — evaluates whether an active position
    should continue to be held based on current market, sentiment, sector,
    leader, trend and condition engine signals.

    No trading execution.  Research-aid only.
    """

    __tablename__ = "portfolio_position_diagnosis"

    diagnosis_id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    portfolio_name = Column(String(64), nullable=False, index=True)
    stock_code = Column(String(12), nullable=False, index=True)
    stock_name = Column(String(64), nullable=True)
    sector_name = Column(String(128), nullable=True)

    diagnosis_status = Column(String(24), nullable=False, index=True)
    suggested_action = Column(String(32), nullable=False, index=True)
    thesis_status = Column(String(32), nullable=False)

    market_support_score = Column(Float, default=0.0)
    sentiment_support_score = Column(Float, default=0.0)
    sector_support_score = Column(Float, default=0.0)
    leader_support_score = Column(Float, default=0.0)
    trend_health_score = Column(Float, default=0.0)
    condition_support_score = Column(Float, default=0.0)
    thesis_score = Column(Float, default=0.0)

    health_score = Column(Float, default=0.0)
    data_coverage_ratio = Column(Float, default=0.0)

    latest_close = Column(Float, nullable=True)
    unrealized_return_pct = Column(Float, nullable=True)
    drawdown_20d = Column(Float, nullable=True)
    position_pct = Column(Float, nullable=True)
    position_size_status = Column(String(24), nullable=True)

    reason_summary = Column(Text)
    risk_warnings_json = Column(Text)
    observation_conditions_json = Column(Text)
    invalidation_conditions_json = Column(Text)
    evidence_json = Column(Text)
    current_context_json = Column(Text)

    data_quality_status = Column(String(24))
    issue_summary = Column(Text)
    rule_version = Column(String(32), default="v1.7.2")

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("position_id", "trade_date", name="uq_position_diagnosis"),
    )


# ── 16. portfolio_risk_snapshot (V1.7.3) ────────────────────────────────────

class PortfolioRiskSnapshot(Base):
    """Portfolio-level risk snapshot — concentration, correlation, drawdown.

    One row per (trade_date, portfolio_name, is_simulated).
    No trading execution.
    """

    __tablename__ = "portfolio_risk_snapshot"

    risk_snapshot_id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, index=True)
    portfolio_name = Column(String(64), nullable=False, index=True)
    is_simulated = Column(Boolean, nullable=False, index=True)

    portfolio_risk_score = Column(Float, default=0.0)
    portfolio_risk_level = Column(String(24), index=True)
    portfolio_permission = Column(String(40), index=True)

    position_count = Column(Integer, default=0)
    sector_count = Column(Integer, default=0)
    total_position_pct = Column(Float, default=0.0)
    cash_pct = Column(Float, nullable=True)
    max_single_position_pct = Column(Float, default=0.0)
    max_single_position_code = Column(String(12))
    max_sector_position_pct = Column(Float, default=0.0)
    max_sector_name = Column(String(128))
    top3_position_pct = Column(Float, default=0.0)
    crowded_sector_count = Column(Integer, default=0)
    high_correlation_pair_count = Column(Integer, default=0)
    average_pairwise_correlation = Column(Float, nullable=True)
    max_pairwise_correlation = Column(Float, nullable=True)
    portfolio_drawdown_20d = Column(Float, nullable=True)
    portfolio_drawdown_60d = Column(Float, nullable=True)
    consecutive_loss_days = Column(Integer, default=0)
    dangerous_position_count = Column(Integer, default=0)
    cautious_position_count = Column(Integer, default=0)
    unknown_position_count = Column(Integer, default=0)
    market_state = Column(String(32))
    sentiment_cycle = Column(String(32))

    market_exposure_risk_score = Column(Float, default=0.0)
    single_position_risk_score = Column(Float, default=0.0)
    sector_concentration_risk_score = Column(Float, default=0.0)
    correlation_risk_score = Column(Float, default=0.0)
    drawdown_risk_score = Column(Float, default=0.0)
    consecutive_loss_risk_score = Column(Float, default=0.0)
    diagnosis_risk_score = Column(Float, default=0.0)
    data_coverage_ratio = Column(Float, default=0.0)

    risk_flags_json = Column(Text)
    recommendations_json = Column(Text)
    observation_conditions_json = Column(Text)
    risk_release_conditions_json = Column(Text)
    evidence_json = Column(Text)
    issue_summary = Column(Text)
    data_quality_status = Column(String(24))
    rule_version = Column(String(32), default="v1.7.3")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            "trade_date", "portfolio_name", "is_simulated",
            name="uq_portfolio_risk_snapshot",
        ),
    )


ALL_TABLES = [
    SecurityMaster, UniverseConfig, UniverseMember,
    DataProviderConfig, DataProviderHealth, DataProviderCallLog,
    TradingCalendar, DataLoadTask, DataLoadTaskLog,
    DataCoverageReport, DataGapDetail,
    BackfillBatch, BackfillBatchSnapshot,
    PortfolioPosition,
    PortfolioPositionDiagnosis,
    PortfolioRiskSnapshot,
]
