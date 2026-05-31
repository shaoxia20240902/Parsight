# BI LLM MVP Pipeline

## 目标

本版先做最小可用后端链路，让 BI 生成流程真实调用 LLM，能够驱动前端三阶段展示，并在生成完成后落库，用户下次进入直接查看已生成看板。

暂不追求完整复杂 Agent 编排。复杂的行业推断、角色场景拆解、多轮修复可以后续迭代。本版核心是：

1. 所有 BI 内容由 LLM 生成，包括分类、公共筛选、问题、图表类型、SQL、思考过程。
2. 服务端通过现有 `POST /api/bi/generate/{file_id}` SSE 推送阶段事件，前端无需换协议。
3. 生成完成后写入 `file_records.bi_config`，状态写为 `completed`。
4. 下次进入时 `GET /api/bi/status/{file_id}` 返回 `completed`，`GET /api/bi/config/{file_id}` 直接读取已落库配置。

## 现有能力复用

复用现有表：

- `file_records.bi_config`：最终 BI 配置。
- `file_records.bi_thinking_journal`：生成过程自然语言思考记录。
- `file_records.bi_status`、`bi_generation_started_at`、`bi_generation_finished_at`：生成状态。
- `sheet_meta.understanding_content`：单表理解内容。
- `spaces.relations_content`：跨表关联总结。

复用现有接口：

- `POST /api/bi/generate/{file_id}`：SSE 生成。
- `GET /api/bi/status/{file_id}`：只读状态。
- `GET /api/bi/config/{file_id}`：读取已生成配置。
- `POST /api/bi/chart-data`：按已落库 SQL 查询图表数据。

复用现有前端事件契约：

- `categories_ready`
- `thinking_entry`
- `chart_plan_ready`
- `chart_start`
- `chart_done`
- `chart_failed`
- `bi_completed`

## MVP 三阶段

### B1 分类与公共筛选

输入给 LLM：

- 文件名、Sheet 列表、字段、样本值。
- 每张表的单表理解。
- 空间关联总结。

LLM 输出：

```json
{
  "thinking": "自然语言思考过程",
  "categories": [
    {
      "id": "sheet_sales",
      "name": "销售明细",
      "display_name": "销售明细",
      "source": "sheet",
      "table_name": "实际物理表名"
    }
  ],
  "global_filters": [
    {
      "field": "区域",
      "label": "区域",
      "canonical_key": "区域",
      "applies_to": [
        {"table_name": "实际物理表名", "field": "区域"}
      ]
    }
  ]
}
```

服务端处理：

- 校验分类数量不超过 8。
- 校验 `table_name` 和筛选字段必须存在。
- 为筛选字段补充 `options/sample_values`。
- SSE 推送 `categories_ready`，携带分类和公共筛选。

### B2 问题定义

输入给 LLM：

- B1 分类结果。
- 每个分类对应表字段、单表理解、关联总结。

LLM 输出：

```json
{
  "thinking": "自然语言思考过程",
  "category_plans": [
    {
      "category_id": "sheet_sales",
      "category_name": "销售明细",
      "questions": [
        {
          "id": "q_sales_kpi",
          "title": "销售核心指标",
          "question": "整体销售额、利润、订单与客户规模是否健康？",
          "priority": 100
        }
      ]
    }
  ]
}
```

服务端处理：

- 每个分类保留最多 8 个问题。
- 生成初始 `chart_plan`，图表类型先标记为 `pending`，用于前端显示空白占位。
- SSE 推送 `chart_plan_ready` 前先等待 B3 的第一批图表规划结果。为匹配当前前端，MVP 可以在 B3 图表类型和 SQL 生成前一次性推送完整 `chart_plan`，其中图表类型填 `table` 或 LLM 若已给出则填真实类型。

### B3 图表类型与 SQL

对 B2 的每个问题并行调用 LLM。每个问题一次模型调用，输出图表类型、SQL、encoding、指标配置。

输入给 LLM：

- 当前问题。
- 当前分类表名、字段、样本值、单表理解。
- 关联总结。
- 公共筛选定义。

LLM 输出：

```json
{
  "thinking": "自然语言思考过程",
  "chart": {
    "chart_type": "bar",
    "title": "区域销售额对比",
    "question": "不同区域销售贡献是否均衡？",
    "sql": "SELECT `区域`, SUM(...) AS `销售额` FROM `table` GROUP BY `区域` ORDER BY `销售额` DESC LIMIT 10",
    "encoding": {
      "x": {"field": "区域", "label": "区域", "role": "dimension"},
      "y": [{"field": "销售额", "label": "销售额", "format": "number"}]
    },
    "items": []
  }
}
```

服务端处理：

- SQL 必须通过安全校验：只允许 `SELECT` 或 `WITH ... SELECT`，禁止写操作。
- SQL 中使用的表名必须是当前文件内表。
- 执行一次 SQL，成功后把前 20 行写入 `preview/tablePreview`。
- 成功一个推送一个 `chart_done`。
- 失败则推送 `chart_failed`，MVP 不做多轮修复，只丢弃失败图表并记录报告。

## 最终配置结构

最终写入 `file_records.bi_config`：

```json
{
  "version": 4,
  "file_id": "...",
  "dialect": "mysql",
  "categories": [],
  "custom_categories": [],
  "global_filters": [],
  "charts": [],
  "generation_report": {
    "strategy": "llm_mvp_three_stage",
    "sheet_count": 5,
    "category_count": 8,
    "chart_count": 32,
    "failed_chart_count": 2
  }
}
```

每个 chart 至少包含：

- `id`
- `category_id/categoryId`
- `title`
- `question/description`
- `chart_type/chartType`
- `sql`
- `table_name`
- `encoding`
- `items`
- `on_board/onBoard`
- `expanded`
- `board_order/boardOrder`
- `preview/tablePreview`

## 实现范围

新增：

- `backend/app/services/bi_mvp_generation.py`
  - `BILlmMVPGenerator`
  - 内部三个 LLM 调用：B1、B2、B3
  - 输出现有前端可消费的 BI config。

修改：

- `backend/app/routers/bi.py`
  - `_generate_bi_events` 改用 `BILlmMVPGenerator`。
  - 保留状态锁、thinking journal、落库逻辑。

不改：

- 数据模块。
- 表理解模块。
- 关联总结模块。
- 前端协议。
- 数据库表结构。

## 后续迭代

1. B1/B2/B3 拆成更细 Agent，每步加模型自检。
2. B3 增加 SQL 修复模型调用。
3. 加图表质量评分，决定上板顺序。
4. 支持跨表 SQL，而不是 MVP 只允许单表图表。
5. 把 LLM 生成过程保存为更结构化的阶段日志，支持前端回放。
