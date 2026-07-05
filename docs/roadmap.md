# 版本路线图

## 当前进度

- V1.4.1 多数据源适配层、MiniQMT 接入与 PostgreSQL 元数据库：完成

## V1.4.1 完成范围

- PostgreSQL / SQLite fallback 元数据库。
- `security_master`、`universe_config`、`universe_member`、`data_provider_config`、`data_provider_health`、`data_provider_call_log`。
- `LocalCacheProvider`、`MiniQMTProvider`、`AkShareProvider`、`TushareProvider`。
- `MarketDataService` provider fallback。
- Provider 调用日志和健康状态。
- Provider CLI：`check_providers`、`fetch_daily`、`provider_stats`、`test_miniqmt`。
- Streamlit “数据源”只读健康度页面。

## V1.4.1 边界

- 不迁移 `historical_loader.py`、`daily_incremental.py`、`retry_failed.py`、`date_range_repair.py` 到 `MarketDataService`。
- 不接 Qlib / Alpha158 / Alpha360。
- 不训练模型。
- 不接 `xttrader`。
- 不接 ClickHouse。
- 不做全市场分钟线或 tick 数据。
- PostgreSQL / SQLite 只存元数据，不存大规模行情明细。

## 下一步：V1.4.2

- 历史数据补齐。
- 任务队列。
- 覆盖率报告。
- 缺口修复。
- 旧数据更新链路逐步接入 `MarketDataService`。
- 按交易日历判断缺失，不按自然日判断。

## 已完成

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
- V1.4.1 多数据源适配层、MiniQMT 接入与 PostgreSQL 元数据库：完成

## 下一步

- V1.4.2 历史数据补齐、任务队列、覆盖率报告、缺口修复：下一步

## 规划中

- V1.5 每日任务流水线：规划中
- V1.6 每日候选股报告：规划中
- V1.7 Qlib Alpha158 接入
- V1.8 Alpha360 / 机器学习模型
- V1.9 AI 分析报告与复盘
