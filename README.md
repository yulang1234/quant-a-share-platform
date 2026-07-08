# Quant A-Share Research Platform

## 当前版本：V1.4.8 core_500 小规模真实执行与批次恢复增强

V1.4.8 开始 core_500 小规模真实执行验证。新增 `batch_precheck` 预检、`--allow-core-500-run` 二次保护、`safe-core500-test` 安全执行 profile、批次恢复执行（pending/failed/empty/retryable）。`batch_report` 增强 retryable_count、suggested_retry_command、risk_warning。保持所有安全机制：默认 dry-run，core_500 真实执行必须 `--allow-core-500-run`。

### V1.4.8 已完成

- 新增 `batch_precheck`，执行前验证 batch/calendar/DuckDB/Parquet/Provider 状态。
- `batch_runner` 增加 core_500 真实执行二次保护 `--allow-core-500-run`。
- `batch_runner` 支持 `--profile safe-core500-test`（limit≤10, sleep≥1.0, stop_on_failed_rate, max_failed_rate≤0.3）。
- `batch_runner` 支持按 `--status pending/failed/empty/retryable` 恢复执行。
- `batch_report` 增强 retryable_count / non_retryable_count / suggested_retry_command / risk_warning。
- `batch_runner` confirm 后自动尝试 after snapshot。
- 提供 core_500 2024年 qfq 小区间真实执行标准流程。
- 保持 dry-run 默认。
- 真实执行必须 `--confirm`。
- core_500 真实执行必须 `--allow-core-500-run`。
- `--save-local` 必须配合 `--confirm`。
- PostgreSQL / SQLite 仍不存行情明细。

### V1.4.8 当前限制

- 本版本不是 core_500 全量补数。
- 本版本不是全市场补数。
- 本版本只建议跑 core_500 的 2024 年 qfq 小区间验证。
- 每次执行仍必须指定 batch_id、limit、confirm。
- `batch_runner` 不会自动循环补完整个 batch。
- Provider 稳定性受 AkShare / Tushare / MiniQMT 环境影响。
- 本版本不做板块问诊、龙头识别、持仓决策。
- 本版本不接 Qlib、Alpha158、Alpha360。

### V1.4.8 安全 CLI 示例

```bash
# 1. 构建 core_500
python -m src.backfill.core_universe_builder --core-size 500 --confirm

# 2. 创建 2024年1月 qfq 小批次计划
python -m src.backfill.batch_planner --universe core_500 --start-date 20240101 --end-date 20240131 --adj qfq --limit 20 --allow-core-500-plan --confirm

# 3. 预检
python -m src.backfill.batch_precheck --batch-id <batch_id>

# 4. no-save 小规模验证（10条）
python -m src.backfill.batch_runner --batch-id <batch_id> --profile safe-core500-test --limit 10 --confirm --no-save --allow-core-500-run

# 5. save-local 真实落库（10条）
python -m src.backfill.batch_runner --batch-id <batch_id> --profile safe-core500-test --limit 10 --confirm --save-local --allow-core-500-run

# 6. 批次报告
python -m src.backfill.batch_report --batch-id <batch_id>

# 7. 重试失败任务
python -m src.backfill.batch_runner --batch-id <batch_id> --status retryable --limit 10 --confirm --no-save --allow-core-500-run
```

### 下一版本 V1.4.9 建议

- Streamlit 增加 backfill batch 页面。
- 可视化展示 batch 状态、覆盖率快照、Provider 失败率。
- 支持从 UI 查看 suggested command。
- 支持批次执行日志查询。

## V1.4.7 core_500 分批补数准备与批次管理

V1.4.7 为 core_500 分批补数做准备。新增批次元数据（`backfill_batch` / `backfill_batch_snapshot`），`batch_planner` 支持 dry-run 预览 core_500 分批计划，confirm 写入时必须显式传 `--allow-core-500-plan`，`batch_runner` 按 `batch_id` 安全执行有限任务，`batch_report` 输出完整批次状态、覆盖率快照和 Provider 失败率。core_universe_builder 支持 `--core-size 500`。所有新 CLI 默认 dry-run。

### V1.4.7 已完成

