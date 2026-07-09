# A 股 AI 投研决策系统

面向 A 股的个人 AI 投研决策辅助系统。系统自动整理市场环境、情绪周期、板块强度、主线板块和板块问诊结果，生成每日决策卡。

> 系统**不自动实盘下单**，**不输出具体股票买卖建议**。所有判断为"建议观察"性质，最终决策由用户确认。

---

## 当前版本：V1.6.3（买卖条件引擎）

V1.5 系列已形成完整的最小投研闭环：从市场环境 → 情绪周期 → 板块映射 → 板块强度 → 主线识别 → 板块问诊，最终汇聚为每日决策卡。

### V1.5 各版本能力一览

| 版本 | 能力 | 入口 |
|------|------|------|
| V1.5.0 | 最小投研决策闭环骨架 | `src/decision/daily_decision_card.py` |
| V1.5.1 | 市场环境判断：attack / neutral / defense / high_risk | `src/market/market_environment.py` |
| V1.5.2 | 情绪周期判断：ice_point → climax → retreat 共 8 阶段 | `src/sentiment/sentiment_cycle.py` |
| V1.5.3 | 板块基础数据 + 股票板块映射（DuckDB 2 张表） | `src/sector/sector_service.py` |
| V1.5.4 | 板块强度计算：3/5/10/20 日收益 + 排名 | `src/sector/sector_strength.py` |
| V1.5.5 | 主线板块识别：confirmed / potential / one_day / cooling / high_risk | `src/sector/sector_mainline.py` |
| V1.5.6 | 板块问诊：聚合市场+情绪+强度+主线的诊断卡片 | `src/sector/sector_diagnosis.py` |
| V1.5.7 | 全A股主路径：去core500默认化，新增统一同步入口 | `src/data_update/all_a_recent_sync.py` |
| V1.5.8 | 深色科技风AI投研驾驶舱 + PostgreSQL移除 | `ui/streamlit_app.py` (5 Tab) |

### V1.6 系列：龙头、机会指数、买卖条件

| 版本 | 能力 | 入口 |
|------|------|------|
| V1.6.1 | 板块龙头识别：一号/二号/补涨/伪龙头/高风险追高 | `src/leader/sector_leader.py` |
| V1.6.2 | 目标收益机会指数：6维加权评分 | `src/opportunity/opportunity_index.py` |
| V1.6.3 | 买卖条件引擎：8类条件+权限摘要 | `src/conditions/condition_engine.py` |

---

## 今日决策卡

V1.5 的核心输出入口，聚合所有模块的判断：

```python
from src.decision.daily_decision_card import build_daily_decision_card

card = build_daily_decision_card("2026-07-09")
data = card.as_dict()

# 输出包含:
# - market_environment     → V1.5.1 市场环境
# - sentiment_cycle_v2     → V1.5.2 情绪周期
# - sentiment_snapshot     → V1.5.0 兼容
# - sector_snapshot        → V1.5.0 板块概览
# - overall_bias           → 综合倾向 (defensive/neutral/aggressive)
# - risk_warnings          → 风险提示
# - suggested_actions      → 建议动作
```

---

## 核心模块调用示例

### 市场环境判断 (V1.5.1)

```python
from src.market.market_environment import build_market_environment
env = build_market_environment("2026-07-08")
print(env.market_state)  # attack / neutral / defense / high_risk / unknown
print(env.action_hint)   # 中文建议
```

CLI：`python -m src.market.market_environment --date 2026-07-08 --json`

### 情绪周期判断 (V1.5.2)

```python
from src.sentiment.sentiment_cycle import build_sentiment_cycle
cycle = build_sentiment_cycle("2026-07-08")
print(cycle.sentiment_cycle)  # ice_point / repair / warming / climax / cooling / retreat / chaotic / unknown
print(cycle.sentiment_score)  # 0-100
print(cycle.action_hint)      # 中文建议
```

CLI：`python -m src.sentiment.sentiment_cycle --date 2026-07-08 --json`

### 板块查询 (V1.5.3)

```python
from src.sector.sector_service import get_sectors_by_stock, get_stocks_by_sector

r = get_sectors_by_stock("000001")
print(r.sectors)  # [{sector_code, sector_name, sector_type, ...}]

r = get_stocks_by_sector(sector_name="银行")
print(r.stocks)   # [{stock_code, stock_name, ...}]
```

同步板块数据（须先于强度/主线/问诊使用）：

```bash
python -m src.sector.sector_sync --sync-basic --source akshare --confirm
python -m src.sector.sector_sync --sync-map --source akshare --confirm
```

### 板块强度 (V1.5.4)

```python
from src.sector.sector_strength import calculate_sector_strength, get_sector_rank

r = calculate_sector_strength("2026-07-09", sector_name="机器人")
print(r.strength_score, r.strength_level, r.return_5d)

ranking = get_sector_rank("2026-07-09", top_n=20)
```

CLI：`python -m src.sector.sector_strength --date 2026-07-09 --rank --top-n 20`

