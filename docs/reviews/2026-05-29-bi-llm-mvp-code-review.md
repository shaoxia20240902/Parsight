# BI LLM MVP 生成链路代码 Review

日期：2026-05-29

范围：
- 后端三阶段生成：`backend/app/services/bi_mvp_generation.py`
- BI SSE 路由与状态：`backend/app/routers/bi.py`
- 前端生成入口：`frontend/src/components/BIDashboard.vue`
- 前端阶段看板：`frontend/src/components/bi/BIStagedGeneratingBoard.vue`
- 前端进度归一化：`frontend/src/composables/useBiGenerationProgress.ts`
- 相关落库方法：`backend/app/services/db_service.py`

## 结论

当前实现已经能支撑 MVP：模型生成分类、问题、图表 SQL，通过 SSE 驱动 B1/B2/B3 前端过程，并在成功后落库，下次进入可直接读取。

但这条链路仍有几个会影响稳定性的逻辑问题。优先级最高的是生成任务与 SSE 连接绑定、旧配置清理、跨表分类的真实语义、失败图表的最终状态表达，以及 SQL 预执行带来的性能与成功率问题。

## 修复状态

本轮已修复：
- SSE 连接与生成任务解耦：`/generate/{file_id}` 仍返回 SSE，但真实生成任务进入后台 job，浏览器断开不再取消任务。
- 重新生成时清理旧配置：进入 `generating` 后清空旧 `bi_config`，避免旧看板和新任务混用。
- `generating` 状态恢复：无本地 job 时不再直接覆盖，只有超过 30 分钟的旧任务才允许抢占。
- B2 分类事件：后端补发 `category_plan_start/category_plan_done`，并为每个分类写入独立 thinking。
- 失败图表契约：最终配置保留失败占位；SQL 生成失败会先 repair，再降级 detail table，彻底失败才标记 failed。
- B3 计数口径：前端新增成功/失败/已处理统计，避免失败图表导致“永远未完成”的误导。
- SQL repair/fallback：新增 MySQL 修复 prompt 与安全明细表 fallback。
- Prompt 版本化：`generation_report.prompt_version` 记录当前生成契约版本。
- 前端真实/Mock 边界：真实模式不再 fallback 到 demoConfig；按钮文案按真实配置状态显示。
- 代码清理：移除发现的死变量。

仍保留为 MVP 约束：
- `custom` 分类现在明确记录为 `cross_table_theme_single_table_sql`：它是跨表主题设计，但当前 SQL 仍落到单张主表。真正跨表 JOIN 需要等关联图谱结构化后再打开白名单 JOIN。

## 主要问题

### P0：SSE 断开会取消整个生成任务

位置：
- `backend/app/routers/bi.py:208`
- `backend/app/routers/bi.py:217`
- `backend/app/routers/bi.py:265`

现在 `generation_task` 是在 SSE 响应协程内部创建的。如果浏览器刷新、页面切换、网络断开或代理超时，FastAPI 会取消响应协程，进入 `CancelledError` 分支并把 `bi_status` 置为 `failed`。这意味着后端“生成任务生命周期”实际上依赖前端连接持续存在。

影响：
- 用户只是刷新页面，也可能中断后端生成。
- 长时间 LLM 任务容易被浏览器或开发工具超时打断。
- 断线重连只能重新生成，无法继续看已有进度。

建议：
- 把生成任务从 SSE 请求中解耦，改成后台 job。
- `POST /generate/{file_id}` 只负责创建 job、更新状态、返回 job id 或订阅流。
- SSE 只订阅 job event log；断开不取消 job。
- 事件落库到 `bi_generation_events` 或 Redis stream，前端重进可 replay。

### P0：重新生成没有先清空旧 BI 配置

位置：
- `backend/app/routers/bi.py:115`
- `backend/app/routers/bi.py:116`
- `backend/app/routers/bi.py:253`

DBService 已经有 `clear_bi_config()`，但重新生成入口没有调用。生成状态进入 `generating` 时，旧的 `bi_config` 仍然存在。虽然当前前端生成中会展示 staged UI，但刷新或状态查询边界场景下，旧配置仍可能被误认为可展示数据。

影响：
- 生成中刷新后，用户可能看到旧看板和新生成状态混在一起。
- 新旧配置无法明确区分，后续做 job replay 会更难。

建议：
- 在 `update_bi_status(file_id, "generating")` 后立即 `clear_bi_config(file_id)`，或者更好地引入 `generation_id`，旧配置保留为 `last_completed_config`，新任务写入 `draft_config`。
- UI 明确区分“上次完成结果”和“当前生成中结果”。

### P1：跨表高维分类当前只是“语义跨表”，SQL 仍只能查一张主表

位置：
- `backend/app/services/bi_mvp_generation.py:260`
- `backend/app/services/bi_mvp_generation.py:355`
- `backend/app/services/bi_mvp_generation.py:385`
- `backend/app/services/bi_mvp_generation.py:562`

