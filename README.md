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
├── main.py
├── config/
├── data/
│   ├── duckdb/
│   ├── parquet/
│   │   ├── ods/
│   │   ├── dwd/
│   │   │   ├── daily_raw/      # V0.3 不复权日线 Parquet
│   │   │   └── daily_qfq/      # V0.3 前复权日线 Parquet
│   │   └── ads/
│   └── stock_pool/
├── src/
│   ├── data_source/
│   │   └── akshare_client.py    # V0.3 AkShare 封装
│   ├── data_update/
│   │   ├── historical_loader.py # V0.3 历史数据加载器
│   │   ├── daily_incremental.py # V0.4 每日增量更新
│   │   ├── update_log.py        # V0.3 更新日志
│   │   └── retry_failed.py      # V0.3 失败重试
│   ├── data_quality/
│   │   ├── duplicate_checker.py # V0.5 重复数据检查
│   │   ├── missing_date_checker.py # V0.5 缺失日期检查
│   │   ├── price_checker.py     # V0.5 价格异常检查
│   │   └── quality_report.py    # V0.5 质量报告汇总
│   ├── storage/
│   │   ├── duckdb_repo.py
│   │   ├── parquet_repo.py
│   │   └── schema.py
│   ├── universe/
│   └── ...
├── ui/
│   └── streamlit_app.py
├── tests/
│   ├── test_akshare_client.py      # V0.3 AkShare 客户端测试
│   ├── test_cli_output_safety.py   # V0.3 CLI 输出安全性测试
│   ├── test_encoding_integrity.py  # 编码与 CSV 完整性测试
│   ├── test_historical_loader.py   # V0.3 历史数据加载器测试
│   ├── test_update_log.py          # V0.3 更新日志测试
│   ├── test_parquet_repo.py        # V0.3 Parquet 仓库测试
│   ├── test_daily_incremental.py   # V0.4 每日增量更新测试
│   ├── test_main_startup.py        # V0.4/V0.5 启动与版本文案测试
│   ├── test_duplicate_checker.py   # V0.5 重复数据检查测试
│   ├── test_missing_date_checker.py # V0.5 缺失日期检查测试
│   ├── test_price_checker.py       # V0.5 价格异常检查测试
│   ├── test_quality_report.py      # V0.5 质量报告测试
│   ├── test_stock_pool.py
│   └── test_filters.py
└── docs/
    └── roadmap.md
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
- V0.8 因子标准化与排名 [下一步]
- V0.9 因子有效性分析
- V1.0 TopK 选股策略

## 免责声明

本项目仅用于个人研究和学习，不构成任何投资建议，不进行自动交易，不保证任何收益。