### 主线识别 (V1.5.5)

```python
from src.sector.sector_mainline import build_mainline_snapshot

snap = build_mainline_snapshot("2026-07-09")
print(snap.has_clear_mainline)
print(snap.confirmed_mainlines)
print(snap.market_mainline_summary)
```

CLI：`python -m src.sector.sector_mainline --date 2026-07-09 --snapshot`

### 板块问诊 (V1.5.6)

```python
from src.sector.sector_diagnosis import diagnose_sector_by_name

d = diagnose_sector_by_name("2026-07-09", sector_name="机器人")
print(d.diagnosis_status)           # healthy / watch / cautious / ...
print(d.action_hint)                # 中文建议
print(d.observation_conditions)      # 观察条件
print(d.invalidation_conditions)     # 失效条件
```

CLI：`python -m src.sector.sector_diagnosis --date 2026-07-09 --sector 机器人`

---

## 当前限制

1. **不做具体龙头识别** — `leader_structure` 固定为 `pending_v1.6.1`
2. **不输出具体股票买卖建议** — 所有 `suggested_action` 仅为"观察/关注/等待"级别
3. **不自动实盘交易** — 系统不接任何交易接口
4. **部分指标为近似计算**：
   - 涨跌停：`pct_chg >= 9.8` 近似（标记 `approximate_limit_up`）
   - 晋级率：基于连续近似涨停计算（标记 `approximate_promotion_rate`）
   - 炸板率：无法计算（无分时数据），永远在 `missing_indicator_names` 中
   - 基准指数：使用全市场样本等权平均替代（无指数行情表）
5. **数据不足时优雅降级** — 输出 `unknown` 或空列表，不崩溃

---

## 安装与测试

### 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # Linux / macOS
pip install -r requirements.txt
cp .env.example .env
```

### 运行测试

```bash
python -m pytest tests/ -q        # 全量测试 (1023+ passed)