- `core_universe_builder` 支持 `--core-size 500` 构建 core_500 universe。
- 新增 `backfill_batch` 和 `backfill_batch_snapshot` 元数据表。
- `data_load_task` 新增 `batch_id` 字段（可选，向后兼容）。
- 新增 `batch_planner`，支持 dry-run 预览 core_500 分批补数计划；confirm 写入需要 `--allow-core-500-plan`。
- 新增 `batch_runner`，支持按 `batch_id` 安全执行有限任务。
- 新增 `batch_report`，查看批次状态、任务统计、覆盖率快照和 Provider 失败率。
- `task_runner.run_tasks` 支持 `batch_id` 过滤 + `stop_on_failed_rate` 保护。
- 支持 before / after 覆盖率快照（集成在 planner/runner 中）。
- 保持 dry-run 默认。
- 真实写入必须 `--confirm`。
- `--save-local` 必须配合 `--confirm`。
- PostgreSQL / SQLite 仍不存行情明细。

### V1.4.7 当前限制

- 本版本不是 core_500 全量补数执行版。
- 本版本不是全市场补数。
- `batch_runner` 不会自动循环补完整个 batch。
- 每次执行仍必须手动指定 `batch_id`、`limit` 和 `confirm`。
- 本版本不做板块问诊、龙头识别、持仓决策。
- 本版本不接 Qlib、Alpha158、Alpha360。
- 本版本不训练模型、不自动交易、不接 xttrader。

### V1.4.7 安全 CLI 示例

```bash
# 构建 core_500 universe
python -m src.backfill.core_universe_builder --core-size 500 --dry-run
python -m src.backfill.core_universe_builder --core-size 500 --confirm

# 批次计划（dry-run）
python -m src.backfill.batch_planner --universe core_500 --start-date 20240101 --end-date 20240131 --adj qfq --limit 20 --dry-run

# 批次计划（confirm — 需要 --allow-core-500-plan）
python -m src.backfill.batch_planner --universe core_500 --start-date 20240101 --end-date 20240131 --adj qfq --limit 20 --allow-core-500-plan --confirm

# 批次执行
python -m src.backfill.batch_runner --batch-id <batch_id> --limit 10 --confirm --no-save
python -m src.backfill.batch_runner --batch-id <batch_id> --limit 10 --confirm --save-local

# 批次报告
python -m src.backfill.batch_report --batch-id <batch_id>
```

### 下一版本 V1.4.8 建议

- core_500 小规模真实执行。
- 支持按批次逐步跑 2024 年 qfq 数据。
- 增强失败任务重试策略。
- 增强 batch before / after 对比可视化。
- Streamlit 增加 backfill batch 页面。

## V1.4.6 真实交易日历与证券主数据增强

V1.4.6 将数据底座升级为真实交易日历和 Provider 驱动的证券主数据。AkShareProvider 实现 `get_trading_calendar` 和增强的 `get_stock_basic`，MarketDataService 新增统一的日历和股票基本信息接口，trading_calendar 支持 `calendar_source` / `is_real_calendar` 标记，security_master 支持 Provider 同步及 ST/退市/停牌字段增强。coverage_scanner 和 small_batch_report 优先使用真实日历并展示来源。

### V1.4.6 已完成

- 增强真实 A 股交易日历同步能力（AkShare `tool_trade_date_hist_sina`）。
- AkShareProvider 实现 `get_trading_calendar` 和增强的 `get_stock_basic`（全市场股票信息）。
- LocalCacheProvider 增强 `get_trading_calendar` / `get_stock_basic`（读本地 DB）。
- MarketDataService 新增 `get_trading_calendar` / `get_stock_basic` 方法（Provider fallback + call log）。
- `trading_calendar` 表新增 `calendar_source`、`is_real_calendar`、`source_provider`、`source_updated_at` 字段。
- `security_master` 表新增 `is_suspended`、`data_source` 字段。
- `sync_trading_calendar` 支持 Provider 驱动 + weekday fallback 警告。
- `sync_security_master` 支持 Provider 驱动同步 + ST/退市识别 + 字段标准化。
- `coverage_scanner` 优先使用真实交易日历，fallback 时显式警告。
- `small_batch_report` 展示 `calendar_source` / `is_real_calendar`。
- `task_stats` 增强失败原因分类（按 error_type / provider），增加 retryable 统计。
- 保持 dry-run 默认。
- 真实写入必须 `--confirm`。
- PostgreSQL / SQLite 仍不存行情明细。

### V1.4.6 当前限制

- 本版本不是全市场历史数据补齐。
- 本版本不是 core_500 补数。
- 停牌状态依赖 Provider 能力，不保证所有 Provider 都可完整提供。
- 如果 Provider 不可用，系统可能 fallback 到 weekday 日历，但会明确提示。
- 本版本不做板块问诊、龙头识别、持仓决策。
- 本版本不接 Qlib、Alpha158、Alpha360。
- 本版本不训练模型、不自动交易、不接 xttrader。

