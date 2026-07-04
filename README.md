# Quant A-Share Research Platform

面向 A 股 500 支核心股票池的个人量化研究平台。

## 项目定位

这是一个面向 A 股的个人量化研究平台，第一阶段以 500 支核心股票为研究对象，后续会逐步支持历史数据初始化、每日增量更新、数据质量检查、因子计算、评分、回测、Qlib 研究和 AI 分析报告。

## 当前版本状态

- V0.1 项目骨架：完成
- V0.2 股票池管理：完成
- V0.3 20 年历史数据初始化：完成
- V0.4 每日增量更新：完成
- V0.5 数据质量检查：完成
- V0.5.1 板块/行业自动获取 & 多源补齐：完成
- V0.6 数据修复与重跑：完成
- V0.7 基础因子计算：完成
- V0.8 因子标准化与排名：完成
- V0.9 因子有效性分析：完成
- V1.0 TopK 选股策略：完成
- V1.1 基础回测引擎：完成
- V1.2 回测评价体系：完成
- V1.3 多因子评分系统：完成
- V1.4 Streamlit 可视化平台升级：完成

## V1.4 已完成内容

V1.4 整理 Streamlit 页面为统一量化研究平台：项目总览、数据中心、因子研究、TopK选股、回测、评分、命令手册、风险提示。
页面只展示已有结果，不执行全量任务。所有结果不构成投资建议。

### 启动可视化平台
```bash
streamlit run ui/streamlit_app.py
```

安全说明：
- V1.4 只做 Streamlit 可视化平台升级
- 页面只展示已有结果，不直接执行全量计算
- 页面不调用 AkShare、不写 Parquet
- 页面不修改原始行情、因子、策略、回测、评分结果表
- V1.5 才做每日任务流水线
- 所有结果仅用于个人量化研究，不构成投资建议

### 测试
- pytest: 537 passed

## V1.3 已完成内容

V1.3 基于 V0.8 排名和 V0.9 分析，实现可配置多因子综合评分（percentile_rank 加权）。
支持因子有效性过滤和覆盖度统计。不构成投资建议。

### 多因子评分系统
```bash
python -m src.scoring.run_scoring --model momentum_quality_score --limit 5
python -m src.scoring.run_scoring --model trend_volume_score --limit 5
python -m src.scoring.run_scoring --model low_vol_stable_score --trade-date 20260703
```
说明：V1.3 只做多因子综合评分 / V1.4 做可视化升级 / V1.5 做每日任务 / 不调 AkShare / 不写 Parquet。pytest: 533 passed.

## V1.2 已完成内容

V1.2 基于 V1.1 回测生成的每日收益和资金曲线，计算绩效指标、回撤序列、月度收益和年度收益。
本版本只做回测评价体系，不做多因子评分系统，不调用 AkShare，不写 Parquet，不修改 V1.1 基础回测结果。

### 回测评价体系
```bash
python -m src.backtest_evaluation.run_backtest_evaluation --backtest-name single_return_20d_top20_bt

python -m src.backtest_evaluation.run_backtest_evaluation --backtest-name single_return_20d_top20_bt --risk-free-rate 0.02

python -m src.backtest_evaluation.run_backtest_evaluation --backtest-name single_return_20d_top20_bt --start-date 20200101 --end-date 20231231
```

说明：V1.2 默认读取 backtest_daily_return 和 backtest_equity_curve；V1.2 只做回测评价指标；V1.3 才做多因子评分系统；不调用 AkShare；不写 Parquet；不修改 V1.1 基础回测结果；回测结果不构成投资建议。

## V1.1 已完成内容

V1.1 基于 V1.0 候选股和 qfq 价格，实现基础回测：持仓→每日收益→资金曲线。
V1.2 负责夏普、最大回撤等回测评价指标。

### 基础回测引擎
```bash
python -m src.backtest.run_backtest --strategy single_return_20d_top20 --limit 5
python -m src.backtest.run_backtest --strategy single_return_20d_top20 --initial-cash 500000 --top-k 10 --rebalance-frequency weekly --limit 5
python -m src.backtest.run_backtest --strategy single_return_20d_top20 --start-date 20200101 --end-date 20231231
```
说明：V1.1 只做基础回测 / V1.2 做评价指标 / 不构成投资建议。

