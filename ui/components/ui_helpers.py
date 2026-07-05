"""V1.4 UI helpers — safe data display, Chinese labels, stock names."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from src.storage.duckdb_repo import query_df

# ── Display defaults and translations ─────────────────────────────────────
DEFAULT_DISPLAY_LIMIT = 5000

COLUMN_CN = {
    "stock_code": "股票代码",
    "stock_name": "股票名称",
    "trade_date": "交易日期",
    "check_date": "检查日期",
    "factor_name": "因子名称",
    "model_name": "模型名称",
    "strategy_name": "策略名称",
    "backtest_name": "回测名称",
    "pool_name": "股票池",
    "market": "市场",
    "exchange": "交易所",
    "is_active": "状态",
    "is_blacklisted": "黑名单",
    "note": "备注",
    "sector": "板块/行业",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "close": "收盘价",
    "volume": "成交量",
    "amount": "成交额",
    "turnover_rate": "换手率",
    "rank_value": "排名",
    "percentile_rank": "百分位排名",
    "raw_value": "原始值",
    "clipped_value": "去极值后",
    "zscore_value": "标准化值",
    "direction_value": "方向调整值",
    "factor_direction": "因子方向",
    "rank_method": "排名方法",
    "forward_days": "未来天数",
    "avg_ic": "平均IC",
    "avg_rank_ic": "平均Rank IC",
    "ic_std": "IC标准差",
    "rank_ic_std": "Rank IC标准差",
    "ic_ir": "IC信息比",
    "rank_ic_ir": "Rank IC信息比",
    "positive_ic_ratio": "IC为正比例",
    "positive_rank_ic_ratio": "Rank IC为正比例",
    "avg_top_group_return": "顶部组平均收益",
    "avg_bottom_group_return": "底部组平均收益",
    "avg_group_spread": "分组收益差",
    "trade_date_count": "交易日数量",
    "rank_in_strategy": "策略内排名",
    "composite_score": "综合得分",
    "factor_count": "因子数量",
    "selected_reason": "入选原因",
    "universe_name": "股票范围",
    "initial_cash": "初始资金",
    "portfolio_return": "组合收益率",
    "holding_count": "持仓数量",
    "equity": "资金曲线",
    "weight": "持仓权重",
    "rebalance_date": "调仓日期",
    "start_date": "开始日期",
    "end_date": "结束日期",
    "initial_equity": "初始权益",
    "final_equity": "最终权益",
    "total_return": "总收益率",
    "annualized_return": "年化收益率",
    "annualized_volatility": "年化波动率",
    "max_drawdown": "最大回撤",
    "sharpe_ratio": "夏普比率",
    "calmar_ratio": "卡玛比率",
    "win_rate": "胜率",
    "avg_daily_return": "平均日收益",
    "best_daily_return": "最佳日收益",
    "worst_daily_return": "最差日收益",
    "trading_days": "交易天数",
    "risk_free_rate": "无风险利率",
    "running_max_equity": "历史最高权益",
    "drawdown": "回撤",
    "year_month": "月份",
    "monthly_return": "月度收益率",
    "year": "年份",
    "yearly_return": "年度收益率",
    "score_rank": "评分排名",
    "percentile_score": "百分位得分",
    "expected_factor_count": "应有因子数",
    "available_factor_count": "可用因子数",
    "missing_factor_count": "缺失因子数",
    "factor_coverage_ratio": "因子覆盖率",
    "factor_score": "因子得分",
    "factor_weight": "因子权重",
    "weighted_score": "加权得分",
    "factor_rank_value": "因子排名",
    "factor_percentile_rank": "因子百分位排名",
    "repair_action": "修复动作",
    "adj_type": "复权类型",
    "status": "状态",
    "affected_rows": "影响行数",
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "issue_type": "问题类型",
    "issue_level": "问题等级",
    "issue_detail": "问题详情",
}

# ── Factor name translations ───────────────────────────────────────────────
FACTOR_CN = {
    "return_1d": "1日收益率", "return_5d": "5日收益率", "return_10d": "10日收益率",
    "return_20d": "20日收益率", "return_60d": "60日收益率",
    "momentum_5d": "5日动量", "momentum_10d": "10日动量", "momentum_20d": "20日动量", "momentum_60d": "60日动量",
    "ma5": "5日均线", "ma10": "10日均线", "ma20": "20日均线", "ma60": "60日均线", "ma120": "120日均线",
    "close_ma5_ratio": "收盘/MA5", "close_ma10_ratio": "收盘/MA10", "close_ma20_ratio": "收盘/MA20",
    "close_ma60_ratio": "收盘/MA60", "close_ma120_ratio": "收盘/MA120",
    "volatility_5d": "5日波动率", "volatility_10d": "10日波动率", "volatility_20d": "20日波动率", "volatility_60d": "60日波动率",
    "volume_ma5": "5日均量", "volume_ma20": "20日均量", "volume_ma60": "60日均量",
    "volume_ratio_5_20": "5/20日量比", "volume_ratio_20_60": "20/60日量比",
    "amount_ma5": "5日均额", "amount_ma20": "20日均额", "amount_ma60": "60日均额",
    "turnover_ma5": "5日均换手", "turnover_ma20": "20日均换手", "turnover_ma60": "60日均换手", "turnover_ratio_5_20": "5/20日换手比",
    "high_20d": "20日最高", "low_20d": "20日最低", "price_position_20d": "20日价格位置",
    "high_60d": "60日最高", "low_60d": "60日最低", "price_position_60d": "60日价格位置",
}
COLUMN_CN.update(FACTOR_CN)

# ── Safe fetch helpers ──────────────────────────────────────────────────────

def safe_fetch_table_count(table_name: str) -> int:
    try:
        r = query_df(f"SELECT COUNT(*) AS c FROM {table_name}")
        return int(r.iloc[0]["c"]) if not r.empty else 0
    except Exception:
        return 0

def safe_fetch_latest_date(table_name: str, date_col: str = "trade_date") -> str | None:
    try:
        r = query_df(f"SELECT MAX({date_col}) AS d FROM {table_name}")
        if r.empty: return None
        val = r.iloc[0]["d"]
        return str(val)[:10] if val else None
    except Exception:
        return None

def safe_fetch_sample(table_name: str, limit: int = DEFAULT_DISPLAY_LIMIT) -> pd.DataFrame:
    try:
        return query_df(f"SELECT * FROM {table_name} LIMIT {int(limit)}")
    except Exception:
        return pd.DataFrame()

def safe_metric(label: str, table: str, default: str = "0") -> str:
    try:
        r = query_df(f"SELECT COUNT(*) AS c FROM {table}")
        return str(int(r.iloc[0]["c"])) if not r.empty else default
    except Exception:
        return default

# ── Display helpers ─────────────────────────────────────────────────────────

def add_stock_name(df: pd.DataFrame) -> pd.DataFrame:
    """Left-join stock_pool to add stock_name column."""
    if df is None or df.empty or "stock_code" not in df.columns:
        return df
    try:
        pool = query_df("SELECT stock_code, stock_name FROM stock_pool")
        if pool.empty: return df
        df = df.copy()
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
        pool["stock_code"] = pool["stock_code"].astype(str).str.zfill(6)
        if "stock_name" not in df.columns:
            df = df.merge(pool, on="stock_code", how="left")
            df["stock_name"] = df["stock_name"].fillna("")
    except Exception:
        pass
    return df

def translate_factor_name(df: pd.DataFrame) -> pd.DataFrame:
    """Translate factor_name column using FACTOR_CN map."""
    if df is None or df.empty or "factor_name" not in df.columns:
        return df
    df = df.copy()
    df["factor_name"] = df["factor_name"].map(FACTOR_CN).fillna(df["factor_name"])
    return df

def translate_display_values(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    maps = {
        "is_active": {True: "启用", False: "停用", 1: "启用", 0: "停用"},
        "is_blacklisted": {True: "黑名单", False: "正常", 1: "黑名单", 0: "正常"},
        "adj_type": {"raw": "不复权", "qfq": "前复权", "all": "全部"},
        "status": {
            "success": "成功",
            "failed": "失败",
            "dry_run": "预演",
            "skipped": "跳过",
            "pending": "待处理",
            "open": "待处理",
            "closed": "已关闭",
        },
        "repair_action": {
            "plan": "生成计划",
            "deduplicate": "去重",
            "refetch": "重拉数据",
            "rebuild-parquet": "重建Parquet",
            "auto": "自动",
        },
    }
    for col, mapping in maps.items():
        if col in df.columns:
            df[col] = df[col].map(mapping).fillna(df[col])
    return df

def rename_columns_cn(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    return df.rename(columns={c: COLUMN_CN.get(c, c) for c in df.columns})

def format_display_df(df: pd.DataFrame, cols: list[str] | None = None) -> pd.DataFrame:
    """Add stock name, translate factors, select display columns in order."""
    if df is None or df.empty: return df
    df = add_stock_name(df)
    df = translate_factor_name(df)
    df = translate_display_values(df)
    # Move stock_name right after stock_code
    if "stock_name" in df.columns and "stock_code" in df.columns:
        ordered = []
        for c in df.columns:
            if c == "stock_name": continue
            ordered.append(c)
            if c == "stock_code": ordered.append("stock_name")
        df = df[[c for c in ordered if c in df.columns]]
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    df = rename_columns_cn(df)
    return df

def show_table(df: pd.DataFrame, cols: list[str] | None = None, height: int = 350, key: str = ""):
    """Formatted table display with Chinese labels and stock names."""
    df = format_display_df(df, cols)
    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True, height=height, key=key, selection_mode="single-row", on_select="ignore")
    else:
        st.info("暂无数据")

def show_empty(msg: str = "暂无数据"):
    st.info(msg)

def render_cmd(commands: str):
    st.code(commands, language="bash")
