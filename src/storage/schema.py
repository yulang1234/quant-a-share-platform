"""
Database schema definitions for quant research platform.

All CREATE TABLE statements are centralised here so that
``init_database()`` (in ``duckdb_repo.py``) can replay them in order.
"""

# ── Ordered list of DDL statements ──────────────────────────────────────
CREATE_TABLE_SQL: list[str] = [
    # 1. Stock pool — the curated universe
    # NOTE: composite PK (stock_code, pool_name) — "000001" can belong to
    #       different pools, and the same pool never contains duplicates.
    """
    CREATE TABLE IF NOT EXISTS stock_pool (
        stock_code      VARCHAR(6)   NOT NULL,
        stock_name      VARCHAR(64)  NOT NULL,
        market          VARCHAR(8)   DEFAULT 'A股',
        exchange        VARCHAR(4)   DEFAULT 'SZ',
        pool_name       VARCHAR(64)  DEFAULT 'core_500',
        source          VARCHAR(32)  DEFAULT 'manual',
        is_active       BOOLEAN      DEFAULT TRUE,
        is_blacklisted  BOOLEAN      DEFAULT FALSE,
        note            VARCHAR(256),
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, pool_name)
    );
    """,
    # 2. Stock basic info (listing status, industry, etc.)
    """
    CREATE TABLE IF NOT EXISTS stock_basic (
        stock_code      VARCHAR(6)   NOT NULL,
        stock_name      VARCHAR(64),
        industry        VARCHAR(64),
        listing_date    DATE,
        market          VARCHAR(8),
        exchange        VARCHAR(4),
        is_hs          BOOLEAN,
        total_shares    BIGINT,
        float_shares    BIGINT,
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code)
    );
    """,
    # 3. Daily raw (unadjusted) market data
    """
    CREATE TABLE IF NOT EXISTS stock_daily_raw (
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        open            DECIMAL(12,2),
        high            DECIMAL(12,2),
        low             DECIMAL(12,2),
        close           DECIMAL(12,2),
        pre_close       DECIMAL(12,2),
        volume          BIGINT,
        amount          DECIMAL(16,2),
        amplitude       DECIMAL(8,4),
        pct_change      DECIMAL(8,4),
        change_amount   DECIMAL(12,2),
        turnover_rate   DECIMAL(8,4),
        data_source     VARCHAR(16)  DEFAULT 'akshare',
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date)
    );
    """,
    # 4. Daily QFQ (forward-adjusted) market data
    """
    CREATE TABLE IF NOT EXISTS stock_daily_qfq (
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        open            DECIMAL(12,2),
        high            DECIMAL(12,2),
        low             DECIMAL(12,2),
        close           DECIMAL(12,2),
        volume          BIGINT,
        amount          DECIMAL(16,2),
        pct_change      DECIMAL(8,4),
        turnover_rate   DECIMAL(8,4),
        data_source     VARCHAR(16)  DEFAULT 'akshare',
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date)
    );
    """,
    # 5. Adjustment factors for price-back adjustment
    """
    CREATE TABLE IF NOT EXISTS stock_adj_factor (
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        adj_factor      DECIMAL(12,6),
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date)
    );
    """,
    # 6. Data-update operation log
    """
    CREATE TABLE IF NOT EXISTS data_update_log (
        id              BIGINT,
        stock_code      VARCHAR(6),
        task_type       VARCHAR(32)  NOT NULL,
        adj_type        VARCHAR(8)   DEFAULT 'raw',
        start_date      DATE,
        end_date        DATE,
        row_count       INTEGER      DEFAULT 0,
        status          VARCHAR(16)  DEFAULT 'pending',
        error_message   VARCHAR(1024),
        started_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        finished_at     TIMESTAMP,
        PRIMARY KEY (id)
    );
    """,
    # 7. Data quality check report
    """
    CREATE TABLE IF NOT EXISTS data_quality_report (
        id              BIGINT,
        stock_code      VARCHAR(6),
        check_date      DATE         NOT NULL,
        issue_type      VARCHAR(32)  NOT NULL,
        issue_level     VARCHAR(16)  DEFAULT 'WARN',
        issue_detail    VARCHAR(1024),
        adj_type        VARCHAR(8),
        status          VARCHAR(16)  DEFAULT 'open',
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id)
    );
    """,
    # 8. Daily factor values
    """
    CREATE TABLE IF NOT EXISTS factor_daily (
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        factor_name     VARCHAR(64)  NOT NULL,
        factor_value    DECIMAL(20,8),
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date, factor_name)
    );
    """,
    # 9. Daily factor rank
    """
    CREATE TABLE IF NOT EXISTS factor_rank_daily (
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        factor_name     VARCHAR(64)  NOT NULL,
        rank            INTEGER,
        score           DECIMAL(10,4),
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date, factor_name)
    );
    """,
    # 10. Composite stock score
    """
    CREATE TABLE IF NOT EXISTS stock_score_daily (
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        score_method    VARCHAR(32)  NOT NULL,
        total_score     DECIMAL(10,4),
        rank            INTEGER,
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date, score_method)
    );
    """,
    # 11. Daily candidate stocks (selected by strategy)
    """
    CREATE TABLE IF NOT EXISTS stock_candidate_daily (
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        strategy_name   VARCHAR(64)  NOT NULL,
        rank            INTEGER,
        score           DECIMAL(10,4),
        expected_return DECIMAL(8,4),
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date, strategy_name)
    );
    """,
    # 12. Backtest run metadata
    """
    CREATE TABLE IF NOT EXISTS backtest_run (
        run_id          BIGINT,
        strategy_name   VARCHAR(64)  NOT NULL,
        pool_name       VARCHAR(64)  DEFAULT 'core_500',
        start_date      DATE,
        end_date        DATE,
        params          VARCHAR(2048),
        total_return    DECIMAL(10,4),
        sharpe_ratio    DECIMAL(8,4),
        max_drawdown    DECIMAL(8,4),
        status          VARCHAR(16)  DEFAULT 'pending',
        started_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        finished_at     TIMESTAMP,
        PRIMARY KEY (run_id)
    );
    """,
    # 13. Backtest NAV history
    """
    CREATE TABLE IF NOT EXISTS backtest_nav (
        run_id          BIGINT       NOT NULL,
        trade_date      DATE         NOT NULL,
        nav             DECIMAL(12,4),
        benchmark_nav   DECIMAL(12,4),
        daily_return    DECIMAL(8,4),
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (run_id, trade_date)
    );
    """,
    # 14. Backtest trade log
    """
    CREATE TABLE IF NOT EXISTS backtest_trade (
        trade_id        BIGINT,
        run_id          BIGINT       NOT NULL,
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        direction       VARCHAR(4)   NOT NULL,
        price           DECIMAL(12,2),
        shares          BIGINT,
        amount          DECIMAL(16,2),
        reason          VARCHAR(256),
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (trade_id)
    );
    """,
    # 15. Qlib / ML model scores
    """
    CREATE TABLE IF NOT EXISTS qlib_model_score_daily (
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        model_name      VARCHAR(64)  NOT NULL,
        score           DECIMAL(10,4),
        rank            INTEGER,
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date, model_name)
    );
    """,
]


