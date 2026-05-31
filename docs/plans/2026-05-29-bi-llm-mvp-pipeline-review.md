# Review: BI LLM MVP Pipeline

## Findings

### P1: B2 前端依赖 `chart_plan_ready`，但文档把 B2 和 B3 边界写得不够清晰

当前前端在收到 `categories_ready` 后进入 B2，看 `!hasChartPlanReady` 展示问题规划；收到 `chart_plan_ready` 后进入 B3。也就是说 B2 的结束事件必须是 `chart_plan_ready`，该事件里必须带完整问题占位列表。

修正：B2 完成后立即推送 `chart_plan_ready`，其中每个 question 生成一个 chart placeholder，`chart_type` 可以先填 `table`。B3 后续通过 `chart_start/chart_done/chart_failed` 逐个更新完成状态。

### P1: SQL 由 LLM 直接生成，必须限制单表和只读

MVP 允许 LLM 生成 SQL，但如果只做字符串透传，风险太高，也容易让 `/chart-data` 在筛选注入时失败。

修正：B3 每题只允许使用当前分类绑定的 `table_name`；SQL 必须通过 `SQLValidator.sanitize_sql`；并且服务层再检查 SQL 中引用的反引号表名不能超出当前文件表集合。执行预览失败的图表丢弃并推送 `chart_failed`。

### P1: 下次直接查看要求必须在最终落库前把 preview 补齐

前端首次读取 `GET /api/bi/config/{file_id}` 时会直接渲染 `preview/tablePreview`。如果只落 SQL，没有 preview，图表区域会空或需要额外异步加载。

修正：B3 成功图表执行 SQL，写入前 20 行到 `preview/tablePreview`。最终 `bi_config.charts` 只包含成功执行的图表。

### P2: 全部内容由 LLM 生成，但服务端仍需要规范化和兜底字段

“全部内容由 LLM 生成”不等于服务端不做结构整理。前端需要固定字段名，如 `category_id/categoryId`、`chart_type/chartType`、`on_board/onBoard`。

修正：LLM 负责内容语义，服务端负责 ID、双字段兼容、排序、布局字段、字段存在性校验和 JSON 安全转换。

### P2: 公共筛选选项不能只信 LLM

LLM 可以决定哪些字段作为公共筛选，但选项值应来自数据库，避免编造筛选项。

修正：B1 只让 LLM 选择筛选字段和适用表；服务端调用 `fetch_distinct_field_values` 补充 `options/sample_values`。

### P2: 失败率过高时需要明确状态

如果所有 B3 图表都失败，仍标记 `completed` 会让用户看到空看板。

修正：如果成功图表为 0，生成任务抛错并标记 `failed`；如果部分成功，落库成功图表，报告里写 `failed_chart_count`。

## Decision

文档方案可执行，但实现时必须按上述修正处理：

1. B2 完成立即推 `chart_plan_ready`。
2. B3 并行逐图执行并推送完成。
3. 只落库成功图表和完整 preview。
4. SQL 严格只读、单文件、单表约束。
5. 生成 0 图表时失败，不落空配置。
