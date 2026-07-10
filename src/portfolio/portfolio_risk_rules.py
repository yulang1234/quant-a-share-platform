"""V1.7.3 portfolio risk rules — thresholds, weights, scoring and classification.

All thresholds and weights are centralized here.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.portfolio.portfolio_risk_types import (
    CorrelationPair,
    PortfolioPermission,
    PortfolioRiskLevel,
    PortfolioRiskResult,
    RiskDimension,
    SectorExposure,
    clamp_score,
)

RULE_VERSION = "v1.7.3"

RISK_WEIGHTS: dict[str, float] = {
    "single_position": 0.20,
    "sector_concentration": 0.20,
    "market_exposure": 0.20,
    "correlation": 0.15,
    "drawdown": 0.15,
    "consecutive_loss": 0.05,
    "position_diagnosis": 0.05,
}

# ── Total position ───────────────────────────────────────────────────────────


def calculate_total_position_pct(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate total position percentage from active positions."""
    issues: list[str] = []
    total = 0.0
    for p in positions:
        pct = p.get("position_pct")
        if pct is None:
            issues.append(f"{p.get('stock_code', '?')} 仓位百分比缺失")
            continue
        try:
            total += float(pct)
        except (ValueError, TypeError):
            issues.append(f"{p.get('stock_code', '?')} 仓位百分比非法")

    cash = None
    if 0 <= total <= 100:
        cash = round(100 - total, 1)

    return {"total_position_pct": round(total, 1), "cash_pct": cash, "issues": issues}


# ── Single position risk ─────────────────────────────────────────────────────


def evaluate_single_position_risk(positions: list[dict[str, Any]]) -> RiskDimension:
    dim = RiskDimension(name="single_position", weight=RISK_WEIGHTS["single_position"])
    if not positions:
        dim.issues.append("无持仓数据")
        return dim

    max_pct = 0.0
    max_code = ""
    for p in positions:
        pct = float(p.get("position_pct", 0) or 0)
        if pct > max_pct:
            max_pct = pct
            max_code = p.get("stock_code", "")

    if max_pct < 10:
        dim.risk_score = max(0, max_pct * 1.5)
        dim.risk_level = "low"
    elif max_pct < 15:
        dim.risk_score = 15 + (max_pct - 10) * 3
        dim.risk_level = "low"
    elif max_pct < 20:
        dim.risk_score = 30 + (max_pct - 15) * 4
        dim.risk_level = "medium"
    elif max_pct < 30:
        dim.risk_score = 50 + (max_pct - 20) * 2.5
        dim.risk_level = "high"
    else:
        dim.risk_score = 75 + min((max_pct - 30) * 1.5, 25)
        dim.risk_level = "critical"

    dim.current_value = f"{max_pct:.1f}%"
    dim.threshold = "15% / 20% / 30%"
    dim.reason = f"最大单股: {max_code} {max_pct:.1f}%"
    dim.evidence = [f"max_single={max_code}:{max_pct:.1f}%"]
    return dim


# ── Sector concentration ─────────────────────────────────────────────────────