## V1.0 已完成内容

V1.0 基于 V0.8 排名和 V0.9 有效性分析，实现单因子/多因子加权 TopK 候选股票生成。
本版本只生成候选股票，不做回测、资金曲线、交易。

### TopK 选股策略
```bash
# 默认单因子策略
python -m src.strategy.run_topk_strategy --strategy single_return_20d_top20 --limit 5

# 临时单因子
python -m src.strategy.run_topk_strategy --factor-name return_20d --top-k 20 --limit 5

# 临时多因子
python -m src.strategy.run_topk_strategy --factor-weights "{\"return_20d\":0.5,\"momentum_20d\":0.5}" --top-k 20 --limit 5
```
说明：V1.0 只生成候选股票 / V1.1 才做回测 / 不构成投资建议 / 不调 AkShare / 不写 Parquet

### 测试
- pytest: 492 passed

## V0.9 已完成内容

V0.9 基于 V0.7 因子数据与 V0.8 排名数据，进行 IC/RankIC/分组收益/有效性汇总。

### 因子有效性分析
```bash
# 小批量因子有效性分析
python -m src.factor_analysis.run_factor_analysis --pool core_500 --limit 5

# 指定因子分析
python -m src.factor_analysis.run_factor_analysis --factor-name return_20d --forward-days 5 --limit 5

# 指定日期范围和未来收益周期
python -m src.factor_analysis.run_factor_analysis --factor-name return_20d --start-date 20200101 --end-date 20231231 --forward-days 10
```

说明：V0.9 只做因子有效性分析 / V1.0 才做 TopK 选股 / 不调用 AkShare / 不写 Parquet / 不修改原始数据

### 测试
- pytest: 467 passed（含 V0.9 分析测试）

## V0.8 已完成内容

V0.8 基于 V0.7 的因子数据，进行横截面去极值、z-score 标准化、方向处理与排名。

### 因子标准化与排名
```bash
# 小批量计算因子排名
python -m src.factor_rank.run_factor_ranking --pool core_500 --limit 5

# 指定因子排名
python -m src.factor_rank.run_factor_ranking --factor-name return_20d --limit 5

# 指定交易日排名
python -m src.factor_rank.run_factor_ranking --trade-date 20260703

# 指定日期范围
python -m src.factor_rank.run_factor_ranking --start-date 20260101 --end-date 20260703 --limit 5
```

说明：
- V0.8 默认读取 `stock_daily_factors`
- V0.8 只做标准化与排名，结果写入 `stock_factor_rank`
- V0.9 才做因子有效性分析
- 不调用 AkShare / 不写 Parquet / 不修改原始数据

### 测试
- pytest: 454 passed（含 V0.8 排名测试）

## V0.7 已完成内容

V0.7 基于 V0.3/V0.4 落库的 qfq 日线数据，计算 42 个基础量化因子并写入 DuckDB。

本版本只做因子计算，不做标准化、排名、有效性分析。

### 基础因子计算
```bash
# 小批量计算基础因子
python -m src.factors.run_factor_calculation --pool core_500 --limit 5

# 单只股票计算基础因子
python -m src.factors.run_factor_calculation --stock-code 000001

# 指定日期范围计算
python -m src.factors.run_factor_calculation --stock-code 000001 --start-date 20200101 --end-date 20231231
```

说明：
- V0.7 默认使用 qfq 前复权日线数据
- V0.7 只计算基础因子，结果写入 `stock_daily_factors`
- 没有 qfq 数据时会 skipped
- V0.8 才做因子标准化与排名
- V0.9 才做因子有效性分析
- 不写 Parquet
- 不调用 AkShare
- 不修改 `stock_daily_qfq` / `stock_daily_raw` 原始行情数据

### 测试
- pytest: 425 passed（含 V0.7 因子测试）

## V0.6 已完成内容

V0.6 基于 V0.5 的 `data_quality_report` 结果，提供安全、可控、可追踪的数据修复与重跑能力。

