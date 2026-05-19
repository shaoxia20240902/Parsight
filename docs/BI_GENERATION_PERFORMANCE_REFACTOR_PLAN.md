# BI 看板生成性能与稳定性改造方案

日期：2026-05-18

## 结论

当前 BI 生成慢的主因不是单个 SQL 慢，而是 LLM 编排过度展开：单 Sheet 会走「选角 -> 每角色场景 -> 每场景问题 -> 每角色审视 -> 汇总筛选 -> 逐题 SQL LLM -> SQL 预执行/修复」链路。日志中的 1 个 Sheet 被拆成 4 个角色、12 个场景、约 34 个问题是现有提示词和流程的自然结果。

系统里已经有“汇总筛选 6-8 个问题”的 Aggregator，但它发生在问题生成之后；并且后续 SQL LLM 生成在单 Sheet 内仍是逐题串行。`MAX_WAREHOUSE = 100` 也会让系统最多保留 100 张图，因此多 Sheet 或关联分析下会继续向 100 张膨胀，和“每个 BI 分类 6-8 个核心图”的产品预期不一致。

## 从日志还原的问题

### 1. 单 Sheet 问题爆炸

日志显示：

- 选定 4 个业务视角。
- 每个角色拆 3 个场景。
- 每个场景生成 2-3 个问题。

这会产生约 `4 * 3 * 3 = 36` 个候选问题。现有代码允许这个结果：

- `ROLE_PICKER_SYSTEM` 约束角色为 2-4 个。
- `SCENARIO_SYSTEM` 约束每角色 1-3 个场景。
- `QUESTION_SYSTEM` 约束每场景 1-3 个问题。
- `QUESTION_REVIEW_SYSTEM` 每角色还可能补最多 3 题。

Aggregator 只在最后从候选问题中精选 6-8 个，但它不能减少前面已经发生的 LLM 调用数量。

### 2. 图表数量控制位置太晚

`BIBusinessGenerator.MAX_WAREHOUSE = 100` 是全局仓库上限，不是每个 Sheet/分类的生成目标。`MAX_BOARD_PER_CATEGORY = 8` 只控制哪些图展示在看板上，不阻止仓库继续生成和保存更多图。

这导致两层浪费：

- 生成阶段仍为大量候选问题调用 SQL LLM、预执行 SQL、修复 SQL。
- 最后只把部分图标记为 `on_board=false`，但前面的成本已经花完。

### 3. SQL LLM 生成没有在单 Sheet 内并行

`BIBlueprintPipeline` 对场景和问题生成用了 `asyncio.gather` 并发；但 `_generate_sheet_pipeline` 中从问题到图表草稿的循环是串行 `await _question_to_chart_draft(...)`。

也就是说，精选后的每个问题都要依次等待 SQL LLM 返回。若每个 SQL LLM 需要 30-90 秒，6-8 个问题就会直接消耗数分钟到十几分钟；如果 Aggregator 失败保留了全部 30+ 问题，就会变成几十分钟甚至 1 小时。

### 4. Aggregator 失败会退回“保留全部”

当前逻辑中，Aggregator 如果失败、超时或返回空结果，会记录 warning 并保留全部问题。这是危险默认值。对于生成成本来说，失败时应该降级为确定性 top N，而不是放大到全部。

### 5. SQL 对 MySQL `only_full_group_by` 不稳

日志中的 SQL 都有同类问题：

```sql
SELECT 维度, SUM(指标), SUM(指标) / total.total_value
FROM table
CROSS JOIN (SELECT SUM(指标) AS total_value FROM table) total
GROUP BY 维度
```

在 MySQL 开启 `only_full_group_by` 时，`total.total_value` 虽然来自单行 CROSS JOIN，但仍被视为非聚合列，必须写成 `MAX(total.total_value)`、`ANY_VALUE(total.total_value)` 或改成外层子查询/窗口写法。

正确方向是改 SQL 生成规则和修复规则，不应该关闭数据库 SQL mode。

### 6. 最后一步失败不应该导致整体重新生成

日志里的 `Decimal is not JSON serializable` 发生在 SSE `bi_completed` 返回阶段。当前代码已经在 `json.dumps(..., default=_json_default)` 里处理 Decimal，但日志说明运行时版本或某个分支还没有带这个参数。

更大的设计问题是：生成完成前才一次性落库。如果最终 SSE 序列化、连接断开或某个尾部动作失败，用户体验上就会看到整个流程失败，并倾向于重新生成。生成流程需要阶段性持久化和可恢复状态，而不是“最后一次性提交”。

## 目标状态

