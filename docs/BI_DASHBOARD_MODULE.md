# BI 看板实现设计

> 目标：围绕现有前端 BI 看板交互，重构后端生成逻辑，让看板不是“一次性让 LLM 吐一堆图”，而是经过字段画像、分类规划、图表候选生成、SQL 校验、数据预览、质量评分和最终组装的高准确度流水线。

---

## 1. 设计结论

现有 BI 后端方向可用，但生成方式需要重做。当前 `BIClassificationAgent` 一次调用同时负责分类、图表设计、SQL、筛选字段，容易出现：

- 分类不贴合前端“Sheet 分类 + 自定义分类”模型。
- 公共筛选只是从图表 `filters` 里反推，缺少全局字段适用范围和冲突处理。
- 因为动态表字段全部是 `TEXT`，LLM 容易把不可计算字段当指标。
- SQL 没有生成后执行校验，图表可能进仓库后才失败。
- 一次输出 6-10 个图，质量不可控，无法并行提升速度。

推荐改为多阶段流水线：

```text
Sheet 元数据 + 样本
  -> 字段画像 Profiler（代码 + SQL）
  -> Sheet 分类规划（模型生成业务主题，后端校验 1:1 Sheet tabs）
  -> 公共筛选抽取（代码画像 + 模型命名排序 + MySQL 拉取选项）
  -> 每个 Sheet 并行生成图表候选
  -> 每个候选并行生成 SQL
  -> SQL 校验 + 执行预览
  -> 图表质量评分与排序
  -> 组装前端 BIInsightsState 兼容配置
```

第一版实现重点不是更多图，而是“每张图都能查出正确数据、筛选能正确作用、分类和前端交互一致”。

---

## 2. 前端约束反推

当前前端在 `frontend/src/components/bi/BIInsightsBoard.vue` 和 `frontend/src/mocks/biInsightsMock.ts` 中定义了明确的产品模型：

| 前端能力 | 后端需要提供 |
|----------|--------------|
| 左侧全局筛选 | `globalFilters[]`，字段、label、options、适用图表范围 |
| 顶部分类 Tab | 最多 5 个 Sheet 分类 + 最多 3 个自定义分类 |
| Sheet 分类 | 由模型规划业务主题，但必须与上传 Excel 的 Sheet 一一对应 |
| 自定义分类 | 由模型基于真实关联关系推荐，用户也可创建、改名、删除；后端需保存配置 |
| 图表仓库 | 最多 40 个图表，区分 `onBoard` |
| 每类看板最多 10 图 | 后端生成 `boardOrder`、`onBoard` 默认值 |
| 图表卡片 | title、question、chartType、tablePreview、sql |
| 单图筛选 | `chartFilters` 优先于全局筛选 |
| 开发者模式 | 保留 SQL、table_name、字段映射和校验信息 |
| 对话修改图表 | 单图 regenerate API，必须复用当前图表上下文 |

因此后端 BI 配置不应只返回旧版：

```json
{ "categories": [...], "charts": [...] }
```

而应返回更贴近前端的结构：

```json
{
  "version": 2,
  "file_id": "...",
  "categories": [],
  "custom_categories": [],
  "global_filters": [],
  "charts": [],
  "generation_report": {}
}
```

前端可以继续兼容旧字段，但新后端应以 v2 结构为准。

---

## 3. BI 配置数据模型

### 3.1 Category

Sheet 分类由模型生成业务主题和展示信息，后端强校验它必须保持单 Sheet 边界。

```json
{
  "id": "sheet_0",
  "name": "销售明细",
  "display_name": "销售明细",
  "icon": "sheet",
  "source": "sheet",
  "sheet_key": "销售明细",
  "table_name": "admin_1_销售明细",
  "sheet_index": 0,
  "locked": true
}
```

规则：

- `source=sheet` 的分类数量等于 Sheet 数，最多 5 个。
- 模型可以给 `display_name/description/business_theme/primary_kpis`。
- 不允许模型把多个 Sheet 合成一个 Sheet 分类，也不允许拆分一个 Sheet。
- 后端固定并校验 `id/table_name/source/sheet_index`，模型不能改这些数据绑定字段。