### 安全机制
- **dry-run 默认开启**：所有命令默认只预览，不修改数据
- **--confirm 保护**：真实执行必须同时传 `--confirm`
- **repair log 全记录**：所有操作（含 dry-run/skipped）写入 `data_repair_log`
- **不默认全量**：limit 参数限制修复范围

### 核心模块
- `repair_planner`: 从质量报告生成修复计划
- `duplicate_repair`: 清理 stock_code+trade_date 重复数据
- `date_range_repair`: 按日期区间重拉 AkShare 数据
- `parquet_repair`: 从 DuckDB 重建 Parquet 文件
- `repair_log`: 修复日志读写与汇总

### CLI
```bash
# dry-run 计划
python -m src.data_repair.run_data_repair --pool core_500 --limit 5 --action plan --dry-run

# dry-run 去重
python -m src.data_repair.run_data_repair --pool core_500 --limit 5 --action deduplicate --adj all --dry-run

# 真实去重（需同时 --no-dry-run --confirm）
python -m src.data_repair.run_data_repair --pool core_500 --limit 5 --action deduplicate --adj all --no-dry-run --confirm

# dry-run 重拉区间
python -m src.data_repair.run_data_repair --pool core_500 --stock-code 000001 --adj raw --action refetch --start-date 20260701 --end-date 20260703 --dry-run

# 真实重拉
python -m src.data_repair.run_data_repair --pool core_500 --stock-code 000001 --adj raw --action refetch --start-date 20260701 --end-date 20260703 --no-dry-run --confirm

# 真实重建 Parquet
python -m src.data_repair.run_data_repair --pool core_500 --stock-code 000001 --adj all --action rebuild-parquet --no-dry-run --confirm
```

### 测试
- pytest: 383 passed（含 36 个 V0.6 测试）
- 所有外部 API 调用在测试中 mock
- dry-run 默认保护数据安全

## V0.5 已完成内容

- 数据质量检查模块：对已经落库的日线数据执行基础检查
- 重复数据检查：`stock_code + trade_date` 维度检测重复记录
- 缺失交易日检查：基于自然日间隔检测日期缺口
- 价格异常检查：`open/high/low/close/volume/amount` 基础规则校验
- 质量报告汇总：`data_quality_report` 表写入与查询
- 命令行入口：`python -m src.data_quality.quality_report`
- Streamlit 数据质量展示页：状态、分类统计、最近问题、命令示例
- V0.5 只检查不修复，修复重跑留给 V0.6
- CLI 输出 ASCII safe，Windows GBK 安全
- 测试：pytest -v 304 passed

## V0.5 不做什么

- 不自动修复数据（V0.6）
- 不自动重跑失败股票（V0.6）
- 不做因子计算（V0.7）
- 不做评分（V0.8）
- 不做策略与回测（V1.0）
- 不接 Qlib / Alpha360
- 不接 DeepSeek / GPT
- 不做自动交易
- 不接券商 API
- 不做复杂交易日历系统
- 不做自动定时任务

## V0.4 已完成内容

- 每日增量更新模块：从 stock_pool 读取股票列表，自动判断缺失数据区间
- 自动计算增量 start_date：基于数据库已有最大 trade_date + 1 天
- 支持 adj=raw/qfq/all 三种模式
- 支持 --limit 小批量测试
- 支持 --force + --start-date 重刷指定区间
- 无历史数据时自动 skipped，提示需先跑 V0.3
- 已是最新数据时自动 skipped（already up to date）
- 失败不中断整体任务
- 重复执行不产生重复数据（upsert 去重）
- CLI 输出 ASCII safe，Windows GBK 安全
- Streamlit 增量更新展示页面
- DuckDB 新增 get_max_trade_date / count_daily_records
- 测试：pytest -v 263 passed（V0.4 阶段）

## V0.3 已完成内容

- AkShare 客户端：支持 raw 不复权和 qfq 前复权日线数据拉取，字段映射完整
- 批量历史数据加载器：支持参数化配置（pool/start-date/end-date/limit/adj/sleep）
- 失败不中断：单只股票失败不会影响其他股票
- 数据写入 DuckDB（去重 upsert，重复执行不产生重复数据）
- 数据同步保存 Parquet（按 stock_code 单文件，自动合并去重）
- 更新日志记录与查询（success/failed/empty/skipped）
- 失败任务查询（自动排除后续已成功的组合）与重试
- Streamlit 历史数据初始化状态页面
- **真实链路已验证**：平安银行(000001) 20 年日线 raw + qfq 各 4,736 行成功入库
- 单元测试覆盖：304 个测试（含 V0.5 数据质量检查）

