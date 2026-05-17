# BI 图表生成与看板体验改造 Review 文档

日期：2026-05-17  
状态：已按 review 决策更新，作为本轮实现依据。

## 1. 核心决策

BI 生成不能只停在「理解 -> 角色 -> 场景 -> 问题 -> SQL」。SQL 必须由 LLM 在完整业务上下文中生成，SQL 之后还必须有一层深度图表规划：

`理解 -> 角色 -> 场景 -> 问题 -> 单题 LLM 写 SQL -> SQL 安全校验 -> 统一问题意图 -> 图表类型规则 -> 前端渲染契约 -> 预览校验 -> 失败修复`

这层的目标不是减少生成能力，而是让 BI 逻辑越来越强：

1. 模型继续深度理解业务场景、问题意图、字段语义和字段展示名。
2. 代码规则负责兜底，确保占比、趋势、排名、双轴、KPI 等问题不会选错图。
3. SQL 由 LLM 根据用户问题、场景、完整六维理解、字段画像和样本值生成；代码模板只做兜底。
4. 前端只保留一套 BI 渲染代码，所有图表从统一契约渲染。
5. 新图表类型进入提示词，让模型在场景和问题阶段就思考「什么图最适合」。

本轮全部实现 Phase 1-3，不再分期等待。

## 2. 必须保留的产品约束

- 仓库上限：单个空间/文件的 BI 仓库最多 100 个图表。
- 默认分类上板数：每个分类仍最多 10 个。
- KPI：用 `kpi_group` 组合卡片，直接同步保存到 `bi_config`。
- 百分比：默认展示 0 位小数，例如 `38%`，不是 `38.2%`。
- 字段展示：图表和表格必须使用业务可读字段。能显示名称就不要显示 id；必须使用 id 时，要优先寻找同表中的名称字段作为展示列。
- 前端：只能保留当前 BI 看板一套渲染代码，删除未被引用的旧 `components/charts/ChartCard.vue`。

## 3. 新增提示词要求

在问题生成 Agent 的提示词中加入「图表规划」要求。模型每个问题必须输出：

- `visual_intent`：业务视觉意图，如 `share_structure`、`time_trend`、`dual_axis_compare`。
- `preferred_chart_types`：从正式图表类型中选择 1-2 个。
- `field_display_policy`：说明字段展示策略，尤其是避免 id。
- `required_fields`：渲染该图需要的字段角色。

正式图表类型：

| 类型 | 用途 |
|---|---|
| `kpi_group` | 单 Sheet 核心指标组合卡片 |
| `bar` | 分类对比、同量纲多指标对比 |
| `line` | 时间趋势、结构随时间变化 |
| `pie` | 低基数占比结构 |
| `combo` | 金额/数量 + 比率/百分比的双轴混合图 |
| `ranking` | Top/Bottom 排名，横向条形或排名表 |
| `table` | 汇总表、关联对比表 |
| `detail_table` | 明细、异常、待处理清单 |

模型可建议，但最终后端 `BIChartTypeResolver` 必须做规则校验和增强。

## 4. 问题类型与图表映射

| 问题意图 | 数据要求 | 默认图表 | SQL/字段要求 |
|---|---|---|---|
| 总览 KPI | 0 维度 + 多个核心指标 | `kpi_group` | 每个 item 一个聚合表达式，同步保存 `items` |
| 占比结构 | 1 低基数维度 + 1 指标 + 占比 | `pie` | SQL 输出维度、指标、`占比`；占比 0 位小数 |
| Top/Bottom 排名 | 1 展示维度 + 1 指标 + 排序 | `ranking` | 优先用名称字段，不用 id；默认 Top 10 |
| 时间趋势 | 时间字段 + 1 指标 | `line` | SQL 按时间桶升序，最多 24 期 |
| 结构随时间变化 | 时间字段 + 维度 + 指标/占比 | `line` | SQL 输出时间、系列、值；前端多序列 |
| 双指标对比 | 维度/时间 + 金额/数量 + 比率/百分比 | `combo` | 柱走左轴，线走右轴；百分比 0 位小数 |
| 同量纲多指标对比 | 维度/时间 + 多个同量纲指标 | `bar` 或 `line` | 分类用分组柱，时间用多折线 |
| 目标达成 | 实际 + 目标 + 达成率 | `combo` | 实际/目标为柱，达成率为线 |
| 异常/清单 | 多字段、可操作对象 | `detail_table` | 输出名称、状态、指标、原因字段 |
| 关联对比 | 关联键 + 两侧真实业务指标 | `table` | 表头使用真实字段 alias，不出现左表指标/右表指标 |

## 5. SQL 生成与图表规划层

新增单题 SQL Agent：`BIChartSQLAgent`，并保留确定性后处理模块 `BIChartTypeResolver`。

输入：