### 3.2 Custom Category

自定义分类由两部分组成：模型基于真实 Sheet 关联关系推荐的系统分类，以及用户后续手动创建的分类。

```json
{
  "id": "custom_经营概览",
  "name": "经营概览",
  "display_name": "经营概览",
  "icon": "chart",
  "source": "custom",
  "locked": false,
  "created_by": "user",
  "chart_ids": ["chart_x", "chart_y"]
}
```

规则：

- 最多 3 个。
- 系统推荐分类必须来自已验证的 Sheet 关联关系；如果所有 Sheet 都没有关联关系，则不生成系统自定义分类。
- 用户可新增、改名、删除自定义分类，删除后分类下图表回到默认 Sheet 分类。
- 自定义分类不是单表数据源边界，而是关联分析视图；图表必须绑定唯一主表 `table_name`，并在 `related_tables` 标明跨表来源。

### 3.3 Chart

```json
{
  "id": "chart_sheet0_001",
  "category_id": "sheet_0",
  "default_category_id": "sheet_0",
  "custom_category_ids": [],
  "title": "各区域销售额排名",
  "question": "哪些区域贡献了主要销售额？是否存在明显短板？",
  "chart_type": "bar",
  "table_name": "admin_1_销售明细",
  "sql": "SELECT ...",
  "x_field": "区域",
  "y_field": "销售额",
  "metric": {
    "field": "销售额",
    "aggregation": "sum",
    "label": "销售额"
  },
  "dimensions": ["区域"],
  "time_field": null,
  "filters": [],
  "global_filter_fields": ["区域", `月份`],
  "on_board": true,
  "collapsed": false,
  "expanded": false,
  "board_order": 0,
  "quality": {
    "score": 0.92,
    "warnings": []
  },
  "preview": {
    "columns": ["区域", "销售额"],
    "rows": []
  }
}
```

规则：

- `category_id` 是当前所在分类；`default_category_id` 是原始 Sheet 分类。
- `on_board=true` 的图每个分类最多 10 个。
- 仓库总图表最多 40 个。
- `preview.rows` 必须来自真实 SQL 执行，不能由 LLM 生成。
- SQL 不含用户筛选条件，筛选由 chart-data API 注入。

---

## 4. 公共筛选设计

公共筛选不能从 LLM 输出的图表 filters 被动合并，应在图表生成前独立抽取。

### 4.1 字段候选规则

用代码从所有 Sheet 字段画像中选候选：

| 字段角色 | 是否适合全局筛选 | 规则 |
|----------|------------------|------|
| 日期/月/季度/年 | 高 | 可解析为日期或字段名含 `日期/月/季度/时间/year/month` |
| 地区/区域/城市/省份 | 高 | 低基数枚举，跨多个 Sheet 同名或语义相近 |
| 渠道/平台/门店/部门 | 高 | 低基数枚举 |
| 状态/类型/分类 | 中 | 低基数但业务价值要评分 |
| 客户/商品/SKU/订单号 | 低 | 高基数字段不进全局筛选 |
| 金额/数量/比例 | 否 | 指标字段不作为筛选 |

候选字段需要记录适用表，而不是假设所有图表都能用：

```json
{
  "field": "区域",
  "label": "区域",
  "canonical_key": "region",
  "type": "enum",
  "options": ["华东", "华南", "华北"],
  "applies_to": [
    { "table_name": "admin_1_销售明细", "field": "区域" },
    { "table_name": "admin_1_渠道数据", "field": "区域" }
  ],
  "priority": 90
}
```

### 4.2 抽取流程

1. **代码画像**：对每个字段计算 `unique_count`、空值率、样本值、是否可数值转换、是否可日期转换。
2. **同义归并**：字段名规范化，如 `地区/区域/大区` 归到 `region`，`月份/月/销售月份` 归到 `month`。
3. **LLM 命名辅助**：只让模型决定 label、业务含义和优先级，不让模型编 options。
4. **SQL 拉取 options**：`SELECT DISTINCT` 获取真实选项，最多 50 个。
5. **适用范围绑定**：每张图表记录可被哪些全局筛选影响。