### V1.4.6 安全 CLI 示例

```bash
# 真实交易日历同步
python -m src.trading_calendar.sync_trading_calendar --start-date 20240101 --end-date 20241231 --exchange CN --dry-run
python -m src.trading_calendar.sync_trading_calendar --start-date 20240101 --end-date 20241231 --exchange CN --confirm

# Provider 驱动 security_master 同步
python -m src.security.sync_security_master --limit 20 --dry-run
python -m src.security.sync_security_master --limit 20 --confirm

# 覆盖率扫描（使用真实日历）
python -m src.data_quality.coverage_scanner --universe core_50 --adj qfq --start-date 20240101 --end-date 20240131 --limit 10 --dry-run

# 批次报告（展示日历来源）
python -m src.backfill.small_batch_report --universe core_50 --start-date 20240101 --end-date 20240131 --adj qfq --limit 50

# 任务统计（增强失败分类）
python -m src.data_tasks.task_stats
```

### 下一版本 V1.4.7 建议

- core_500 分批补数准备。
- 按 Provider 限速和失败率自动分批。
- 补数任务批次 ID。
- 批次级 before / after 覆盖率快照。
- 更完整的失败重试和跳过策略。

## V1.4.5 core_50 / core_100 小批量补数与批次报告

V1.4.5 将 V1.4.4 的小样本验证升级为 core_50 / core_100 小批量补数闭环。支持按 universe 生成任务、按 limit 分批执行、按 raw/qfq 分批、按年份区间分批、失败任务重试、批次覆盖率报告和 Provider 稳定性统计。保持所有操作安全可控（默认 dry-run，--confirm 才写）。本版本不是全市场 / core_500 补数版本。

### V1.4.5 已完成

- 新增 `core_universe_builder`，支持构建 core_50 / core_100 小批量 universe。
- 新增 `small_batch_planner`，支持按 universe / adj / year / limit 生成补数任务。
- 新增 `small_batch_runner`，安全包装 `task_runner`，支持 `--no-save` / `--save-local`。
- 新增 `small_batch_report`，输出批次覆盖率摘要。
- 新增 Provider 批次稳定性统计（集成在 `small_batch_report` 中）。
- 保持 dry-run 默认。
- 真实写入任务必须 `--confirm`。
- 真实保存本地行情必须 `--confirm --save-local`。
- PostgreSQL / SQLite 仍不存行情明细。

### V1.4.5 当前限制

- 本版本不是全市场补数。
- 本版本不是 core_500 补数。
- core_50 / core_100 的选股逻辑先以稳定、安全、可验证为主，不代表最终投研股票池。
- 行业资讯、板块问诊、龙头识别、持仓决策不在本版本范围内。
- 当前不接 Qlib、Alpha158、Alpha360。
- 当前不训练模型、不自动交易、不接 xttrader。

### V1.4.5 安全 CLI 示例

```bash
# 构建 core_50 / core_100
python -m src.backfill.core_universe_builder --core-size 50 --dry-run
python -m src.backfill.core_universe_builder --core-size 50 --confirm

# 生成小批量任务
python -m src.backfill.small_batch_planner --universe core_50 --start-date 20240101 --end-date 20240131 --adj qfq --limit 5 --dry-run
python -m src.backfill.small_batch_planner --universe core_50 --start-date 20240101 --end-date 20240131 --adj qfq --limit 5 --confirm

# 执行任务
python -m src.backfill.small_batch_runner --limit 5 --adj qfq --confirm --no-save
python -m src.backfill.small_batch_runner --limit 5 --adj qfq --confirm --save-local

# 批次覆盖率报告
python -m src.backfill.small_batch_report --universe core_50 --start-date 20240101 --end-date 20240131 --adj qfq --limit 50
```

### 下一版本 V1.4.6 建议

- 真实交易日历 API 接入。
- 真实 Provider 驱动 security_master 同步。
- ST / 退市 / 停牌字段增强。
- core_500 分批补数准备。
- 补数任务失败原因分类增强。

## V1.4.4 小样本真实回填验证与本地保存链路稳定化

V1.4.4 强化小样本真实回填验证和本地保存链路。`task_runner` 支持 `save-local`，`smoke_backfill` 支持单股小区间验证，`repair_status_updater` 支持任务成功后更新 gap 状态，`coverage_compare` 支持 before / after 覆盖率对比。本版本不是 core_50 / core_500 / 全市场补数版本。

