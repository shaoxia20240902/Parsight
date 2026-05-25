# BI 看板分阶段生成体验优化方案

## 背景

当前 BI 看板生成在表理解完成后会自动触发，用户只能看到一个整体生成态和思考日志。生成内部虽然已经有 SSE 与日志，但页面没有展示分类规划、筛选项规划、单分类/单图表执行状态，也没有把失败图表显式暴露出来，导致用户无法判断进度与失败位置。

## 目标

1. 表理解完成后进入 BI 页面先展示启动页，由用户点击“开始生成看板”。
2. 生成过程拆成可见阶段：分类规划、图表规划、按分类执行图表、完成汇总。
3. 分类名称在 Tab 与生成态中最多展示 6 个字。
4. 后端按分类顺序执行，当前分类内可有限并发；未开始分类显示等待，执行中显示加载，完成显示完成。
5. 图表级状态可见：等待、执行中、完成、失败；失败项提供重试入口。
6. 扩展图表类型契约，至少覆盖 20 种 BI 图表意图，当前渲染器优先支持可落地的 ECharts 类型，暂不支持的类型降级到相近可渲染形态。

## 后端事件契约

`POST /api/bi/generate/{file_id}` 保持 SSE 返回。新增或细化以下事件：

- `bi_start`：开始生成。
- `category_planning`：分析 Sheet 与表理解，规划业务分类。
- `categories_ready`：分类规划完成，返回 `categories`。
- `chart_planning`：规划每个分类的图表数量、类型分布与全局筛选项。
- `category_plan_start`：开始规划某个分类内的图表方案。
- `category_plan_done`：某个分类图表方案规划完成，返回 `charts_count` 与 `type_counts`。
- `chart_plan_ready`：返回 `categories`、`global_filters`、`chart_plan`。
- `category_start`：开始执行某个分类。
- `chart_start`：开始执行某个图表。
- `chart_done`：单图执行成功，包含 `chart_id`、`category_id`、`chart_type`、`title`。
- `chart_failed`：单图失败，包含 `chart_id`、`category_id`、`title`、`message`。
- `category_done`：分类执行结束，包含成功/失败数量。
- `bi_completed`：最终配置已保存，返回完整 `bi_config`。
- `error`：生成流程不可恢复失败。

## 前端状态模型

`BIDashboard.vue` 负责判断状态：

- `completed`：加载已生成配置。
- `blocked`：显示表理解未完成提示。
- `none` 或 `failed`：显示手动启动页。
- `generating`：按 SSE 阶段切换视图（见下）。

生成中分两屏，避免用户长时间盯「思考进度页」：

| 阶段 | 组件 | 说明 |
|------|------|------|
| `category_planning`（尚无 `categories_ready`） | `BIGeneratingExperience` | 轮播 + **分析区最多 3 行**（`BIThinkingSnippet`，超出框内滚动） |
| `categories_ready` 之后 | `BIStagedGeneratingBoard` | **直接进入看板布局**：顶部分类 Tab、分类下思考卡片、图表占位/执行态 |
| 失败 | `BIGeneratingExperience` | 错误与重试 |

`BIStagedGeneratingBoard.vue`：

- 分类 Tab 与完成数 `done/total`。
- 图表方案未就绪：分类下展示思考卡片（图 1 样式）。
- `chart_plan_ready` 后：渲染该分类全部图表卡片，卡内骨架 + 思考文案；`chart_done` 显示完成态。
- 顶栏保留四阶段标签（分类 / 图表方案 / 执行 / 完成）。

`BIGeneratingExperience.vue`（仅规划前）：

- 分类未出现时隐藏大块进度面板，仅保留轮播与思考区。
- 思考日志仍可展开（可选）。

失败图表重试分两层：

- 生成中失败：当前版本先提供“重试生成”入口，重新执行本次 BI 生成。
- 已生成图表失败或用户修改失败：沿用 `/api/bi/regenerate-chart` 的单图重生成能力。

## 图表类型扩展

新增统一类型集合，后端可产出，前端按支持度渲染或降级：

1. `kpi_group`：指标组
2. `kpi`：单指标卡
3. `bar`：柱状图
4. `stacked_bar`：堆叠柱状图
5. `horizontal_bar`：横向条形图
6. `line`：折线图
7. `multi_line`：多折线图
8. `area`：面积图
9. `stacked_area`：堆叠面积图
10. `pie`：饼图
11. `donut`：环形图
12. `combo`：柱线组合图
13. `ranking`：排行图
14. `table`：汇总表
15. `detail_table`：明细表
16. `treemap`：矩形树图
17. `funnel`：漏斗图
18. `scatter`：散点图
19. `bubble`：气泡图
20. `heatmap`：热力图
21. `radar`：雷达图
22. `gauge`：仪表盘
23. `waterfall`：瀑布图
24. `map`：地图

默认选择原则：

- 单指标与核心经营总览优先 `kpi` / `kpi_group`。
- 时间趋势优先 `line` / `area` / `multi_line`。
- 分类对比优先 `bar` / `horizontal_bar` / `ranking`。
- 构成占比优先 `pie` / `donut` / `treemap`。
- 漏斗转化优先 `funnel`。
- 双指标关系优先 `scatter` / `bubble`。
- 多维矩阵优先 `heatmap`。
- 目标达成优先 `gauge`。
- 明细追踪优先 `detail_table`。

## 实施步骤

1. 后端 `BIBusinessGenerator.generate` 增加 `on_progress_event` 回调。
2. 分类规划、图表规划、分类执行、图表执行处发出 SSE 事件。
3. 将 Sheet 分类流水线改为按分类顺序执行，分类内图表预览保留有限并发。
4. 扩展 `BIChartTypeResolver.VALID_TYPES` 与基础类型推断。
5. 前端 `generateBIConfig` 类型补充阶段事件字段。
6. `BIDashboard.vue` 改为手动启动生成，并把事件传给生成体验组件。
7. `BIGeneratingExperience.vue` 展示阶段进度、分类队列、图表队列与失败重试。
8. `BIInsightsBoard.vue` 分类名称限制从 4 字改为 6 字。
9. `BIChartRenderer.vue` 增加新类型渲染或降级。

## 验证

- 前端构建通过：`npm run build`。
- 后端关键模块语法通过：`python -m py_compile app/routers/bi.py app/services/bi_generation.py`。
- 手动验证：无 BI 配置时进入 BI 页应显示开始按钮；点击后能看到阶段进度、分类状态、图表状态；完成后进入看板。