### 4.3 筛选注入

当前 `_build_where_clause()` 只按字段名直接注入：

```sql
WHERE "区域" = :filter_0
```

新逻辑应改为：

- 根据 `chart.table_name` 找 `global_filter.applies_to` 中对应字段。
- 只有适用字段才注入该图表 SQL。
- 如果图表有 `chartFilters`，同字段优先使用单图筛选。
- 不适用该表的全局筛选必须忽略，不能导致 SQL 报错。

伪代码：

```python
effective_filters = resolve_filters(
    chart_table=chart["table_name"],
    global_filters=request.filters,
    chart_filters=request.chart_filters,
    filter_registry=bi_config["global_filters"],
)
sql, params = inject_where(chart["sql"], effective_filters)
```

---

## 4.4 业务 KPI 与对比口径

BI 看板不是简单把 Sheet 字段画图。图表数据来自 Sheet 导入后的 MySQL 表，但图表问题必须站在业务视角生成关键指标：

| 指标类型 | 识别方式 | SQL 形态 | 看板用途 |
|----------|----------|----------|----------|
| 总量 KPI | 金额、销量、订单数、库存、利润等字段 | `SUM(...)`, `COUNT(*)` | 第一眼看到规模 |
| 达成率 | 同表存在“实际/完成”和“目标/预算/计划”字段 | `SUM(actual) / NULLIF(SUM(target), 0)` | 判断是否达标 |
| 占比 | 维度 + 指标 | 分组值 / 全表总值 | 判断结构集中度 |
| 排名 | 维度 + 指标 | `GROUP BY ... ORDER BY metric DESC LIMIT 10` | 找重点对象 |
| 趋势 | 时间字段 + 指标 | `DATE_FORMAT(date, '%Y-%m')` | 判断波动与增长 |
| 明细定位 | 高价值/异常/低库存/逾期等条件 | `SELECT ... LIMIT 100` | 查原因和对象 |

图表查询接口应同时返回当前筛选后的图表数据和用于对比的总数摘要：

```json
{
  "rows": [
    { "区域": "华东", "销售额": 1280000, "占比": 32.4 }
  ],
  "comparison": {
    "总销售额": 3950000
  },
  "effective_filters": {
    "月份": "2026-05"
  }
}
```

这样前端在表格或图表卡片中可以展示“当前值 / 总值 / 占比 / 达成率”，而不需要再发一次独立查询。

---

## 5. 字段画像与准确性地基

当前导入表字段全部是 MySQL `TEXT`，所以 BI 不能信 `columns.type`。必须新增 BI 字段画像。

### 5.1 字段画像输出

```json
{
  "table_name": "admin_1_销售明细",
  "field": "销售额",
  "raw_type": "text",
  "semantic_type": "currency",
  "data_role": "metric",
  "numeric_ratio": 0.99,
  "date_ratio": 0.0,
  "unique_count": 1834,
  "null_ratio": 0.01,
  "sample_values": ["1280.5", "990"],
  "recommended_aggregations": ["sum", "avg", "max"],
  "filterable": false,
  "groupable": false
}
```

### 5.2 画像实现

优先用 SQL/代码，不用 LLM：

- `COUNT(*)`
- `COUNT(DISTINCT field)`
- `SUM(field IS NULL OR field = '')`
- 数值可转比例：样本中尝试 `float(clean(value))`
- 日期可转比例：样本中尝试常见日期格式
- 高基数判断：`unique_count / row_count`
- 枚举判断：`unique_count <= 50` 或 `unique_count / row_count <= 0.2`

LLM 只做语义角色补充：

- 金额、数量、单价、利润、成本、达成率、转化率。
- ID、名称、备注、描述、地址、电话等排除项。
- 业务 KPI 优先级排序。

---

## 6. 多 Agent 生成流水线

### 6.1 Agent 划分

