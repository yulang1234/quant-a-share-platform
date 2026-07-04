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
        sector          VARCHAR(128),
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
    # 8. Daily factor values (EAV style)
    #    Reserved — V0.7 uses stock_daily_factors (wide table) instead.
    #    This table may be deprecated in a future migration.
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
    #    Reserved for V0.8: factor standardization & ranking.
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
    #     Reserved for V0.8+: multi-factor composite scoring.
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
    # 11. Daily candidate stocks
    #     Reserved for V1.0: strategy-selected candidate stocks.
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
    #     Reserved for V1.0+: backtest engine.
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
    #     Reserved for V1.0+: backtest NAV tracking.
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
    #     Reserved for V1.0+: backtest trade logging.
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
    #     Reserved for V1.7+: Qlib Alpha158 / Alpha360 model integration.
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
    # 16. Data repair log (V0.6)
    """
    CREATE TABLE IF NOT EXISTS data_repair_log (
        repair_id       VARCHAR(36)   NOT NULL,
        stock_code      VARCHAR(6),
        pool_name       VARCHAR(64)  DEFAULT 'core_500',
        adj_type        VARCHAR(8)   DEFAULT 'all',
        issue_type      VARCHAR(32)  DEFAULT 'manual',
        repair_action   VARCHAR(32)  DEFAULT 'plan',
        start_date      DATE,
        end_date        DATE,
        dry_run         BOOLEAN      DEFAULT TRUE,
        confirm         BOOLEAN      DEFAULT FALSE,
        status          VARCHAR(16)  DEFAULT 'planned',
        affected_rows   BIGINT       DEFAULT 0,
        before_row_count BIGINT      DEFAULT 0,
        after_row_count  BIGINT      DEFAULT 0,
        error_message   VARCHAR(1024),
        started_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        finished_at     TIMESTAMP,
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (repair_id)
    );
    """,
    # 17. Daily stock factors — wide table (V0.7)
    """
    CREATE TABLE IF NOT EXISTS stock_daily_factors (
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        factor_date     DATE,
        source_adj      VARCHAR(8)  DEFAULT 'qfq',
        return_1d       DOUBLE,
        return_5d       DOUBLE,
        return_10d      DOUBLE,
        return_20d      DOUBLE,
        return_60d      DOUBLE,
        momentum_5d     DOUBLE,
        momentum_10d    DOUBLE,
        momentum_20d    DOUBLE,
        momentum_60d    DOUBLE,
        ma5             DOUBLE,
        ma10            DOUBLE,
        ma20            DOUBLE,
        ma60            DOUBLE,
        ma120           DOUBLE,
        close_ma5_ratio     DOUBLE,
        close_ma10_ratio    DOUBLE,
        close_ma20_ratio    DOUBLE,
        close_ma60_ratio    DOUBLE,
        close_ma120_ratio   DOUBLE,
        volatility_5d   DOUBLE,
        volatility_10d  DOUBLE,
        volatility_20d  DOUBLE,
        volatility_60d  DOUBLE,
        volume_ma5      DOUBLE,
        volume_ma20     DOUBLE,
        volume_ma60     DOUBLE,
        volume_ratio_5_20   DOUBLE,
        volume_ratio_20_60  DOUBLE,
        amount_ma5      DOUBLE,
        amount_ma20     DOUBLE,
        amount_ma60     DOUBLE,
        turnover_ma5    DOUBLE,
        turnover_ma20   DOUBLE,
        turnover_ma60   DOUBLE,
        turnover_ratio_5_20 DOUBLE,
        high_20d        DOUBLE,
        low_20d         DOUBLE,
        price_position_20d  DOUBLE,
        high_60d        DOUBLE,
        low_60d         DOUBLE,
        price_position_60d  DOUBLE,
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date)
    );
    """,
    # 18. Factor rank — cross-sectional ranking (V0.8)
    """
    CREATE TABLE IF NOT EXISTS stock_factor_rank (
        stock_code          VARCHAR(6)   NOT NULL,
        trade_date          DATE         NOT NULL,
        factor_name         VARCHAR(64)  NOT NULL,
        raw_value           DOUBLE,
        clipped_value       DOUBLE,
        zscore_value        DOUBLE,
        direction_value     DOUBLE,
        rank_value          BIGINT,
        percentile_rank     DOUBLE,
        factor_direction    VARCHAR(16),
        rank_method         VARCHAR(16) DEFAULT 'zscore',
        universe_name       VARCHAR(64) DEFAULT 'core_500',
        created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date, factor_name, universe_name)
    );
    """,
    # 19. Forward returns for factor effectiveness (V0.9)
    """
    CREATE TABLE IF NOT EXISTS factor_forward_returns (
        stock_code      VARCHAR(6)   NOT NULL,
        trade_date      DATE         NOT NULL,
        forward_days    INTEGER      NOT NULL,
        close           DOUBLE,
        future_close    DOUBLE,
        forward_return  DOUBLE,
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (stock_code, trade_date, forward_days)
    );
    """,
    # 20. Factor IC report (V0.9)
    """
    CREATE TABLE IF NOT EXISTS factor_ic_report (
        factor_name     VARCHAR(64)  NOT NULL,
        trade_date      DATE         NOT NULL,
        forward_days    INTEGER      NOT NULL,
        ic              DOUBLE,
        rank_ic         DOUBLE,
        sample_count    BIGINT,
        universe_name   VARCHAR(64) DEFAULT 'core_500',
        created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (factor_name, trade_date, forward_days, universe_name)
    );
    """,
    # 21. Factor group return report (V0.9)
    """
    CREATE TABLE IF NOT EXISTS factor_group_return_report (
        factor_name         VARCHAR(64)  NOT NULL,
        trade_date          DATE         NOT NULL,
        forward_days        INTEGER      NOT NULL,
        group_id            INTEGER      NOT NULL,
        group_count         INTEGER,
        avg_forward_return  DOUBLE,
        median_forward_return DOUBLE,
        stock_count         BIGINT,
        universe_name       VARCHAR(64) DEFAULT 'core_500',
        created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (factor_name, trade_date, forward_days, group_id, universe_name)
    );
    """,
    # 22. Factor analysis summary (V0.9)
    """
    CREATE TABLE IF NOT EXISTS factor_analysis_summary (
        factor_name             VARCHAR(64)  NOT NULL,
        forward_days            INTEGER      NOT NULL,
        start_date              DATE,
        end_date                DATE,
        avg_ic                  DOUBLE,
        avg_rank_ic             DOUBLE,
        ic_std                  DOUBLE,
        rank_ic_std             DOUBLE,
        ic_ir                   DOUBLE,
        rank_ic_ir              DOUBLE,
        positive_ic_ratio       DOUBLE,
        positive_rank_ic_ratio  DOUBLE,
        avg_top_group_return    DOUBLE,
        avg_bottom_group_return DOUBLE,
        avg_group_spread        DOUBLE,
        trade_date_count        BIGINT,
        universe_name           VARCHAR(64) DEFAULT 'core_500',
        created_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        updated_at              TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (factor_name, forward_days, start_date, end_date, universe_name)
    );
    """,
    # 23. Strategy configuration (V1.0)
    """
    CREATE TABLE IF NOT EXISTS strategy_config (
        strategy_name               VARCHAR(64)  NOT NULL,
        strategy_type               VARCHAR(32),
        factor_name                 VARCHAR(64),
        factor_weights              VARCHAR(2048),
        top_k                       INTEGER,
        min_avg_rank_ic             DOUBLE,
        min_positive_rank_ic_ratio  DOUBLE,
        min_group_spread            DOUBLE,
        is_active                   BOOLEAN DEFAULT TRUE,
        description                 VARCHAR(512),
        created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (strategy_name)
    );
    """,
    # 24. Strategy selection result (V1.0)
    """
    CREATE TABLE IF NOT EXISTS strategy_selection_result (
        strategy_name       VARCHAR(64)  NOT NULL,
        trade_date          DATE         NOT NULL,
        stock_code          VARCHAR(6)   NOT NULL,
        rank_in_strategy    INTEGER,
        composite_score     DOUBLE,
        factor_count        INTEGER,
        selected_reason     VARCHAR(512),
        universe_name       VARCHAR(64) DEFAULT 'core_500',
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (strategy_name, trade_date, stock_code, universe_name)
    );
    """,
    # 25. Strategy selection detail (V1.0)
    """
    CREATE TABLE IF NOT EXISTS strategy_selection_detail (
        strategy_name           VARCHAR(64)  NOT NULL,
        trade_date              DATE         NOT NULL,
        stock_code              VARCHAR(6)   NOT NULL,
        factor_name             VARCHAR(64)  NOT NULL,
        factor_score            DOUBLE,
        factor_weight           DOUBLE,
        weighted_score          DOUBLE,
        factor_rank_value       BIGINT,
        factor_percentile_rank  DOUBLE,
        universe_name           VARCHAR(64) DEFAULT 'core_500',
        created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (strategy_name, trade_date, stock_code, factor_name, universe_name)
    );
    """,
    # 26. Backtest config (V1.1)
    """
    CREATE TABLE IF NOT EXISTS backtest_config (
        backtest_name       VARCHAR(128) NOT NULL,
        strategy_name       VARCHAR(64),
        start_date          DATE,
        end_date            DATE,
        initial_cash        DOUBLE,
        top_k               INTEGER,
        rebalance_frequency VARCHAR(16),
        price_type          VARCHAR(16) DEFAULT 'qfq_close',
        status              VARCHAR(16) DEFAULT 'pending',
        description         VARCHAR(512),
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (backtest_name)
    );
    """,
    # 27. Backtest positions (V1.1)
    """
    CREATE TABLE IF NOT EXISTS backtest_position (
        backtest_name       VARCHAR(128) NOT NULL,
        strategy_name       VARCHAR(64),
        rebalance_date      DATE,
        trade_date          DATE         NOT NULL,
        stock_code          VARCHAR(6)   NOT NULL,
        weight              DOUBLE,
        rank_in_strategy    INTEGER,
        composite_score     DOUBLE,
        universe_name       VARCHAR(64) DEFAULT 'core_500',
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (backtest_name, trade_date, stock_code, universe_name)
    );
    """,
    # 28. Backtest daily returns (V1.1)
    """
    CREATE TABLE IF NOT EXISTS backtest_daily_return (
        backtest_name       VARCHAR(128) NOT NULL,
        trade_date          DATE         NOT NULL,
        portfolio_return    DOUBLE,
        holding_count       INTEGER,
        universe_name       VARCHAR(64) DEFAULT 'core_500',
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (backtest_name, trade_date, universe_name)
    );
    """,
    # 29. Backtest equity curve (V1.1)
    """
    CREATE TABLE IF NOT EXISTS backtest_equity_curve (
        backtest_name       VARCHAR(128) NOT NULL,
        trade_date          DATE         NOT NULL,
        initial_cash        DOUBLE,
        portfolio_return    DOUBLE,
        equity              DOUBLE,
        universe_name       VARCHAR(64) DEFAULT 'core_500',
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (backtest_name, trade_date, universe_name)
    );
    """,
    # 30. Backtest performance summary (V1.2)
    """
    CREATE TABLE IF NOT EXISTS backtest_performance_summary (
        backtest_name           VARCHAR(128) NOT NULL,
        start_date              DATE,
        end_date                DATE,
        initial_equity          DOUBLE,
        final_equity            DOUBLE,
        total_return            DOUBLE,
        annualized_return       DOUBLE,
        annualized_volatility   DOUBLE,
        max_drawdown            DOUBLE,
        sharpe_ratio            DOUBLE,
        calmar_ratio            DOUBLE,
        win_rate                DOUBLE,
        avg_daily_return        DOUBLE,
        best_daily_return       DOUBLE,
        worst_daily_return      DOUBLE,
        trading_days            BIGINT,
        risk_free_rate          DOUBLE,
        created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (backtest_name, start_date, end_date)
    );
    """,
    # 31. Backtest drawdown series (V1.2)
    """
    CREATE TABLE IF NOT EXISTS backtest_drawdown_series (
        backtest_name       VARCHAR(128) NOT NULL,
        trade_date          DATE         NOT NULL,
        equity              DOUBLE,
        running_max_equity  DOUBLE,
        drawdown            DOUBLE,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (backtest_name, trade_date)
    );
    """,
    # 32. Backtest monthly return (V1.2)
    """
    CREATE TABLE IF NOT EXISTS backtest_monthly_return (
        backtest_name       VARCHAR(128) NOT NULL,
        year_month          VARCHAR(7)   NOT NULL,
        monthly_return      DOUBLE,
        start_equity        DOUBLE,
        end_equity          DOUBLE,
        trading_days        BIGINT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (backtest_name, year_month)
    );
    """,
    # 33. Backtest yearly return (V1.2)
    """
    CREATE TABLE IF NOT EXISTS backtest_yearly_return (
        backtest_name       VARCHAR(128) NOT NULL,
        year                VARCHAR(4)   NOT NULL,
        yearly_return       DOUBLE,
        start_equity        DOUBLE,
        end_equity          DOUBLE,
        trading_days        BIGINT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (backtest_name, year)
    );
    """,
]