### V1.4.4 已完成

- `task_runner` 支持 `save-local`。
- `confirm + no-save` 只验证 Provider 和任务状态，不保存行情。
- `confirm + save-local` 可保存本地行情。
- 保存链路复用现有 DuckDB / Parquet。
- `repair_status_updater` 可更新 gap 状态。
- `coverage_compare` 可做 before / after 对比。
- `smoke_backfill` 支持单股小区间验证。
- 默认 dry-run。
- `--confirm` 才真实执行。
- `--save-local` 必须配合 `--confirm`。
- PostgreSQL / SQLite 元数据库不存行情明细。

### V1.4.4 当前限制

- 本版本不是全市场补数。
- 本版本不是 core_50 / core_500 补数。
- `smoke_backfill` 只适合单股小区间验证。
- `save-local` 当前只适合小样本验证。
- 当前没有迁移 `historical_loader.py`。
- 当前没有接 Qlib、Alpha158、Alpha360。
- 当前没有训练模型、自动交易、`xttrader`、ClickHouse、全市场分钟线或 tick 数据。
- PostgreSQL / SQLite 元数据库不存行情明细。
- 全量补数留到后续版本。

### V1.4.4 安全 CLI 示例

```bash
python -m src.data_quality.smoke_backfill --stock-code 000001.SZ --start-date 20240101 --end-date 20240131 --adj qfq --dry-run
python -m src.data_quality.smoke_backfill --stock-code 000001.SZ --start-date 20240101 --end-date 20240131 --adj qfq --confirm --no-save
python -m src.data_quality.smoke_backfill --stock-code 000001.SZ --start-date 20240101 --end-date 20240131 --adj qfq --confirm --save-local
```

### 下一版本 V1.4.5 建议

- core_50 / core_100 小批量补数。
- 按 limit 分批执行。
- 按 raw / qfq 分批。
- 按年份区间分批。
- 加强失败任务重试。
- 批次覆盖率报告。
- 批次任务统计。
- Provider 稳定性统计。
- 继续禁止全市场无控制补数。

## V1.4.3 数据覆盖率报告、缺口识别与小样本补数验证

V1.4.3 完成覆盖率报告、缺口识别、缺口转修复任务，以及小样本补数验证的基础能力。本版本不是全市场历史数据补齐完成版；默认只扫描本地数据，所有新增 CLI 默认 dry-run，`--confirm` 才写元数据库，`--save-local` 必须配合 `--confirm`。

### V1.4.3 已完成

- 新增 `data_coverage_report` 表。
- 新增 `data_gap_detail` 表。
- 新增 `coverage_scanner`。
- 新增 `coverage_report`。
- 新增 `gap_report`。
- 新增 `build_repair_tasks`。
- 新增 `sample_backfill_validate`。
- 覆盖率基于 `trading_calendar.is_open=true`。
- 缺口识别基于交易日序列，不按自然日判断。
- 缺口可以转换为 `data_load_task`。
- 小样本可以验证 `task_runner + MarketDataService` 链路。
- 所有 CLI 默认 dry-run。
- `--confirm` 才真实写入元数据库。
- `--save-local` 必须配合 `--confirm`。

### V1.4.3 当前限制

- 本版本不是全市场历史数据补齐完成。
- 当前还没有真正执行全市场补数。
- 当前 `security_master` 如果来源是 `stock_pool`，就不是完整全市场。
- 当前 `trading_calendar` 如果是 weekday 生成，就不是完整真实 A 股节假日日历。
- 当前 `coverage_scanner` 只扫描本地 DuckDB / LocalCache 数据。
- 当前 `build_repair_tasks` 只生成任务，不执行任务。
- 当前 `sample_backfill_validate` 是小样本验证工具，不是全量补数工具。
- 当前没有迁移 `historical_loader.py`。
- 当前没有接 Qlib、Alpha158、Alpha360。
- 当前没有训练模型、自动交易、`xttrader`、ClickHouse、全市场分钟线或 tick 数据。
- PostgreSQL / SQLite 元数据库只存元数据、覆盖率摘要、缺口和任务状态，不存行情明细。

### V1.4.3 安全 CLI 示例

```bash
python -m src.data_quality.coverage_scanner --limit 5 --dry-run
python -m src.data_quality.coverage_report --adj qfq --top-missing --limit 20
python -m src.data_quality.gap_report --adj qfq --limit 20
python -m src.data_quality.build_repair_tasks --limit 5 --dry-run
python -m src.data_quality.sample_backfill_validate --limit 3 --dry-run
python -m src.data_quality.sample_backfill_validate --limit 3 --confirm --no-save
python -m src.data_quality.sample_backfill_validate --limit 3 --confirm --save-local
```

