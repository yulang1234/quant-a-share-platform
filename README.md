# Quant A-Share Research Platform

面向 A 股 500 支核心股票池的个人量化研究平台。

## 项目定位

这是一个面向 A 股的个人量化研究平台，第一阶段以 500 支核心股票为研究对象，后续会逐步支持历史数据初始化、每日增量更新、数据质量检查、因子计算、评分、回测、Qlib 研究和 AI 分析报告。

## 当前版本

`V0.1`：项目骨架

## V0.1 已完成内容

- 项目目录结构与模块划分
- `.env` 配置读取与目录自动创建
- 基础日志配置
- DuckDB 与 Parquet 存储骨架
- 15 张初始化数据表 DDL
- 股票池示例 CSV
- `main.py` 启动入口
- Streamlit 首页占位页
- Pytest 初始化测试

## V0.1 不做什么

- 不拉取真实行情数据
- 不接入 Qlib / Alpha360
- 不接入 DeepSeek / GPT
- 不做策略、回测、实盘交易
- 不接券商 API
- 不自动下单

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

## 启动方式

CLI:

```bash
python main.py
```

Streamlit:

```bash
streamlit run ui/streamlit_app.py
```

## 运行测试

```bash
pytest
```

## 目录结构

```text
quant-a-share-platform/
├── README.md
├── requirements.txt
├── .env.example
├── main.py
├── config/
├── data/
├── src/
├── ui/
├── tests/
└── docs/
```

## 后续版本路线

- V0.1 项目骨架
- V0.2 股票池管理
- V0.3 20 年历史数据初始化
- V0.4 每日增量更新
- V0.5 数据质量检查
- V0.6 数据修复与重跑
- V0.7 基础因子计算
- V0.8 因子标准化与排名
- V0.9 因子有效性分析
- V1.0 TopK 选股策略

## 免责声明

本项目仅用于个人研究和学习，不构成任何投资建议，不进行自动交易，不保证任何收益。