B1 会生成 `custom` 分类，也会记录 `related_tables`，但 B3 prompt 明确要求只能查 `table_name` 一张表，`profile_by_category` 也只绑定一个 profile。最终跨表分类只是问题描述里参考多表，SQL 仍是单表。

影响：
- “经营总览 / 目标达成 / 客户产品”看起来是跨表，但数据结果不一定能兑现跨表含义。
- 用户可能认为系统已做关联计算，实际只是主表口径。

建议：
- MVP 阶段在 UI 和 generation_report 明确标注 `custom` 是“跨表主题，单表落地”。
- 下一版 B3 输入应包含 `primary_table` + `join_candidates` + verified relation graph。
- SQL validator 从“只允许单表”升级为“只允许白名单表 + 白名单 JOIN 条件”。

### P1：无本地锁的 `generating` 状态会被直接覆盖为 failed

位置：
- `backend/app/routers/bi.py:105`
- `backend/app/routers/bi.py:109`
- `backend/app/routers/bi.py:111`

现在只要当前进程内 `_generation_locks[file_id]` 没锁，但 DB 状态是 `generating`，就直接认为是无效状态并允许重新生成。这适合单进程开发环境，但在多 worker、多实例、重启恢复时会误杀真实运行中的任务。

影响：
- 多进程部署下，A worker 正在生成，B worker 收到新请求会把状态改成 failed 并启动另一轮。
- 可能出现同一个文件并发生成，最终配置互相覆盖。

建议：
- 使用 DB 级任务表和乐观锁：`generation_id/status/heartbeat/owner_id`。
- 只有 heartbeat 超过阈值才允许抢占。
- `update ... where status != generating or stale` 保证原子性，不用进程内 dict 作为唯一锁。

### P1：失败图表会被从最终配置中删除，用户无法在完成态看到失败占位

位置：
- `backend/app/services/bi_mvp_generation.py:302`
- `backend/app/services/bi_mvp_generation.py:320`
- `backend/app/services/bi_mvp_generation.py:333`
- `frontend/src/composables/useBiGenerationProgress.ts:149`

B3 生成失败时，SSE 过程能看到 `chart_failed`，但最终 `bi_config.charts` 只包含成功图表。落库后用户只看到成功图表数量，例如 `26 / 32` 的成功结果，失败问题只在 `generation_report.failed_charts` 里。

影响：
- 生成完成后，失败图表从看板消失，不利于用户理解缺失了哪些问题。
- 后续单图重试缺少稳定占位入口。

建议：
- 最终配置保留 failed placeholder：`status=failed`、`error_message`、`question`、`category_id`。
- 前端完成态支持失败卡片和“重新生成该图表”。
- `completedChartCount` 应区分 `success_count`、`failed_count`、`planned_count`。

### P1：`completedChartCount` 只统计成功，不统计失败，B3 进度会误导

位置：
- `frontend/src/composables/useBiGenerationProgress.ts:149`
- `frontend/src/components/bi/BIStagedGeneratingBoard.vue:67`

`done` 在分类内部包含 completed 和 failed，但全局 `completedChartCount` 只统计 completed。若有失败图表，侧边栏“已完成”会显示 `26 / 32`，但任务实际已经结束。

影响：
- 用户以为还有 6 个图表没有生成完。
- 已完成态和生成态的数字表达不一致。

建议：
- 改为 `finishedChartCount = completed + failed`。
- UI 文案拆成 `成功 26 / 失败 6 / 共 32`。
- B3 过程态和最终态保持同一口径。

### P1：B2 已有 per-category thinking，但过程态没有真正逐分类 start/done 事件

位置：
- `backend/app/services/bi_mvp_generation.py:225`
- `backend/app/services/bi_mvp_generation.py:236`
- `frontend/src/composables/useBiGenerationProgress.ts:30`
- `frontend/src/composables/useBiGenerationProgress.ts:123`

前端进度工具支持 `category_plan_start/category_plan_done`，但后端没有发这些事件。B2 是一次模型调用生成所有分类问题，然后批量输出 thinking。前端因此无法准确展示“当前正在规划哪个分类”，只能依赖默认 active tab 或最后 thinking。

影响：
- B2 的动态感有限。
- 用户点击不同分类时能看到不同 thinking，但“自动推进到当前分类”不稳定。

建议：
- 最小改法：B2 归一化后为每个 plan 依次 emit `category_plan_start`、`thinking_entry`、`category_plan_done`，每个事件带 `category_id`。
- 更真实的改法：B2 按分类逐个调用 LLM，或者按分类流式生成，这样 UI 可真实逐分类推进。

### P1：SQL 成功率低，缺少自动修复循环

位置：
- `backend/app/services/bi_mvp_generation.py:380`
- `backend/app/services/bi_mvp_generation.py:386`
- `backend/app/services/bi_mvp_generation.py:424`