| Agent | 职责 | 是否并行 | 输出 |
|-------|------|----------|------|
| B0 Profiler | 字段画像，代码为主 | 按 Sheet 并行 | `field_profiles` |
| B1 Sheet Planner | 为每个 Sheet 规划分析主题 | 按 Sheet 并行 | `sheet_plan` |
| B2 Filter Planner | 规划全局筛选 | 单次 | `global_filters` |
| B3 Chart Idea Agent | 生成图表候选，不写 SQL | 按 Sheet 并行 | `chart_ideas` |
| B4 SQL Agent | 单个图表生成 SQL | 按图表并行，限流 | `sql` |
| B5 Validator | SQL 执行、预览、失败报错 | 按图表并行，限流 | `validated_chart` |
| B6 Ranker | 图表质量评分与上板排序 | 单次或按 Sheet | `ranked_charts` |
| B7 Custom Category Advisor | 推荐系统自定义分类 | 单次 | `custom_categories` |

### 6.2 并发原则

可以并行：

- 多 Sheet 字段画像。
- 多 Sheet 图表候选生成。
- 多图表 SQL 生成。
- 多图表 SQL 执行预览。

必须串行：

- 字段画像 -> 图表候选。
- 图表候选 -> SQL。
- SQL 执行 -> 质量评分。
- 质量评分 -> 默认上板布局。

推荐限流：

```python
sem = asyncio.Semaphore(4)
async with sem:
    return await agent.run(...)
```

避免 40 个图同时打 LLM 或 MySQL。

---

## 7. 图表生成策略

### 7.1 每个 Sheet 的图表配额

仓库最多 40 图，Sheet 最多 5 个。推荐：

| Sheet 数 | 每 Sheet 候选 | 每 Sheet 默认上板 |
|----------|----------------|-------------------|
| 1 | 12-18 | 8-10 |
| 2 | 8-12 | 6-8 |
| 3-5 | 6-8 | 4-6 |

总仓库超过 40 时由 B6 Ranker 裁剪。

### 7.2 图表类型选择

| 类型 | 使用条件 |
|------|----------|
| `kpi` | 单指标汇总，如总销售额、订单数、平均客单价 |
| `bar` | 低基数维度 + 数值指标排名/对比 |
| `line` | 时间字段 + 数值指标趋势 |
| `pie` | 低基数分类占比，分类数建议 2-8 |
| `table` | 明细、异常列表、低库存、逾期项 |

前端 mock 目前只支持 `bar/line/pie/table/kpi`，后端第一版应限制为这 5 类。旧 prompt 中的 `funnel/gauge/ranking` 先不要作为默认输出，除非前端渲染已经补齐。

### 7.3 图表质量评分

每张图生成后评分：

| 评分项 | 权重 |
|--------|------|
| SQL 可执行且返回非空 | 35 |
| 指标字段可数值计算 | 20 |
| 图表类型与字段角色匹配 | 15 |
| 问题有业务价值 | 15 |
| 与同 Sheet 其他图不重复 | 10 |
| 支持公共筛选 | 5 |

低于 70 分进仓库但不上板；低于 50 分直接报错并阻断本次生成，避免保存低质量图表。

---

## 8. SQL 生成与校验

### 8.1 SQL 规则

- 只允许 `SELECT`。
- 表名、字段名必须反引号包裹。
- 不写动态筛选 `WHERE`，除非图表本身是固定业务条件，例如“库存低于安全库存”。
- 指标字段是 TEXT 时必须显式转换：

```sql
SUM(CAST(REPLACE(REPLACE(REPLACE(`销售额`, ',', ''), '￥', ''), '%', '') AS DECIMAL(18,4))) AS `销售额`
```

- 日期字段如果是文本月份，可以直接分组；如果是完整日期，按需要生成：

```sql
DATE_FORMAT(`订单日期`, '%Y-%m') AS `月份`
```

- 每张图表 SQL 默认 `LIMIT 100`，排名/柱状图建议 `LIMIT 10`。

### 8.2 校验流程