`sample_backfill_validate --save-local` 是实验性小样本能力，只允许显式 `--confirm` 后使用；不写 PostgreSQL 行情明细。

### 下一版本 V1.4.4 建议

- 小样本真实回填验证加强。
- raw / qfq 本地保存链路稳定化。
- 覆盖率 before / after 对比。
- 修复任务执行结果自动回写 gap 状态。
- core_50 / core_500 分批补数准备。
- 真实交易日历 API 接入。
- 真实 Provider 驱动 security_master 同步。

## V1.4.2 全市场证券主数据、交易日历与历史数据任务队列基础

V1.4.2 完成证券主数据、交易日历和历史数据加载任务队列的基础能力。本版本仍以安全收口为主：所有新增 CLI 默认 dry-run，只有显式 `--confirm` 才写元数据库；`task_runner` 默认 `--no-save`，不会把行情明细写入 PostgreSQL。

### V1.4.2 已完成

- 新增 `trading_calendar` 表。
- 新增 `data_load_task` 表。
- 新增 `data_load_task_log` 表。
- 新增 security_master 同步服务和 CLI。
- 新增 `universe_all_a` 构建服务和 CLI。
- 新增 trading calendar service 和同步 CLI。
- 新增 data load task repository / log repository。
- 新增 `retry_policy`。
- 新增 `task_builder`，支持 raw / qfq / all，支持按年分片。
- 新增 `task_runner`，默认 dry-run，默认 `--no-save`。
- 新增 `task_stats`。

### V1.4.2 当前限制

- 当前 `security_master` sync 主要基于本地 `stock_pool`，不是完整 Provider 驱动的全市场证券主数据同步。
- 当前 `universe_all_a` 如果基于本地 `stock_pool` 或当前 `security_master`，范围就是本地已有股票范围，不代表完整全 A。
- 当前 `trading_calendar` 默认 weekday 生成，不包含完整中国节假日和临时休市。
- 当前还没有真实交易日历 API；后续覆盖率报告必须基于真实交易日历，不能基于简单自然日或 weekday。
- 当前还没有真实全市场历史数据补齐。
- 当前没有迁移 `historical_loader.py` 到 `MarketDataService`。
- 当前没有接 Qlib / Alpha158 / Alpha360。
- 当前没有训练模型、自动交易、`xttrader`、ClickHouse、全市场分钟线或 tick 数据。
- PostgreSQL / SQLite 元数据库不存行情明细。

### V1.4.2 安全 CLI 示例

```bash
python -m src.security.sync_security_master --limit 5 --dry-run
python -m src.universe.universe_builder --limit 5 --dry-run
python -m src.trading_calendar.sync_trading_calendar --start-date 20260101 --end-date 20260131 --exchange CN --dry-run
python -m src.data_tasks.task_builder --limit 10 --dry-run
python -m src.data_tasks.task_runner --limit 5 --dry-run
python -m src.data_tasks.task_runner --limit 5 --confirm --no-save
python -m src.data_tasks.task_stats
```

### 下一版本 V1.4.3 建议

- 真实 Provider 驱动的 `security_master` 同步。
- 真实交易日历 API 接入。
- 历史数据覆盖率报告。
- 缺口识别。
- 缺口修复任务生成。
- 小样本真实历史数据补齐。
- 旧 `historical_loader.py` 渐进接入 `MarketDataService`。

V1.4.1 完成了元数据库、多数据源 Provider 架构、Provider fallback、调用日志、健康状态、CLI 检查工具，以及 Streamlit “数据源”健康度只读页面。

### V1.4.1 已完成

- 元数据库：支持 PostgreSQL；未配置 `DATABASE_URL` 时自动 fallback 到 `data/meta/quant_meta.db`。
- 元数据表：`security_master`、`universe_config`、`universe_member`、`data_provider_config`、`data_provider_health`、`data_provider_call_log`。
- Provider 架构：`LocalCacheProvider`、`MiniQMTProvider`、`AkShareProvider`、`TushareProvider`。
- Provider fallback：LocalCache 优先，MiniQMT / Tushare 不可用时自动跳过，AkShare 作为补充源。
- Provider 日志与健康状态：记录 success / failed / empty / skipped，并限制错误信息长度。
- CLI：`check_providers`、`fetch_daily`、`provider_stats`、`test_miniqmt`。
- Streamlit：新增“数据源”tab，只读展示元数据库、Provider 健康、调用统计和最近错误。