# 按模块单独测试
python -m pytest tests/test_market_environment.py -q   # V1.5.1: 26 tests
python -m pytest tests/test_sentiment_cycle.py -q      # V1.5.2: 38 tests
python -m pytest tests/test_sector_mapping.py -q       # V1.5.3: 25 tests
python -m pytest tests/test_sector_strength.py -q      # V1.5.4: 17 tests
python -m pytest tests/test_sector_mainline.py -q      # V1.5.5: 20 tests
python -m pytest tests/test_sector_diagnosis.py -q     # V1.5.6: 21 tests
python -m pytest tests/test_daily_decision_card.py -q  # 决策卡集成
```

---

## 数据与密钥安全

### 不提交 GitHub 的文件

- `.env` — 环境变量（含 token / password）
- `data/duckdb/*.duckdb` — DuckDB 本地数据库
- `data/parquet/` — Parquet 行情数据
- `data/meta/*.db` — Meta DB fallback
- `logs/` — 应用日志
- `streamlit.log` — Streamlit 日志

### 密钥配置

- 使用 `.env` 环境变量，参考 `.env.example`
- `TUSHARE_TOKEN` 等密钥通过环境变量注入，不写死在代码中
- `.gitignore` 已保护所有数据目录和日志文件

---

## 服务器部署

```bash
# 1. 拉取代码
git pull origin main

# 2. 安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 配置环境
cp .env.example .env
# 编辑 .env，填入必要的 token（TUSHARE_TOKEN 可选）

# 4. 运行全量测试
python -m pytest tests/ -q

# 5. 初始化数据库（首次部署）
python -c "from src.storage.duckdb_repo import init_database; init_database()"

# 6. 同步板块基础数据（须先于板块强度/主线/问诊）
python -m src.sector.sector_sync --sync-basic --source akshare --confirm
python -m src.sector.sector_sync --sync-map --source akshare --confirm

# 7. Smoke test — 调用今日决策卡
python -c "
from src.decision.daily_decision_card import build_daily_decision_card
print(build_daily_decision_card())
"
```

---

## 下一步计划 (V1.6 系列)

| 版本 | 计划 | 状态 |
|------|------|------|
| V1.6.1 | 板块龙头识别（填补 `leader_structure` 字段） | 规划中 |
| V1.6.2 | 目标收益机会指数 | 规划中 |
| V1.6.3 | 买卖条件引擎 | 规划中 |

---

## 项目目录结构（V1.5 重点模块）

```text
quant-a-share-platform/
├── src/
│   ├── decision/
│   │   └── daily_decision_card.py    # V1.5 今日决策卡聚合入口
│   ├── market/                        # V1.5.1 市场环境判断
│   │   ├── market_environment.py      # 编排器 + CLI
│   │   ├── market_indicators.py       # 样本指标计算
│   │   ├── market_types.py            # 枚举 + dataclass
│   │   └── market_state.py            # V1.5.0 兼容
│   ├── sentiment/                     # V1.5.2 情绪周期判断
│   │   ├── sentiment_cycle.py         # 编排器 + CLI + V1.5.0 兼容
│   │   ├── sentiment_indicators.py    # 情绪指标计算 (30+ 指标)
│   │   └── sentiment_types.py         # 枚举 + dataclass
│   ├── sector/                        # V1.5.3-1.5.6 板块全链路
│   │   ├── sector_types.py            # 板块映射类型
│   │   ├── sector_repository.py       # DuckDB CRUD
│   │   ├── sector_service.py          # 查询 API
│   │   ├── sector_sync.py             # AkShare 同步 + CLI
│   │   ├── sector_strength_types.py   # 强度类型
│   │   ├── sector_strength.py         # 强度计算 + CLI
│   │   ├── sector_mainline_types.py   # 主线类型
│   │   ├── sector_mainline.py         # 主线识别 + CLI
│   │   ├── sector_diagnosis_types.py  # 问诊类型
│   │   ├── sector_diagnosis.py        # 问诊编排 + CLI
│   │   └── sector_snapshot.py         # V1.5.0 兼容
│   ├── rules/                         # 规则引擎（权重集中管理）
│   │   ├── market_environment_rules.py     # V1.5.1 市场规则
│   │   ├── sentiment_cycle_rules.py        # V1.5.2 情绪规则
│   │   ├── sector_strength_rules.py        # V1.5.4 强度评分
│   │   ├── sector_mainline_rules.py        # V1.5.5 主线分类
│   │   ├── sector_diagnosis_rules.py       # V1.5.6 问诊聚合
│   │   └── basic_decision_rules.py         # V1.5.0 基础决策
│   └── storage/
│       ├── duckdb_repo.py              # DuckDB 统一入口
│       └── schema.py                   # 40 张表 DDL (含 V1.5.3 新增)
├── tests/
│   ├── test_market_environment.py      # 26 tests
│   ├── test_sentiment_cycle.py         # 38 tests
│   ├── test_sector_mapping.py          # 25 tests
│   ├── test_sector_strength.py         # 17 tests
│   ├── test_sector_mainline.py         # 20 tests
│   ├── test_sector_diagnosis.py        # 21 tests
│   └── test_daily_decision_card.py     # 决策卡集成
└── config/
    └── settings.py                     # 项目路径配置 (.env 驱动)
```

---

## 技术栈

- Python 3.11+
- **DuckDB** — 行情数据、板块数据、因子、回测（主力分析引擎）
- **SQLite** — 元数据、任务状态、日志、决策卡（业务小表）
- **Parquet** — 数据湖备份
- pandas / numpy
- akshare（外部数据源）
- streamlit / plotly（可视化）
- pytest（测试框架）

---

## 免责声明

本项目仅用于个人研究和学习，不构成任何投资建议，不进行自动交易，不保证任何收益。

---

## 历史版本归档

<details>
<summary>V1.5.1 市场环境判断（点击展开）</summary>

V1.5.1 从 `stock_daily_raw` 聚合计算市场指标，通过规则引擎输出 `attack / neutral / defense / high_risk / unknown`。

- 入口：`src/market/market_environment.py`
- CLI：`python -m src.market.market_environment --date YYYY-MM-DD --json`
- 测试：26 tests

</details>

<details>
<summary>V1.5.0 最小投研决策闭环骨架（点击展开）</summary>

V1.5.0 建立了每日投研决策卡的最小骨架：市场状态（保守 unknown-by-default）、情绪周期、板块快照、决策规则层。

- `market_state` / `sentiment_cycle` 始终 unknown（V1.5.0 无真实数据）
- suggested_actions 白名单机制，禁止出现"买入/卖出"等词汇
- overall_bias 最高只到 neutral

</details>

<details>
<summary>V1.4.x 数据基础设施（点击展开）</summary>

V1.4 系列完成了数据层基础设施建设：
- V1.4.1：多数据源 Provider 架构（LocalCache / MiniQMT / Tushare / AkShare）+ PostgreSQL 元数据库
- V1.4.2：全市场证券主数据、交易日历、历史数据任务队列
- V1.4.3：数据覆盖率报告、缺口识别、小样本补数验证
- V1.4.4：小样本真实回填验证、本地保存链路
- V1.4.5：core_50/core_100 小批量补数
- V1.4.6：真实交易日历（AkShare sina）、证券主数据增强
- V1.4.7：core_500 分批补数准备与批次管理
- V1.4.8：core_500 小规模真实执行与批次恢复
- V1.4.9：Streamlit backfill batch 页面

</details>

<details>
<summary>V0.x-V1.3 量化研究平台（点击展开）</summary>

- V0.1-V0.6：项目骨架、股票池管理、历史数据初始化、增量更新、数据质量、数据修复
- V0.7：42 个基础因子计算
- V0.8：因子标准化与排名
- V0.9：因子有效性分析（IC/RankIC/分组收益）
- V1.0：TopK 选股策略
- V1.1：基础回测引擎
- V1.2：回测评价体系（夏普、最大回撤、月度/年度收益）
- V1.3：多因子评分系统
- V1.4：Streamlit 可视化平台升级

</details>