1. `SQLValidator.sanitize_sql()`。
2. 检查只引用允许的 `table_name`。
3. 检查引用字段存在于该表。
4. 执行 SQL 获取 preview。
5. 检查返回列数适合图表类型。
6. 检查行数非空。
7. 失败时直接报错，停止保存本次 BI 配置。

### 8.3 预览数据

`preview` 必须由后端真实查询得到：

```json
{
  "columns": ["区域", "销售额"],
  "rows": [
    { "区域": "华东", "销售额": 1280000 }
  ]
}
```

前端 `BIMiniTablePreview` 和仓库卡片直接使用该 preview。

---

## 9. 自定义分类模型

自定义分类本质是关联分析和用户组织图表的容器，不应绕过后端 SQL 校验。

### 9.1 后端保存

当前 `bi_config` 存在 `file_records.bi_config`，第一版可继续 JSON 保存：

```json
{
  "custom_categories": [],
  "chart_category_overrides": {
    "chart_sheet0_001": "custom_经营"
  }
}
```

后续如果要多用户、多版本、撤销恢复，再拆表：

- `bi_dashboards`
- `bi_categories`
- `bi_charts`
- `bi_chart_layouts`

### 9.2 用户操作 API

建议新增：

| API | 用途 |
|-----|------|
| `POST /api/bi/categories` | 新增自定义分类 |
| `PATCH /api/bi/categories/{id}` | 修改自定义分类名称 |
| `DELETE /api/bi/categories/{id}` | 删除自定义分类，图表回到默认 Sheet 分类 |
| `PATCH /api/bi/charts/{id}` | 修改 `category_id/on_board/collapsed/expanded/board_order` |
| `PATCH /api/bi/layout` | 批量保存拖拽排序 |

这些操作不需要 LLM。

### 9.3 系统推荐自定义分类

B7 只在字段画像确认 Sheet 之间存在关联关系时运行；如果所有 Sheet 都没有可验证关联，不生成系统自定义分类，也不调用模型硬凑专题。

可验证关联必须满足：

- 两个 Sheet 存在候选关联字段，例如客户 ID、商品 ID、订单号、SKU、地区编码等。
- 字段取值有真实重叠，且 overlap score 达到阈值。
- 能用 MySQL `JOIN` 跑出非空预览数据。

存在关联时，可推荐 0-2 个系统自定义分类，例如：

- 经营概览：挑选每个 Sheet 的核心 KPI 和趋势。
- 异常预警：挑选库存不足、订单取消率、成本异常等图。
- 客户关联：客户信息 × 销售/订单数据。
- 商品关联：商品/SKU 主数据 × 库存/销售数据。

但必须遵守：

- 系统推荐分类也占 3 个自定义分类上限。
- 用户可删除。
- 每个系统分类只引用已有图表，不生成额外 SQL。

---

## 10. 后端 API 设计

### 10.1 生成配置

```http
POST /api/bi/generate/{file_id}
Accept: text/event-stream
```

SSE steps：

| step | 含义 |
|------|------|
| `profiling` | 字段画像 |
| `planning` | Sheet 分析规划 |
| `filters` | 公共筛选抽取 |
| `chart_ideas` | 图表候选生成 |
| `sql_generation` | SQL 并行生成 |
| `validation` | SQL 执行与预览 |
| `ranking` | 质量评分与上板排序 |
| `saving` | 保存配置 |
| `completed` | 返回 v2 config |

### 10.2 获取配置

```http
GET /api/bi/config/{file_id}
```

返回 v2 config，前端直接映射到 `BIInsightsState`。

### 10.3 图表数据

```http
POST /api/bi/chart-data
```

请求：

```json
{
  "file_id": "...",
  "chart_id": "...",
  "filters": { "region": "华东" },
  "chart_filters": { "month": "2025-01" },
  "page": 1,
  "page_size": 20
}
```

响应：

```json
{
  "code": 200,
  "data": {
    "chart_type": "bar",
    "chart_id": "...",
    "rows": [],
    "row_count": 10,
    "effective_filters": []
  }
}
```