- question：包含 `analysis_type`、`visual_intent`、`preferred_chart_types`、`metrics`、`dimensions`、`time_field`。
- metric_spec：字段角色和 SQL 模板 hint。
- sheet_payload：完整六维理解、字段画像、样本值、时间覆盖、表名。
- scenario/perspective：业务场景与角色背景。
- template_sql_fallback：代码模板 SQL，仅在 LLM 失败时兜底。

输出：

- `chart_type`
- `intent_type`
- `encoding`
- LLM 生成的 `sql`
- 可选 `summary_sql`

安全与质量规则：

- LLM SQL 只允许 `SELECT` 或 `WITH ... SELECT`。
- 禁止写入、DDL、`UNION`、`INTO/OUTFILE`。
- SQL 必须先过 `SQLValidator.sanitize_sql`，再执行预览。
- LLM SQL 失败或未通过安全校验时，回退模板 SQL 并记录 warning。
- 执行失败或空结果后，仍进入单图修复 Agent；修复 SQL 也必须再次安全校验。

硬规则：

- `share/structure` 且维度基数 2-8：强制 `pie`。
- `trend/growth_rate` 且时间周期 >= 3：强制 `line`。
- `ranking`：强制 `ranking`。
- 一个字段像金额/数量，另一个字段像率/百分比/毛利率/达成率：强制 `combo`。
- `detail/anomaly_list`：强制 `detail_table`。
- `kpi`：不生成多个单卡，进入 `kpi_group`。
- 如果维度字段是 id，尝试用同表中的名称字段替换展示维度；找不到时才允许 id，并记录 warning。

## 6. 前端统一渲染契约

当前 `BIMockChart.vue` 要替换为真实统一渲染器 `BIChartRenderer.vue`，由 `BIChartCard.vue` 唯一使用。

统一 chart contract：

```json
{
  "chart_type": "combo",
  "intent_type": "dual_metric_compare",
  "encoding": {
    "x": { "field": "客户名称", "label": "客户名称", "role": "dimension" },
    "y": [
      { "field": "销售额", "label": "销售额", "axis": "left", "series_type": "bar", "format": "number" },
      { "field": "毛利率", "label": "毛利率", "axis": "right", "series_type": "line", "format": "percent" }
    ],
    "sort": { "field": "销售额", "direction": "desc" },
    "limit": 10
  }
}
```

渲染要求：

- `pie`：tooltip 展示值和百分比，百分比 0 位小数。
- `line`：支持多序列，坐标轴 `containLabel: true`，大数值格式化。
- `combo`：柱线混合，双 y 轴；右轴百分比 0 位小数。
- `ranking`：横向排名条，默认 Top 10。
- `kpi_group`：一张卡片，最多一行 5 个 item，item 可移动、删除、编辑，修改同步写回 `bi_config`。
- `table/detail_table`：表头使用 SQL alias/encoding label。

## 7. KPI Group 保存策略

后端 `_build_summary_charts()` 不再返回多张 `kpi`，而是返回 1 张 `kpi_group`：

- SQL 同时输出记录数和最多 4 个核心指标，总计最多 5 个 item。
- `items` 写入 `bi_config`。
- 前端对 item 的移动、删除、改名、格式修改，调用 chart 更新接口保存。
- `kpi_group` 在默认上板中算 1 张图。

## 8. 关联分析命名

必须删除「左表指标 / 右表指标」：

```sql
SELECT
  a.`产品名称` AS `产品名称`,
  SUM(CAST(a.`数量` AS DECIMAL(18, 4))) AS `销售明细_数量`,
  SUM(CAST(b.`销售额` AS DECIMAL(18, 4))) AS `产品信息_销售额`
FROM ...
GROUP BY a.`产品名称`
LIMIT 20
```

规则：

- 关联对象优先展示真实业务名称字段。
- 指标 alias 使用 `<表显示名>_<指标字段名>`。
- 图表说明写明 join 字段。

## 9. 本轮实现清单

1. 修改本文档为最终决策版。
2. 后端仓库上限改 100，默认分类上板仍 10。
3. 增强问题生成提示词，加入正式图表类型、visual intent、字段展示策略。
4. 后端新增图表类型解析/增强层，禁止错误图表覆盖硬规则。
5. SQL Builder 支持 `ranking`、`combo`、`detail_table`、多指标 encoding。
6. `_build_summary_charts()` 改为 `kpi_group` 并保存 items。
7. 关联分析 alias 改成业务字段名。
8. 前端类型扩展到 `kpi_group/bar/line/pie/combo/ranking/table/detail_table`。
9. 新建统一 `BIChartRenderer.vue`，替换 `BIMockChart.vue` 的使用。
10. `kpi_group` 前端支持 item 移动、删除、编辑，并同步保存。
11. 删除未被引用的旧 `frontend/src/components/charts/ChartCard.vue`。
12. 运行后端编译检查和前端构建检查。