## V0.2 已完成内容

- 股票代码校验与交易所推断
- 股票池 CSV 加载与字段清洗
- DuckDB `stock_pool` 表读写与 upsert
- 股票池查询、激活、停用、黑名单、删除
- `main.py` 输出股票池统计信息
- Streamlit 股票池管理页面
- 股票池与过滤器测试用例

## 技术栈

- Python 3.10+
- DuckDB
- Parquet
- pandas
- numpy
- akshare
- streamlit
- plotly
- python-dotenv
- pytest

## 安装方式

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## 使用方式

### 项目概览

```bash
python main.py
```

### 小批量测试历史数据拉取

```bash
# 拉取 2 支股票的 raw + qfq 数据
python -m src.data_update.historical_loader --pool core_500 --limit 2 --adj all

# 只拉取不复权数据
python -m src.data_update.historical_loader --pool core_500 --limit 5 --adj raw

# 只拉取前复权数据
python -m src.data_update.historical_loader --pool core_500 --limit 5 --adj qfq

# 自定日期范围
python -m src.data_update.historical_loader --pool core_500 --start-date 20200101 --end-date 20231231 --limit 3

# 控制请求频率（默认 0.5 秒）
python -m src.data_update.historical_loader --pool core_500 --limit 10 --sleep 1.0
```

### 重试失败任务

```bash
python -m src.data_update.retry_failed --limit 10
```

### 每日增量更新

```bash
# 小批量测试 (5 支股票, raw + qfq)
python -m src.data_update.daily_incremental --pool core_500 --limit 5 --adj all

# 只更新不复权数据
python -m src.data_update.daily_incremental --pool core_500 --limit 5 --adj raw

# 只更新前复权数据
python -m src.data_update.daily_incremental --pool core_500 --limit 5 --adj qfq

# Force 重刷指定日期区间
python -m src.data_update.daily_incremental --pool core_500 --limit 3 --start-date 20260701 --end-date 20260703 --force
```

注意：
- V0.4 依赖 V0.3 已完成历史数据初始化
- 如果某只股票没有历史数据，默认会 skipped
- 重复执行不会重复写入
- DuckDB / Parquet 只保存在本地，不提交 GitHub

### 数据质量检查

```bash
# 检查 raw（限制 5 支股票）
python -m src.data_quality.quality_report --adj raw --limit 5

# 检查 qfq（限制 5 支股票）
python -m src.data_quality.quality_report --adj qfq --limit 5

# 同时检查 raw + qfq
python -m src.data_quality.quality_report --adj all --limit 20

# 单只股票检查
python -m src.data_quality.quality_report --stock-code 000001 --adj raw

# 只检查不写库
python -m src.data_quality.quality_report --adj all --limit 5 --no-write
```

注意：
- V0.5 依赖 V0.3 / V0.4 已完成数据落库
- 如果数据库没有日线数据，检查结果为空，属于正常
- V0.5 只检查不修复；修复与重跑是 V0.6
- 结果写入 `data_quality_report` 表，状态默认 `open`

### 查看数据状态

```bash
streamlit run ui/streamlit_app.py
```

### 运行测试

```bash
pytest -v
```

当前测试结果：304 passed。

## V0.3 验收前置条件

在运行 V0.3 历史数据拉取之前，请先完成以下步骤：

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

确认 akshare 可导入：

```bash
python -c "import akshare; print(akshare.__version__)"
```

### 2. 导入股票池

目前股票池数据库为空，需要先导入 ``core_500.csv``：

**方式一（推荐）：Streamlit 页面导入**

```bash
streamlit run ui/streamlit_app.py
```

然后在"股票池管理"标签页点击"导入 core_500.csv"按钮。

**方式二：Python CLI 导入**

