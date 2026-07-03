# Quant A-Share Research Platform

面向 A 股 500 支核心股票池的个人量化研究平台。

## 项目定位

这是一个面向 A 股的个人量化研究平台，第一阶段以 500 支核心股票为研究对象，后续会逐步支持历史数据初始化、每日增量更新、数据质量检查、因子计算、评分、回测、Qlib 研究和 AI 分析报告。

## 当前版本

`V0.3`：20 年历史数据初始化

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
- 单元测试覆盖：215 个测试，含编码完整性、CLI 输出安全、CSV 结构校验

## V0.3 不做什么

- 不做每日增量更新（V0.4）
- 不做数据质量检查（V0.5）
- 不做因子计算（V0.7）
- 不做评分（V0.8）
- 不做策略与回测（V1.0）
- 不接入 Qlib / Alpha360
- 不接入 DeepSeek / GPT
- 不做自动交易
- 不接券商 API

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

### 查看数据状态

```bash
streamlit run ui/streamlit_app.py
```

### 运行测试

```bash
pytest -v
```

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
│   │   ├── update_log.py        # V0.3 更新日志
│   │   └── retry_failed.py      # V0.3 失败重试
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
│   ├── test_encoding_integrity.py  # V0.3 编码与 CSV 完整性测试
│   ├── test_historical_loader.py   # V0.3 历史数据加载器测试
│   ├── test_update_log.py          # V0.3 更新日志测试
│   ├── test_parquet_repo.py        # V0.3 Parquet 仓库测试
│   ├── test_stock_pool.py
│   └── test_filters.py
└── docs/
    └── roadmap.md
```

## 后续版本路线

- V0.1 项目骨架
- V0.2 股票池管理
- V0.3 [OK] 20 年历史数据初始化
- V0.4 每日增量更新
- V0.5 数据质量检查
- V0.6 数据修复与重跑
- V0.7 基础因子计算
- V0.8 因子标准化与排名
- V0.9 因子有效性分析
- V1.0 TopK 选股策略

## 免责声明

本项目仅用于个人研究和学习，不构成任何投资建议，不进行自动交易，不保证任何收益。