### 10.4 单图对话修改

```http
POST /api/bi/regenerate-chart
```

要点：

- 不允许返回不存在字段。
- 不允许改变 `id`。
- 默认保持原 `category_id/on_board/board_order`。
- 必须执行预览 SQL 后再保存。

---

## 11. 提示词设计

下面是建议替换旧 `BI_CLASSIFICATION_SYSTEM_PROMPT` 的分阶段提示词。

### 11.1 B1 Sheet Planner Prompt

```text
你是资深 BI 产品架构师，负责把 Excel 多 Sheet 数据规划成 BI 看板分类。

必须遵守：
1. 只能输出 JSON 对象，不要 Markdown。
2. sheet_categories 必须与输入 sheets 一一对应，不能新增、删除、合并或拆分 Sheet。
3. 每个 Sheet 分类只代表单 Sheet 数据边界，不能把两个 Sheet 合到 sheet 分类。
4. 你可以优化 display_name、description、business_theme、primary_kpis，但不能改变 sheet_index/table_name/sheet_name 的绑定。
5. global_filter_labels 只做业务命名和优先级建议，真实 options 由 MySQL 查询得到，不能编造筛选项。
6. 不确定时直接在 warnings 说明，不要生成兜底分类。

返回格式：
{
  "sheet_categories": [
    {
      "sheet_index": 0,
      "display_name": "销售明细",
      "description": "用于分析订单、销售额、区域、时间趋势的明细事实表",
      "business_theme": "销售执行",
      "primary_kpis": ["销售额", "销量"]
    }
  ],
  "global_filter_labels": [
    {
      "canonical_key": "region",
      "label": "区域",
      "priority": 90,
      "business_meaning": "按区域观察经营差异"
    }
  ],
  "warnings": []
}
```

### 11.2 B2 Global Filter Planner Prompt

```text
你是 BI 筛选器设计师。你只负责给已有筛选候选字段命名和排序，不生成 SQL，不编造选项。

输入：
- candidate_filters：由代码生成，包含 field、canonical_key、options、applies_to、unique_count、coverage
- sheet themes

任务：
1. 从候选中选择最多 6 个公共筛选器。
2. 给每个筛选器一个短 label。
3. 排序：越通用、越常用、跨表覆盖越高，priority 越高。

严格输出 JSON：
{
  "global_filters": [
    {
      "canonical_key": "region",
      "label": "区域",
      "priority": 90,
      "reason": "跨销售和渠道表通用"
    }
  ]
}

约束：
- 只能使用输入里的 canonical_key。
- 不要输出 options，options 由 SQL DISTINCT 提供。
- 不要选择高基数 ID/名称字段。
```

### 11.3 B3 Chart Idea Prompt

```text
你是资深 BI 分析师。你只负责为单个 Sheet 设计图表想法，不写 SQL。

输入：
- sheet_plan
- field_profiles
- global_filters
- 前端支持的图表类型：kpi, bar, line, pie, table
- 配额：生成 N 个候选，其中默认上板 M 个

任务：
生成覆盖 KPI、趋势、结构、排名、明细/异常的图表候选。

严格输出 JSON：
{
  "chart_ideas": [
    {
      "title": "...",
      "question": "...",
      "chart_type": "kpi|bar|line|pie|table",
      "analysis_type": "kpi|trend|ranking|composition|exception|detail",
      "metric": {"field": "...", "aggregation": "sum|avg|count|max|min", "label": "..."},
      "dimensions": ["..."],
      "time_field": "...",
      "filter_fields": ["..."],
      "default_on_board": true,
      "priority": 90,
      "reason": "..."
    }
  ]
}

约束：
- 不要编造字段。
- line 必须有 time_field。
- pie 的维度唯一值建议不超过 8。
- kpi 只能有 0-1 个维度。
- table 必须说明明细或异常条件。
- 同一个 Sheet 内图表不要重复表达同一问题。
```

### 11.4 B4 SQL Prompt

