# 版本路线图

## 当前进度

- V1.4.3 数据覆盖率报告、缺口识别与小样本补数验证：完成

## V1.4.3 完成范围

- `data_coverage_report`、`data_gap_detail`。
- `coverage_scanner`、`coverage_report`、`gap_report`。
- `build_repair_tasks`。
- `sample_backfill_validate`。
- 覆盖率基于 `trading_calendar.is_open=true`。
- 缺口识别基于交易日序列，不按自然日判断。
- 缺口可以转换为 `data_load_task`。
- 所有新增 CLI 默认 dry-run，`--confirm` 才写元数据库。
- `--save-local` 必须配合 `--confirm`。

## V1.4.3 边界

- 不是全市场历史数据补齐完成。
- 当前 coverage_scanner 只扫描本地数据。
- 当前 build_repair_tasks 只生成任务，不执行任务。
- 当前 sample_backfill_validate 是小样本验证工具，不是全量补数工具。
- 当前 trading_calendar 仍可能是 weekday 基础日历，不代表完整真实 A 股节假日日历。
- PostgreSQL / SQLite 元数据库不存行情明细。

## V1.4.2 完成范围

- `trading_calendar`、`data_load_task`、`data_load_task_log`。
- security_master 本地股票池同步基础能力。
- `universe_all_a` 构建基础能力。
- weekday 交易日历基础能力。
- `task_builder`、`task_runner`、`task_stats`、`retry_policy`。
- 所有新增 CLI 默认 dry-run，`--confirm` 才写元数据库。
- `task_runner` 默认 `--no-save`，不写行情明细到 PostgreSQL。

## V1.4.2 边界

- 当前 security_master sync 主要基于本地 stock_pool，不是完整全市场 Provider 同步。
- 当前 universe_all_a 不代表完整全 A，只代表当前本地数据范围。
- 当前 trading_calendar 默认 weekday 生成，不包含完整中国节假日和临时休市。
- 当前未迁移 historical_loader / daily_incremental / retry_failed / date_range_repair。
- 当前未接 Qlib、Alpha158、Alpha360、xttrader、ClickHouse。
- 当前未做全市场分钟线、tick 数据、模型训练或自动交易。

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

## 下一步：V1.4.4

- 小样本真实回填验证加强。
- raw / qfq 本地保存链路稳定化。
- 覆盖率 before / after 对比。
- 修复任务执行结果自动回写 gap 状态。
- core_50 / core_500 分批补数准备。
- 真实交易日历 API 接入。
- 真实 Provider 驱动 security_master 同步。

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
- V1.4.2 全市场证券主数据、交易日历与历史数据任务队列基础：完成
- V1.4.3 数据覆盖率报告、缺口识别与小样本补数验证：完成

## 下一步

- V1.4.4 小样本真实回填验证加强、本地保存链路稳定化、覆盖率 before/after：下一步

## 规划中

- V1.5 每日任务流水线：规划中
- V1.6 每日候选股报告：规划中
- V1.7 Qlib Alpha158 接入
- V1.8 Alpha360 / 机器学习模型
- V1.9 AI 分析报告与复盘