def evaluate_sector_concentration_risk(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute sector exposures and concentration risk."""
    sector_map: dict[str, dict[str, Any]] = {}
    unknown_pct = 0.0

    for p in positions:
        sector = p.get("sector_name") or "__unknown__"
        pct = float(p.get("position_pct", 0) or 0)
        if sector == "__unknown__":
            unknown_pct += pct
        else:
            if sector not in sector_map:
                sector_map[sector] = {"total_pct": 0.0, "count": 0}
            sector_map[sector]["total_pct"] += pct
            sector_map[sector]["count"] += 1

    exposures: list[SectorExposure] = []
    max_pct = 0.0
    max_name = ""
    for name, data in sorted(sector_map.items(), key=lambda x: x[1]["total_pct"], reverse=True):
        level = "normal"
        tp = data["total_pct"]
        if tp > 50:
            level = "critical"
        elif tp > 40:
            level = "high"
        elif tp > 30:
            level = "medium"
        exposures.append(SectorExposure(
            sector_name=name, position_count=data["count"],
            total_position_pct=round(tp, 1), concentration_level=level,
        ))
        if tp > max_pct:
            max_pct = tp
            max_name = name

    if unknown_pct > 0:
        exposures.append(SectorExposure(
            sector_name="未知板块", position_count=0,
            total_position_pct=round(unknown_pct, 1), concentration_level="unknown",
        ))

    # Risk score
    dim = RiskDimension(name="sector_concentration", weight=RISK_WEIGHTS["sector_concentration"])
    if max_pct < 30:
        dim.risk_score = max(0, max_pct * 0.5)
        dim.risk_level = "low"
    elif max_pct < 40:
        dim.risk_score = 15 + (max_pct - 30) * 2
        dim.risk_level = "medium"
    elif max_pct < 50:
        dim.risk_score = 35 + (max_pct - 40) * 3
        dim.risk_level = "high"
    else:
        dim.risk_score = 65 + min((max_pct - 50) * 2, 35)
        dim.risk_level = "critical"

    dim.current_value = f"{max_pct:.1f}% ({max_name})"
    dim.threshold = "30% / 40% / 50%"
    dim.reason = f"最大板块: {max_name} {max_pct:.1f}%, 共{len(sector_map)}个板块"

    crowded_count = sum(1 for e in exposures if e.concentration_level in ("high", "critical"))

    return {
        "dimension": dim,
        "sector_exposures": exposures,
        "max_sector_pct": max_pct,
        "max_sector_name": max_name,
        "sector_count": len(sector_map),
        "crowded_sector_count": crowded_count,
    }


# ── Top3 concentration ───────────────────────────────────────────────────────


def calculate_top_n_concentration(positions: list[dict[str, Any]], n: int = 3) -> float:
    pcts = sorted(
        [float(p.get("position_pct", 0) or 0) for p in positions], reverse=True
    )
    return round(sum(pcts[:n]), 1)


# ── Market exposure risk ─────────────────────────────────────────────────────


def evaluate_market_exposure_risk(
    total_position_pct: float,
    market_context: dict[str, Any] | None,
    sentiment_context: dict[str, Any] | None,
) -> RiskDimension:
    dim = RiskDimension(name="market_exposure", weight=RISK_WEIGHTS["market_exposure"])
    market_state = (market_context or {}).get("market_state", "unknown")
    sentiment_cycle = (sentiment_context or {}).get("sentiment_cycle", "unknown")

    # Reference ceiling by market state
    ceiling_map = {"attack": 90, "neutral": 70, "defense": 40, "high_risk": 20, "unknown": 30}
    ceiling = ceiling_map.get(market_state, 30)

    # Sentiment adjustment
    sentiment_adj = {"repair": 0, "warming": 0, "rising": 0, "climax": -10,
                     "cooling": -15, "retreat": -25, "ice_point": -20, "chaotic": -15, "unknown": -20}
    adjustment = sentiment_adj.get(sentiment_cycle, -20)
    adjusted_ceiling = max(ceiling + adjustment, 0)

    excess = total_position_pct - adjusted_ceiling if total_position_pct > adjusted_ceiling else 0

    if excess <= 0:
        dim.risk_score = max(0, min(total_position_pct / adjusted_ceiling * 15, 15)) if adjusted_ceiling > 0 else 20
        dim.risk_level = "low"
    elif excess <= 15:
        dim.risk_score = 20 + excess * 2
        dim.risk_level = "medium"
    elif excess <= 30:
        dim.risk_score = 50 + (excess - 15) * 2
        dim.risk_level = "high"
    else:
        dim.risk_score = 80 + min((excess - 30) * 0.5, 20)
        dim.risk_level = "critical"

    dim.current_value = f"{total_position_pct:.1f}% (上限{adjusted_ceiling:.0f}%)"
    dim.threshold = f"市场{market_state}参考上限{ceiling}%"
    dim.reason = f"总仓位{total_position_pct:.1f}% vs 参考{adjusted_ceiling:.0f}% (市场={market_state}, 情绪={sentiment_cycle})"
    dim.evidence = [f"market={market_state}", f"sentiment={sentiment_cycle}", f"ceiling={adjusted_ceiling:.0f}"]
    return dim


# ── Correlation risk ─────────────────────────────────────────────────────────


def evaluate_correlation_risk(
    positions: list[dict[str, Any]],
    trade_date: str,
    lookback_days: int = 20,
) -> dict[str, Any]:
    """Compute pairwise Pearson correlation of daily returns."""
    pairs: list[CorrelationPair] = []
    dim = RiskDimension(name="correlation", weight=RISK_WEIGHTS["correlation"])

    if len(positions) <= 1:
        dim.risk_score = 0
        dim.risk_level = "low"
        dim.reason = "持仓数量≤1，相关性不适用"
        return {"dimension": dim, "correlation_pairs": pairs, "average": None, "max": None, "high_count": 0}

    # Fetch return series for each position
    returns: dict[str, np.ndarray] = {}
    issues: list[str] = []

    try:
        from src.storage.duckdb_repo import query_df

        for p in positions:
            code = p.get("stock_code", "")
            df = query_df(
                "SELECT trade_date, pct_change FROM stock_daily_raw "
                "WHERE stock_code = ? AND trade_date <= ? "
                "ORDER BY trade_date DESC LIMIT ?",
                [code, trade_date, lookback_days + 5],
            )
            if df is not None and not df.empty and len(df) >= 15:
                df = df.sort_values("trade_date", ascending=True)
                returns[code] = df["pct_change"].dropna().astype(float).values[-lookback_days:] / 100
            else:
                issues.append(f"{code} 有效交易日不足15天")
    except Exception as exc:
        issues.append(f"行情查询异常: {exc}")

    if len(returns) < 2:
        dim.risk_score = 0
        dim.risk_level = "unknown"
        dim.issues = issues
        return {"dimension": dim, "correlation_pairs": pairs, "average": None, "max": None, "high_count": 0}

    # Compute pairwise correlations
    codes = list(returns.keys())
    corr_values: list[float] = []
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            a, b = codes[i], codes[j]
            min_len = min(len(returns[a]), len(returns[b]))
            if min_len < 15:
                continue
            try:
                corr = float(np.corrcoef(returns[a][:min_len], returns[b][:min_len])[0, 1])
                if np.isnan(corr):
                    continue
                corr = round(corr, 3)
                corr_values.append(corr)
                rl = "low" if abs(corr) < 0.5 else "medium" if abs(corr) < 0.7 else "high" if abs(corr) < 0.85 else "critical"
                pairs.append(CorrelationPair(stock_a=a, stock_b=b, correlation=corr, risk_level=rl))
            except Exception:
                continue

    if not corr_values:
        dim.risk_score = 0
        dim.risk_level = "unknown"
        dim.issues = ["无有效相关性数据"]
        return {"dimension": dim, "correlation_pairs": pairs, "average": None, "max": None, "high_count": 0}

    avg_corr = round(float(np.mean(corr_values)), 3)
    max_corr = round(float(np.max(corr_values)), 3)
    high_count = sum(1 for c in corr_values if abs(c) >= 0.7)

    if avg_corr < 0.4:
        dim.risk_score = max(0, avg_corr * 30)
        dim.risk_level = "low"
    elif avg_corr < 0.6:
        dim.risk_score = 12 + (avg_corr - 0.4) * 90
        dim.risk_level = "medium"
    elif avg_corr < 0.75:
        dim.risk_score = 30 + (avg_corr - 0.6) * 200
        dim.risk_level = "high"
    else:
        dim.risk_score = 60 + min((avg_corr - 0.75) * 160, 40)
        dim.risk_level = "critical"

    if max_corr > 0.85:
        dim.risk_score = max(dim.risk_score, 75)

    dim.current_value = f"avg={avg_corr:.2f}, max={max_corr:.2f}"
    dim.threshold = "avg<0.4/low, 0.4-0.6/med, 0.6-0.75/high, >0.75/crit"
    dim.reason = f"平均相关性{avg_corr:.2f}, {high_count}对高相关"
    dim.issues = issues

    return {"dimension": dim, "correlation_pairs": pairs, "average": avg_corr, "max": max_corr, "high_count": high_count}


# ── Portfolio return series ──────────────────────────────────────────────────


def build_portfolio_return_series(
    positions: list[dict[str, Any]],
    trade_date: str,
    lookback_days: int = 60,
) -> dict[str, Any]:
    """Build approximate portfolio daily return series using current weights."""
    if not positions:
        return {"daily_returns": [], "cumulative": [], "issues": ["无持仓"]}

    # Normalize weights
    total_pct = sum(float(p.get("position_pct", 0) or 0) for p in positions)
    if total_pct <= 0:
        return {"daily_returns": [], "cumulative": [], "issues": ["仓位合计为0"]}

    weights = {p["stock_code"]: float(p.get("position_pct", 0) or 0) / total_pct for p in positions}

    try:
        from src.storage.duckdb_repo import query_df

        codes = list(weights.keys())
        placeholders = ",".join(["?"] * len(codes))
        df = query_df(
            f"SELECT stock_code, trade_date, pct_change FROM stock_daily_raw "
            f"WHERE stock_code IN ({placeholders}) AND trade_date <= ? "
            f"ORDER BY trade_date",
            codes + [trade_date],
        )
        if df is None or df.empty:
            return {"daily_returns": [], "cumulative": [], "issues": ["无行情数据"]}

        df["trade_date"] = pd_to_dates(df)
        df = df.sort_values("trade_date")
        dates = sorted(df["trade_date"].unique())[-lookback_days:]

        daily_returns: list[dict[str, Any]] = []
        for d in dates:
            day_data = df[df["trade_date"] == d]
            port_ret = 0.0
            valid_weight = 0.0
            for code, w in weights.items():
                row = day_data[day_data["stock_code"] == code]
                if not row.empty:
                    ret = float(row["pct_change"].iloc[0] or 0) / 100
                    port_ret += w * ret
                    valid_weight += w
            if valid_weight >= 0.5:
                daily_returns.append({"trade_date": str(d)[:10], "return": round(port_ret, 6),
                                      "coverage": round(valid_weight, 2)})

        cumulative = []
        cum = 1.0
        for dr in daily_returns:
            cum *= (1 + dr["return"])
            cumulative.append({"trade_date": dr["trade_date"], "cumulative": round(cum, 6)})

        return {"daily_returns": daily_returns, "cumulative": cumulative, "approx_current_weight": True, "issues": []}
    except Exception as exc:
        return {"daily_returns": [], "cumulative": [], "issues": [str(exc)]}


def pd_to_dates(df: Any) -> Any:
    import pandas as pd
    if "trade_date" in df.columns:
        try:
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        except Exception:
            pass
    return df


# ── Drawdown risk ────────────────────────────────────────────────────────────


def evaluate_portfolio_drawdown_risk(return_series: dict[str, Any]) -> dict[str, Any]:
    dim = RiskDimension(name="drawdown", weight=RISK_WEIGHTS["drawdown"])
    cumulative = return_series.get("cumulative", [])

    if not cumulative or len(cumulative) < 5:
        dim.risk_level = "unknown"
        dim.issues.append("组合收益数据不足，无法计算回撤")
        return {"dimension": dim, "dd_20d": None, "dd_60d": None}

    values = np.array([c["cumulative"] for c in cumulative])
    peak = np.maximum.accumulate(values)
    drawdowns = (values - peak) / peak * 100  # negative values

    dd_20d = abs(float(np.min(drawdowns[-20:]))) if len(drawdowns) >= 20 else abs(float(np.min(drawdowns)))
    dd_60d = abs(float(np.min(drawdowns))) if len(drawdowns) > 0 else None

    # Use worse of the two
    dd = dd_60d if dd_60d is not None else dd_20d

    if dd < 5:
        dim.risk_score = dd * 2
        dim.risk_level = "low"
    elif dd < 10:
        dim.risk_score = 10 + (dd - 5) * 4
        dim.risk_level = "medium"
    elif dd < 15:
        dim.risk_score = 30 + (dd - 10) * 6
        dim.risk_level = "high"
    else:
        dim.risk_score = 60 + min((dd - 15) * 2, 40)
        dim.risk_level = "critical"

    dim.current_value = f"20d={dd_20d:.1f}%, 60d={dd_60d:.1f}%"
    dim.threshold = "5% / 10% / 15%"
    dim.reason = f"组合最大回撤 20d={dd_20d:.1f}%, 60d={dd_60d:.1f}%"
    return {"dimension": dim, "dd_20d": round(dd_20d, 1), "dd_60d": round(dd_60d, 1) if dd_60d else None}


# ── Consecutive loss risk ────────────────────────────────────────────────────


def evaluate_consecutive_loss_risk(return_series: dict[str, Any]) -> RiskDimension:
    dim = RiskDimension(name="consecutive_loss", weight=RISK_WEIGHTS["consecutive_loss"])
    daily = return_series.get("daily_returns", [])

    if not daily:
        dim.risk_level = "unknown"
        dim.issues.append("组合收益数据不足")
        return dim

    streak = 0
    epsilon = 0.0001
    for dr in reversed(daily):
        if dr["return"] < -epsilon:
            streak += 1
        else:
            break

    if streak <= 2:
        dim.risk_score = streak * 5
        dim.risk_level = "low"
    elif streak <= 4:
        dim.risk_score = 10 + (streak - 2) * 10
        dim.risk_level = "medium"
    elif streak <= 6:
        dim.risk_score = 30 + (streak - 4) * 15
        dim.risk_level = "high"
    else:
        dim.risk_score = 60 + min((streak - 6) * 10, 40)
        dim.risk_level = "critical"

    dim.current_value = f"{streak}天"
    dim.threshold = "2 / 4 / 6天"
    dim.reason = f"连续亏损{streak}个交易日"
    return dim


# ── Diagnosis aggregation ────────────────────────────────────────────────────


def evaluate_position_diagnosis_risk(
    positions: list[dict[str, Any]],
    trade_date: str,
    diagnoses: list[dict[str, Any]] | None = None,
) -> RiskDimension:
    dim = RiskDimension(name="position_diagnosis", weight=RISK_WEIGHTS["position_diagnosis"])
    # If no diagnoses provided, try fetching
    if diagnoses is None:
        try:
            from src.portfolio.position_diagnosis_service import list_diagnoses
            diagnoses = list_diagnoses(trade_date=trade_date)
        except Exception:
            diagnoses = []

    dangerous = sum(1 for d in (diagnoses or []) if d.get("diagnosis_status") == "dangerous")
    cautious = sum(1 for d in (diagnoses or []) if d.get("diagnosis_status") == "cautious")
    unknown = sum(1 for d in (diagnoses or []) if d.get("diagnosis_status") == "unknown")
    exit_count = sum(1 for d in (diagnoses or []) if d.get("suggested_action") == "exit_conditionally")

    dim.current_value = f"dangerous={dangerous}, exit={exit_count}"
    dim.threshold = "dangerous=0, exit=0"

    if dangerous == 0 and exit_count == 0 and cautious == 0:
        dim.risk_score = 0
        dim.risk_level = "low"
    elif dangerous == 0:
        dim.risk_score = cautious * 20
        dim.risk_level = "medium"
    elif dangerous == 1:
        dim.risk_score = 50 + exit_count * 15
        dim.risk_level = "high"
    else:
        dim.risk_score = 75 + min((dangerous - 1) * 10, 25)
        dim.risk_level = "critical"

    dim.reason = f"dangerous={dangerous}, cautious={cautious}, unknown={unknown}, exit_condition={exit_count}"
    return dim


# ── Composite score ──────────────────────────────────────────────────────────


def compute_portfolio_risk_score(dimensions: list[RiskDimension]) -> tuple[float, float]:
    total_weight = sum(d.weight for d in dimensions)
    if total_weight <= 0:
        return (0.0, 0.0)

    weighted = sum(max(0, d.risk_score) * d.weight for d in dimensions)
    raw = weighted / total_weight

    valid_dims = sum(1 for d in dimensions if d.risk_level != "unknown")
    coverage = valid_dims / max(len(dimensions), 1)

    return (clamp_score(raw), round(coverage, 2))


def classify_risk_level(risk_score: float, coverage: float) -> str:
    if coverage < 0.45:
        return "unknown"
    if risk_score >= 75:
        return "critical"
    if risk_score >= 50:
        return "high"
    if risk_score >= 25:
        return "medium"
    return "low"


def apply_hard_risk_overrides(result: PortfolioRiskResult) -> PortfolioRiskResult:
    """Apply hard risk rules that override the computed level."""
    hard_high = any([
        result.total_position_pct > 100,
        result.max_single_position_pct > 30,
        result.max_sector_position_pct > 50,
        (result.portfolio_drawdown_60d or 0) > 15,
        result.dangerous_position_count >= 1,
    ])
    hard_critical = any([
        result.max_single_position_pct > 30 and result.max_sector_position_pct > 50,
        result.dangerous_position_count >= 2,
        result.total_position_pct > 100 and result.max_single_position_pct > 25,
        (result.portfolio_drawdown_60d or 0) > 15 and result.consecutive_loss_days >= 5,
    ])

    if hard_critical and result.portfolio_risk_level != "unknown":
        result.portfolio_risk_level = "critical"
        result.portfolio_risk_score = max(result.portfolio_risk_score, 80)
    elif hard_high and result.portfolio_risk_level not in ("critical", "unknown"):
        result.portfolio_risk_level = "high"
        result.portfolio_risk_score = max(result.portfolio_risk_score, 55)

    return result


# ── Permission ───────────────────────────────────────────────────────────────


def classify_portfolio_permission(result: PortfolioRiskResult) -> str:
    if result.data_coverage_ratio < 0.45:
        return "manual_review"

    if result.portfolio_risk_level == "critical":
        return "reduce_exposure_conditionally"

    if result.portfolio_risk_level == "high":
        return "reduce_exposure_conditionally" if result.dangerous_position_count >= 1 else "freeze_additions"

    if result.market_state in ("defense", "high_risk") and result.total_position_pct > 40:
        return "freeze_new_positions"

    if result.market_state == "high_risk" and result.total_position_pct > 20:
        return "freeze_new_positions"

    if result.portfolio_risk_level == "medium":
        return "watch"

    return "normal"


# ── Recommendations ──────────────────────────────────────────────────────────


def generate_risk_recommendations(result: PortfolioRiskResult) -> dict[str, Any]:
    flags: list[str] = []
    recs: list[str] = []
    obs: list[str] = []
    release: list[str] = []

    if result.max_single_position_pct > 25:
        flags.append(f"单股仓位集中 ({result.max_single_position_code} {result.max_single_position_pct:.1f}%)")
        recs.append("检查高集中个股")
        release.append(f"最大单股仓位 < 20%")

    if result.max_sector_position_pct > 40:
        flags.append(f"板块仓位集中 ({result.max_sector_name} {result.max_sector_position_pct:.1f}%)")
        recs.append("检查高集中板块")
        release.append(f"最大板块仓位 < 40%")

    if result.high_correlation_pair_count > 0:
        flags.append(f"持仓高度相关 ({result.high_correlation_pair_count}对)")
        recs.append("检查高相关持仓对，分散风险")
        release.append("高相关持仓对数量下降")

    if (result.portfolio_drawdown_60d or 0) > 10:
        flags.append(f"组合回撤偏大 (60d={result.portfolio_drawdown_60d:.1f}%)")
        recs.append("关注组合回撤修复情况")
        release.append("组合回撤 < 10%")

    if result.consecutive_loss_days >= 4:
        flags.append(f"连续亏损 ({result.consecutive_loss_days}天)")
        recs.append(f"已连续亏损{result.consecutive_loss_days}天，等待修复")
        release.append("连续亏损结束")

    if result.dangerous_position_count > 0:
        flags.append(f"存在{result.dangerous_position_count}只危险持仓")
        recs.append("人工复核危险持仓")
        release.append("无危险持仓")

    if result.total_position_pct > 100:
        flags.append("总仓位超过100%，数据异常")
        recs.append("检查仓位数据完整性")

    if result.market_state in ("defense", "high_risk"):
        flags.append(f"市场环境不支持高仓位 (market={result.market_state})")
        recs.append("等待市场环境改善后再考虑新增仓位")
        obs.append("市场从 defense/high_risk 转为 neutral/attack")
        release.append("市场环境改善")

    if result.data_coverage_ratio < 0.7:
        flags.append(f"数据覆盖率偏低 ({result.data_coverage_ratio:.0%})")
        recs.append("数据不足，暂不提高风险暴露")
        release.append("数据覆盖率恢复")

    return {
        "risk_flags": flags or ["暂无严重风险标记"],
        "recommendations": recs or ["组合风险可控"],
        "observation_conditions": obs or ["持续监控组合风险变化"],
        "risk_release_conditions": release or ["无特殊解除条件"],
    }