每个 Sheet/分类生成 6-8 个高质量上板问题，最多附带少量候选仓库图。单 Sheet 的 LLM 主链路目标耗时应控制在 5-10 分钟内，失败时可以返回部分成功结果。

推荐目标：

- 每个 Sheet：1 张 KPI 总览 + 6-8 张角色/问题图。
- 每个自定义关联分类：最多 2-3 张图。
- 全局仓库上限从 100 改为可配置，默认 `sheet_count * 10 + relation_count * 3`，并设置硬上限 40 或 50。
- SQL 失败的图只丢弃或局部修复，不拖垮整个 BI 配置。

## 改造方案

### 阶段 1：先止血

1. 把 Aggregator 失败策略从“保留全部”改成确定性 top 8：
   - 按 `priority` 排序。
   - 做图表类型去重和维度去重。
   - 优先保留 `kpi_overview`、趋势、结构、排名、明细各 1-2 个。

2. 在 `_generate_sheet_pipeline` 中加硬上限：
   - 蓝图回传后立刻 flatten 问题。
   - 超过 8 个时，无论 Aggregator 是否成功，都只允许 8 个进入 SQL 生成。
   - summary 图单独保留，不计入 6-8 个分析问题。

3. 修 SQL 提示词：
   - 明确 `only_full_group_by` 约束。
   - 禁止在分组查询 SELECT 中直接引用 CROSS JOIN 总数列。
   - 要求使用 `MAX(total.xxx)`、外层 SELECT 包裹、或窗口函数。

4. 最终 SSE 全部统一使用 `_json_default`，并加一个 `json_safe` 递归转换函数，避免 Decimal、date、datetime 混入时再次失败。

### 阶段 2：提速

1. SQL LLM 并行：
   - 将 `_generate_sheet_pipeline` 中逐题 `await` 改成 `asyncio.gather`。
   - 使用现有 `self.sem` 控制并发，建议默认 4，可通过环境变量配置。

2. 去掉不必要的 SQL LLM：
   - 先用模板 SQL 编译并预执行。
   - 模板 SQL 可执行且图表契约完整时，不调用 SQL LLM。
   - 只有复杂派生指标、模板编译失败、或预执行失败时才调用 SQL LLM/Repair LLM。

3. 降低早期问题生成调用数：
   - 每角色最多 2 个场景。
   - 每场景最多 2 个问题。
   - 审视步骤改为“只指出 gap，不直接补题”，补题交给 Aggregator 一次性处理。

### 阶段 3：重构成更符合预期的智能体链路

建议把当前链路：

```text
角色 -> 场景 -> 问题 -> 审视 -> 汇总筛选 -> 每题 SQL
```

改成：

```text
Sheet 资产理解
-> 多角色并行给洞察方向，不直接产图
-> 统一策展智能体合并为 6-8 个核心问题
-> 图表契约选择
-> SQL 编译优先，LLM 只处理复杂/失败项
-> 并行预执行和局部修复
-> 分阶段保存 BI 配置
```

核心变化是：多角色负责“发现值得问什么”，不是每个角色都直接产出多张图。最终只有策展智能体有权决定进入图表生成的问题清单。

## 建议实现清单

### P0：稳定性

- 增加 `json_safe_bi_config`，所有 SSE 和 DB 写入前统一转换 Decimal/date/datetime。
- `generate_bi_config` 不在开始时立即 `clear_bi_config`，改为保留旧配置，生成成功后原子替换；生成中状态单独记录。
- SQL 失败图进入 `charts_dropped`，不影响其他图。
- Aggregator 失败强制 deterministic top 8。

### P1：性能

- `_generate_sheet_pipeline` 的问题转图表草稿改并发。
- 模板 SQL 优先，LLM SQL 作为 fallback。
- LLMClient 复用 httpx client 或做连接池，避免每次调用创建新 client。
- 添加每步耗时日志：role/scenario/question/aggregate/sql/preview/repair。

### P2：产品效果

- 把“仓库上限 100”替换为“按 Sheet/分类预算”。
- BI 配置里保存 `candidate_questions` 和 `selected_questions`，方便前端展示为什么选这些图。
- 支持继续生成/补充图，而不是失败后只能全量重跑。

## 验收标准

- 单 Sheet 默认最终图表数：7-9 张（含 1 张核心指标总览）。
- Aggregator 失败时最终仍不超过 9 张。
- 任意单图 SQL 失败时，最终 BI 状态仍可 completed，失败图写入 `generation_report.charts_dropped`。
- SQL 中 CROSS JOIN 总计列在 `only_full_group_by` 下可执行。
- SSE completed 事件不会因 Decimal/date/datetime 序列化失败。
- 生成日志能看到每类 LLM 调用次数和耗时。