当前 SQL 只做一次 LLM 生成和一次预执行。实际运行中已经出现 MySQL 语法、`PERCENTILE_CONT` 兼容性、反引号错误、窗口函数上下文错误、`only_full_group_by` 等失败。

影响：
- 成功图表数量不稳定。
- 自定义分类尤其容易失败。

建议：
- 加一轮 SQL repair：把错误信息、原 SQL、字段列表、MySQL 版本约束回传模型，最多修复 1-2 次。
- 对常见错误做规则修复：百分号转义、`PERCENTILE_CONT` 禁用、窗口函数嵌套改子查询、GROUP BY 补列。
- 如果 repair 仍失败，生成一个安全 fallback chart，例如 detail_table 或简单 GROUP BY。

### P2：`_normalize_categories` 未使用 `seen_sheet_tables`

位置：
- `backend/app/services/bi_mvp_generation.py:487`
- `backend/app/services/bi_mvp_generation.py:497`

`seen_sheet_tables` 被写入但没有读取，是遗留变量。

影响：
- 不影响行为，但会降低代码可读性。

建议：
- 删除变量，或用于防止 fallback/custom 绑定重复时的统计。

### P2：`profile_by_table` 在 `_normalize_filters` 中未使用

位置：
- `backend/app/services/bi_mvp_generation.py:631`

这是死变量。

建议：
- 删除，减少噪音。

### P2：BIDashboard 的 `activeConfig` 会在真实模式无配置时 fallback 到 demoConfig

位置：
- `frontend/src/components/BIDashboard.vue:145`

当前 `activeConfig = usingDemo ? demoConfig : (biConfig || demoConfig)`。当 `usingDemo=false` 且 `biConfig=null` 时仍会返回 demoConfig。大多数时候被 `generating` 状态挡住，但如果状态和错误边界没设好，可能在真实模式下显示 demo 数据。

影响：
- 真实/演示边界容易混淆。

建议：
- 改成 `usingDemo ? demoConfig : biConfig`。
- 空配置视图由 `!activeConfig` 明确处理。

### P2：生成成功后按钮文案仍显示 `AI 构建`

位置：
- `frontend/src/components/BIDashboard.vue:14`
- `frontend/src/components/BIDashboard.vue:20`

按钮文案依赖 `usingDemo`。如果真实配置已加载但 UI 状态未及时切换，可能显示 `AI 构建` 而不是 `重新 AI 构建`。目前 `loadBIConfig` 已设置 `usingDemo=false`，但这类状态绑定仍较脆弱。

建议：
- 按 `biConfig` 或 `biStatus === completed` 判断文案，而不是只看 `usingDemo`。

### P2：B1/B2/B3 的 prompt 与 schema 没有版本化

位置：
- `backend/app/services/bi_mvp_generation.py:20`
- `backend/app/services/bi_mvp_generation.py:64`
- `backend/app/services/bi_mvp_generation.py:92`

当前 prompt 直接写在代码里，返回结构靠自然语言约束，没有 schema 校验。

影响：
- 后续 prompt 调整容易破坏前端契约。
- 很难对生成质量做回归测试。

建议：
- 用 Pydantic model 定义 B1/B2/B3 输出 schema。
- prompt 和 schema 带版本号，例如 `bi_mvp_prompt_version=2026-05-29.2`。
- `generation_report` 落库 prompt version、model、token、耗时、重试次数。

### P2：thinking journal 写入是 read-modify-write，长任务下效率和一致性都弱

位置：
- `backend/app/routers/bi.py:152`
- `backend/app/services/db_service.py:341`

每条 thinking 都读取整段 journal，再 append 后写回 JSON 字段。条目多时性能会下降，并且并发写入需要额外锁保护。

建议：
- 迁移到独立表 `bi_thinking_entries(file_id, generation_id, step, category_id, chart_id, text, created_at)`。
- 前端 thinking API 直接分页查询。

## 推荐改造顺序

1. 先修状态与任务生命周期：
   - 后台 job 化，SSE 只订阅。
   - 引入 `generation_id` 和 heartbeat。
   - 重新生成时清理/隔离旧配置。

2. 再修结果契约：
   - 最终配置保留失败占位。
   - 前端展示成功/失败/总数。
   - 完成态支持单图重试。

3. 再提高模型生成质量：
   - B2 发逐分类 start/done 事件。
   - B3 加 SQL repair 和安全 fallback。
   - 输出 schema Pydantic 校验与版本化。

4. 最后做真实跨表：
   - 根据关联总结生成 verified join graph。
   - custom 分类允许白名单 JOIN。
   - SQL validator 支持可审计的跨表查询。

## 可快速落地的小修

- 删除 `seen_sheet_tables`、`profile_by_table` 等死变量。
- `activeConfig` 不再在真实模式 fallback 到 demo。
- `completedChartCount` 改成 `finishedChartCount`，并新增失败数。
- B2 归一化后补发 `category_plan_start/category_plan_done` 事件。
- 重新生成开始时调用 `clear_bi_config()`。