### 数据存储边界

- PostgreSQL / SQLite：只存元数据、Provider 配置、Provider 健康、Provider 调用日志、universe 和后续任务状态摘要。
- DuckDB：本地研究查询引擎。
- Parquet：历史行情和研究数据湖。
- 当前不把大规模行情明细、因子宽表、Qlib 特征明细、模型预测明细、回测逐日明细写入 PostgreSQL。

### DATABASE_URL 配置

`.env` 示例必须使用占位符，不要写真实账号或密码：

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5432/quant_platform
```

未配置 `DATABASE_URL` 时，系统使用 SQLite fallback：

```text
data/meta/quant_meta.db
```

初始化元数据库：

```bash
python -m src.db.migrations init_meta_db
```

### Provider fallback 顺序

- `daily_raw`：LocalCache > MiniQMT > Tushare > AkShare
- `daily_qfq`：LocalCache > Tushare > AkShare > MiniQMT
- `realtime_quote`：MiniQMT > AkShare
- `trading_calendar`：MiniQMT > Tushare > AkShare
- `stock_basic`：MiniQMT > Tushare > AkShare

### Provider CLI

```bash
python -m src.data_sources.check_providers
python -m src.data_sources.fetch_daily --stock-code 000001.SZ --start-date 20260101 --end-date 20260105 --adj qfq --no-save
python -m src.data_sources.provider_stats
python -m src.data_sources.test_miniqmt --stock-code 000001.SZ --start-date 20240101 --end-date 20240701
```

### MiniQMT / AkShare / Tushare 说明

- MiniQMT 当前只接 `xtdata`，不接 `xttrader`；未安装或未启动时显示 disabled / down，不影响系统启动。
- AkShareProvider 是补充源，不再作为唯一主源；不建议直接依赖 AkShare 做无保护的全市场批量拉取。
- Tushare 当前是 token 骨架；未配置 `TUSHARE_TOKEN` 时自动 disabled，后续可作为备用源和校验源。

### Streamlit 数据源页面

- 新增“数据源”tab。
- 页面只读，不执行真实数据拉取。
- 页面不展示完整 `DATABASE_URL`、数据库密码或 `TUSHARE_TOKEN`。
- 页面展示 Provider 健康、调用统计、最近错误和操作提示。

### 当前明确未实现

- 未迁移 `historical_loader.py` 到 `MarketDataService`。
- 未迁移 `daily_incremental.py` 到 `MarketDataService`。
- 未接 Qlib。
- 未接 Alpha158 / Alpha360。
- 未训练模型。
- 未做自动交易。
- 未接 `xttrader`。
- 未接 ClickHouse。
- 未做全市场分钟线。
- 未做历史数据补齐任务队列。
- 未做覆盖率报告和缺口修复。

### 下一版本 V1.4.2 计划

- 历史数据补齐。
- 任务队列。
- 覆盖率报告。
- 缺口修复。
- 旧数据更新链路逐步接入 `MarketDataService`。
- 按交易日历判断缺失，不按自然日判断。

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
- V1.4.2 才做数据覆盖率、缺口修复和补齐任务队列
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
│   ├── backfill/                    # V1.4.5 core_50/core_100 小批量补数
│   │   ├── __init__.py
│   │   ├── core_universe_builder.py
│   │   ├── small_batch_planner.py
│   │   ├── small_batch_runner.py
│   │   └── small_batch_report.py
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
- V1.4.1 多数据源适配层、MiniQMT 接入与 PostgreSQL 元数据库 [完成]
- V1.4.2 全市场证券主数据、交易日历与历史数据任务队列基础 [完成]
- V1.4.3 数据覆盖率报告、缺口识别与小样本补数验证 [完成]
- V1.4.4 小样本真实回填验证与本地保存链路稳定化 [完成]
- V1.4.5 core_50/core_100 小批量补数与批次统计 [完成]
- V1.4.6 真实交易日历与证券主数据增强 [完成]
- V1.4.7 core_500 分批补数准备与批次管理 [完成]
- V1.4.8 core_500 小规模真实执行与批次恢复 [完成]
- V1.4.9 Streamlit backfill batch 页面 [下一步]
- V1.5 每日任务流水线 [规划中]
- V1.6 每日候选股报告 [规划中]

## 免责声明

本项目仅用于个人研究和学习，不构成任何投资建议，不进行自动交易，不保证任何收益。