```bash
python -c "
from src.universe.stock_pool import load_stock_pool_from_csv, save_stock_pool_to_db;
df = load_stock_pool_from_csv();
print(save_stock_pool_to_db(df))
"
```

### 3. 确认股票池已加载

```bash
python main.py
```

确认输出中 ``股票池统计 -> 总记录数`` 大于 0。

### 4. 小批量拉取历史数据

先测试 1 支股票：

```bash
python -m src.data_update.historical_loader --pool core_500 --limit 1 --adj raw
python -m src.data_update.historical_loader --pool core_500 --limit 1 --adj qfq
```

再测试 2 支（raw + qfq）：

```bash
python -m src.data_update.historical_loader --pool core_500 --limit 2 --adj all
```

## 数据安全说明

以下文件只保存在本地，**不提交 GitHub**：

- `.env` — 环境变量配置
- `data/duckdb/*.duckdb` — DuckDB 本地数据库
- `data/parquet/**/*.parquet` — Parquet 数据文件

## 目录结构

```text
quant-a-share-platform/
├── README.md
├── requirements.txt
├── .env.example
├── main.py                        # V1.1 入口
├── config/
│   ├── settings.py
│   └── logging_config.py          # V0.6 RotatingFileHandler
├── data/
│   ├── duckdb/                    # DuckDB 本地数据库（不提交）
│   ├── parquet/
│   │   ├── ods/
│   │   ├── dwd/
│   │   │   ├── daily_raw/         # V0.3 不复权日线 Parquet
│   │   │   └── daily_qfq/         # V0.3 前复权日线 Parquet
│   │   └── ads/
│   └── stock_pool/
│       ├── core_500.csv           # V0.2 500 核心股票池
│       └── sector_overrides.csv   # V0.5.1 行业覆盖表
├── src/
│   ├── data_source/
│   │   └── akshare_client.py      # V0.3 AkShare + V0.5.1 多源行业
│   ├── data_update/               # V0.3/V0.4 历史初始化 & 增量更新
│   │   ├── historical_loader.py
│   │   ├── daily_incremental.py
│   │   ├── update_log.py
│   │   └── retry_failed.py
│   ├── data_quality/              # V0.5 数据质量检查
│   │   ├── duplicate_checker.py
│   │   ├── missing_date_checker.py
│   │   ├── price_checker.py
│   │   └── quality_report.py
│   ├── data_repair/               # V0.6 数据修复与重跑
│   │   ├── repair_planner.py
│   │   ├── duplicate_repair.py
│   │   ├── date_range_repair.py
│   │   ├── parquet_repair.py
│   │   ├── repair_log.py
│   │   └── run_data_repair.py
│   ├── factors/                   # V0.7 基础因子计算
│   │   ├── base_factor.py
│   │   ├── price_factors.py
│   │   ├── momentum_factors.py
│   │   ├── volatility_factors.py
│   │   ├── volume_factors.py
│   │   ├── factor_calculator.py
│   │   └── run_factor_calculation.py
│   ├── factor_rank/               # V0.8 因子标准化与排名
│   │   ├── factor_config.py
│   │   ├── standardizer.py
│   │   ├── ranker.py
│   │   ├── rank_calculator.py
│   │   └── run_factor_ranking.py
│   ├── factor_analysis/           # V0.9 因子有效性分析
│   │   ├── forward_returns.py
│   │   ├── ic_analysis.py
│   │   ├── group_analysis.py
│   │   ├── analysis_summary.py
│   │   └── run_factor_analysis.py
│   ├── strategy/                  # V1.0 TopK 选股策略
│   │   ├── strategy_config.py
│   │   ├── single_factor_strategy.py
│   │   ├── multi_factor_strategy.py
│   │   ├── selector.py
│   │   └── run_topk_strategy.py
│   ├── backtest/                  # V1.1 基础回测引擎
│   │   ├── backtest_config.py
│   │   ├── position_builder.py
│   │   ├── return_calculator.py
│   │   ├── equity_curve.py
│   │   ├── backtest_engine.py
│   │   └── run_backtest.py
│   ├── llm/                       # V1.x AI 分析预留
│   ├── qlib_lab/                  # V1.7+ Qlib 预留
│   ├── report/                    # V1.x 报告预留
│   ├── scoring/                   # 预留
│   ├── storage/
│   │   ├── duckdb_repo.py
│   │   ├── parquet_repo.py
│   │   └── schema.py              # 29 张表 DDL
│   ├── universe/
│   │   ├── stock_pool.py          # V0.2 股票池 + V0.5.1 resolve_sector
│   │   ├── filters.py
│   │   └── repair_sector.py       # V0.5.1 批量补齐行业 CLI
│   └── utils/
├── ui/
│   └── streamlit_app.py           # 12 个标签页
├── tests/
│   ├── conftest.py
│   ├── test_akshare_client.py
│   ├── test_base_factor.py        # V0.7
│   ├── test_backtest_config.py    # V1.1
│   ├── test_backtest_engine.py    # V1.1
│   ├── test_cli_output_safety.py
│   ├── test_daily_incremental.py
│   ├── test_date_range_repair.py  # V0.6
│   ├── test_duplicate_checker.py
│   ├── test_duplicate_repair.py   # V0.6
│   ├── test_encoding_integrity.py
│   ├── test_equity_curve.py       # V1.1
│   ├── test_factor_analysis_summary.py # V0.9
│   ├── test_factor_calculator.py  # V0.7
│   ├── test_factor_config.py      # V0.8
│   ├── test_factor_rank_calculator.py # V0.8
│   ├── test_factor_ranker.py      # V0.8
│   ├── test_factor_standardizer.py # V0.8
│   ├── test_filters.py
│   ├── test_forward_returns.py    # V0.9
│   ├── test_group_analysis.py     # V0.9
│   ├── test_historical_loader.py
│   ├── test_ic_analysis.py        # V0.9
│   ├── test_main_startup.py
│   ├── test_missing_date_checker.py
│   ├── test_momentum_factors.py   # V0.7
│   ├── test_multi_factor_strategy.py # V1.0
│   ├── test_parquet_repo.py
│   ├── test_parquet_repair.py     # V0.6
│   ├── test_position_builder.py   # V1.1
│   ├── test_price_checker.py
│   ├── test_price_factors.py      # V0.7
│   ├── test_quality_report.py
│   ├── test_repair_log.py         # V0.6
│   ├── test_repair_planner.py     # V0.6
│   ├── test_return_calculator.py  # V1.1
│   ├── test_run_data_repair.py    # V0.6
│   ├── test_run_factor_analysis.py # V0.9
│   ├── test_run_factor_calculation.py # V0.7
│   ├── test_run_factor_ranking.py # V0.8
│   ├── test_run_topk_strategy.py  # V1.0
│   ├── test_single_factor_strategy.py # V1.0
│   ├── test_stock_pool.py
│   ├── test_strategy_config.py    # V1.0
│   ├── test_strategy_selector.py  # V1.0
│   ├── test_update_log.py
│   ├── test_volatility_factors.py # V0.7
│   └── test_volume_factors.py     # V0.7
├── docs/
│   ├── roadmap.md
│   ├── architecture.md
│   └── product_design.md
└── logs/                          # V0.6 日志（不提交）
```

## 后续版本路线

- V0.1 项目骨架 [完成]
- V0.2 股票池管理 [完成]
- V0.3 20 年历史数据初始化 [完成]
- V0.4 每日增量更新 [完成]
- V0.5 数据质量检查 [完成]
- V0.5.1 板块/行业自动获取 & 多源补齐 [完成]
- V0.6 数据修复与重跑 [完成]
- V0.7 基础因子计算 [完成]
- V0.8 因子标准化与排名 [完成]
- V0.9 因子有效性分析 [完成]
- V1.0 TopK 选股策略 [完成]
- V1.1 基础回测引擎 [完成]
- V1.2 回测评价体系 [完成]
- V1.3 多因子评分系统 [完成]
- V1.4 Streamlit 可视化平台升级 [完成]
- V1.5 每日任务流水线 [下一步]
- V1.6 每日候选股报告 [规划中]

## 免责声明

本项目仅用于个人研究和学习，不构成任何投资建议，不进行自动交易，不保证任何收益。