```text
你是 MySQL SQL 专家。你只负责把一个图表想法转换成一条 SELECT SQL。

输入：
- table_name
- allowed_fields
- field_profiles
- chart_idea

严格输出 JSON：
{
  "sql": "SELECT ...",
  "x_field": "...",
  "y_field": "...",
  "output_columns": ["...", "..."],
  "notes": []
}

SQL 规则：
- 只输出 SELECT。
- 表名和字段名必须用反引号。
- 只能使用 allowed_fields 中存在的字段。
- 不要加入全局筛选 WHERE，系统会动态注入。
- 如果字段是文本但 numeric_ratio >= 0.8，数值计算必须使用 MySQL `CAST + REPLACE` 清洗逗号、货币符号和百分号后转 `DECIMAL(18,4)`。
- 聚合查询必须 GROUP BY 非聚合字段。
- bar/pie 默认 LIMIT 10。
- table 默认 LIMIT 100。
- line 必须按时间升序 ORDER BY。
```

### 11.5 B5 SQL Error Diagnostic Prompt

```text
你是 MySQL SQL 诊断专家。上一条 SQL 执行失败或预览不符合图表要求。

输入：
- chart_idea
- failed_sql
- error_message
- allowed_fields
- field_profiles
- preview_requirement

任务：
解释失败原因，指出具体错误字段、表名、聚合口径或 MySQL 语法问题。不要生成替代 SQL，不要降级图表。

严格输出 JSON：
{
  "error_type": "invalid_field|invalid_table|mysql_syntax|empty_result|bad_metric|bad_chart_shape",
  "reason": "...",
  "blocking": true
}

约束：
- 有问题就报错，便于开发排查。
- 不输出兜底 SQL。
```

### 11.6 B6 Ranker Prompt

```text
你是 BI 看板主编。你负责从已通过 SQL 校验的图表中选择默认上板图表和排序。

输入：
- categories
- validated_charts：含 preview、quality signals
- 前端限制：每个分类最多 10 个上板，仓库最多 40 个

任务：
1. 每个 Sheet 分类选择最有代表性的图表上板。
2. 排序：KPI/核心趋势优先，其次排名/结构，再是明细。
3. 去掉重复、低价值、空结果图表。

严格输出 JSON：
{
  "ranked_charts": [
    {
      "chart_id": "...",
      "on_board": true,
      "board_order": 0,
      "quality_score": 92,
      "quality_notes": ["..."]
    }
  ]
}
```

### 11.7 B7 Custom Category Advisor Prompt

```text
你是资深 BI 分析负责人，负责基于已验证的 Sheet 关联关系规划系统推荐的自定义分类。

必须遵守：
1. 只能输出 JSON 对象，不要 Markdown。
2. 只有输入 relationships 中存在真实 overlap_count > 0 的关联时，才允许生成 custom_categories。
3. 自定义分类用于关联后的分析图表，不是单 Sheet 分类；每个分类必须绑定 relationship_id。
4. 最多输出 3 个 custom_categories，优先输出业务价值最高的 1-2 个。
5. 自定义分类必须 marked created_by=system，用户后续可以删除或改名。
6. chart_ideas 只输出业务问题和图表意图，不输出 SQL；SQL 由后端 MySQL 生成和执行校验。
7. 没有关联价值时返回空数组，不要兜底。

返回格式：
{
  "custom_categories": [
    {
      "relationship_id": "rel_1",
      "name": "客户分析",
      "display_name": "客户分析",
      "description": "基于销售明细与客户信息的关联，分析客户结构与贡献",
      "analysis_goal": "识别高价值客户和客户结构差异",
      "chart_ideas": [
        {
          "title": "客户贡献对比",
          "question": "不同客户在关联数据中的关键指标表现如何？",
          "chart_type": "table"
        }
      ]
    }
  ],
  "warnings": []
}
```

---

## 12. 代码落地建议

建议新增：

```text
backend/app/services/bi_generation.py
backend/app/services/bi_profiler.py
backend/app/services/bi_planner.py
backend/app/services/bi_filters.py
backend/app/services/bi_sql_validation.py
backend/app/agents/bi_agents.py
```

