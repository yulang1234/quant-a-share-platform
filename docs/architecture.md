# 系统架构文档

## 1. 总体架构

平台由四部分组成：

- `config/`：配置与日志
- `src/`：核心业务模块
- `data/`：DuckDB、Parquet 与股票池数据
- `ui/`：Streamlit 页面入口

## 2. 数据分层

- ODS：原始数据层
- DWD：清洗明细层
- ADS：分析应用层

## 3. DuckDB + Parquet 设计

- DuckDB 负责元数据、日志、结果索引和轻量分析
- Parquet 负责分层文件存储
- 两者组合兼顾本地分析性能与可维护性

## 4. 模块职责

- `data_source/`：外部数据源客户端
- `universe/`：股票池与过滤器
- `storage/`：DuckDB / Parquet 封装
- `data_update/`：历史与增量更新流程
- `data_quality/`：质量检查与报告
- `factors/`：因子计算
- `scoring/`：标准化、评分、排序
- `strategy/`：选股策略
- `backtest/`：回测引擎和指标
- `qlib_lab/`：Qlib 研究扩展
- `report/`：报告生成
- `llm/`：AI 分析扩展

## 5. 数据流

AkShare -> ODS -> DWD -> ADS -> 策略/报告/UI

## 6. Qlib 和 AI 接入规划

- `qlib_lab/` 负责未来的 Alpha158 / Alpha360 研究接入
- `llm/` 负责未来的 AI 分析报告接入
- 当前 V0.1 只保留接口和占位模块