保留现有 `backend/app/agents/bi_agent.py` 作为兼容层，逐步替换为：

```python
class BIOrchestrator:
    async def generate(file_id):
        sheets = await load_sheets(file_id)
        profiles = await profile_sheets_parallel(sheets)
        sheet_plans = await plan_sheets_parallel(profiles)
        filters = await build_global_filters(profiles, sheet_plans)
        ideas = await generate_chart_ideas_parallel(sheet_plans, filters)
        sql_charts = await generate_sql_parallel(ideas)
        validated = await validate_and_preview_parallel(sql_charts)
        ranked = await rank_charts(validated)
        custom = await suggest_custom_categories(ranked)
        return assemble_config(...)
```

第一阶段可以不建新表，继续保存到 `file_records.bi_config`。但配置中必须写入 `version=2`，方便前端兼容。

---

## 13. 与现有实现的差异

| 项 | 当前实现 | 新设计 |
|----|----------|--------|
| 分类 | LLM 生成业务分类 | 代码生成 Sheet 分类，用户管理自定义分类 |
| 图表生成 | 单次 LLM 批量生成 | 每 Sheet/每图拆分，可并行 |
| 字段类型 | 信 `columns.type` | 增加字段画像，识别指标/日期/枚举 |
| 公共筛选 | 从 chart.filters 合并 | 独立抽取，绑定适用表字段 |
| SQL | LLM 直接给，保存前不执行 | 保存前校验、执行、预览；失败直接报错 |
| 图表数量 | 至少 6-10 个笼统要求 | 按 Sheet 配额，仓库最多 40 |
| 前端适配 | 后端结构和 mock 不一致 | 直接输出前端状态所需字段 |
| 自定义分类 | 无后端模型 | 保存用户分类和图表归属 |
| 单图修改 | 旧实现可能在失败时伪成功 | 必须校验 SQL 后保存，失败透明 |

---

## 14. 实施顺序

1. **定义 v2 BI config schema**，让前端 mock 类型和后端字段对齐。
2. **实现字段画像**，解决 TEXT 字段下的指标/日期/枚举识别。
3. **重写公共筛选抽取**，输出 `global_filters` 和 `applies_to`。
4. **拆分 BI Agent**：Sheet Planner、Chart Idea、SQL、Repair、Ranker。
5. **生成前执行 SQL 预览**，把 preview 写入 config。
6. **前端 BI 去 Mock**，接 `config/chart-data/filter-options`。
7. **自定义分类持久化 API**，保存添加、删除、拖拽、上板状态。
8. **单图对话修改**，接真实 regenerate，并执行校验后保存。

---

## 15. 验收标准

| 维度 | 标准 |
|------|------|
| 分类 | Sheet 分类与上传 Sheet 一一对应；自定义分类可增删并保存 |
| 准确性 | 所有图表 preview 来自真实 SQL |
| SQL | 保存的图表 SQL 全部可执行 |
| 筛选 | 全局筛选只作用于适用图表；单图筛选优先 |
| 图表质量 | 上板图表覆盖 KPI、趋势、结构、排名/明细，不重复堆图 |
| 前端适配 | 仓库、上板、拖拽、折叠、放大、开发者 SQL 模式都有后端状态 |
| 失败处理 | LLM/SQL 失败不保存假图表，不返回假数据 |
| 性能 | 多 Sheet、多图 SQL 生成和校验并行限流执行 |

---

## 16. 待确认问题

1. 系统是否默认推荐“经营概览/异常预警”这类自定义分类，还是只允许用户手动创建？
2. 前端第一版是否只保留 `bar/line/pie/table/kpi`，暂不支持 `funnel/gauge/ranking`？
3. BI 配置第一版继续存 `file_records.bi_config`，还是现在就拆成多张表？
4. 上传后是否继续自动生成 BI，还是进入 BI 页面再生成，减少上传等待？
5. 公共筛选最多展示几个？建议 4-6 个，避免左侧筛选过长。
