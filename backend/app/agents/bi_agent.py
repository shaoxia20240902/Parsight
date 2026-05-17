"""
BI 分类智能体 - 分析 Sheet 结构，生成 BI 看板配置

利用 LLM 分析数据表的 Schema 信息，自动：
1. 将数据分为 1-5 个业务类别（销售分析/财务分析/项目进度/人力资源/客户分析等）
2. 为每个 Sheet 生成尽可能多的图表配置（最少 6-10 个）
3. 覆盖增强图表类型：kpi_group, bar, line, pie, combo, ranking, table, detail_table
4. 每个图表包含 SQL 查询和可筛选维度
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent
from app.services.llm_client import LLMClient
from app.utils.sql_validator import SQLValidator

logger = logging.getLogger(__name__)

# BI 分类 Prompt
BI_CLASSIFICATION_SYSTEM_PROMPT = """你是一个专业的BI数据分析师和数据可视化专家。你的任务是根据用户提供的数据表Schema信息，智能生成一份完整的BI看板配置。

## 你的任务

### 1. 业务分类
仔细分析所有Sheet的字段名、数据类型、数据摘要等信息，将数据归类为1-5个业务类别。
常见类别示例：销售分析、财务分析、项目进度、人力资源、客户分析、供应链管理、运营分析、市场分析

### 2. 图表配置
为数据生成尽可能多的图表配置（**至少6-10个**，如果数据维度丰富可以更多），覆盖以下图表类型：

| 类型 | chart_type | 适用场景 | SQL模式 |
|------|-----------|---------|---------|
| 柱状图 | bar | 对比分析、排名展示 | GROUP BY 维度, AGG(指标) |
| 折线图 | line | 时间趋势分析 | GROUP BY 日期字段, AGG(指标) |
| 饼图 | pie | 占比/分布分析 | GROUP BY 维度, AGG(指标) |
| 混合图 | combo | 金额/数量 + 比率/百分比双轴对比 | GROUP BY 维度/时间, 多指标 |
| KPI组 | kpi_group | 核心指标总览 | 单行多指标 |
| 排名图 | ranking | Top N 和 Bottom N | GROUP BY 维度, AGG(指标) ORDER DESC+ASC |
| 表格 | table | 明细数据展示 | SELECT * |
| 明细表 | detail_table | 异常、逾期、低库存等可操作清单 | SELECT 关键字段 |

## 输出格式要求

必须输出**严格的 JSON**（不要包含 markdown 代码块标记）：

```json
{
  "categories": [
    {
      "name": "销售分析",
      "icon": "trend",
      "description": "销售数据相关的分析与洞察"
    }
  ],
  "charts": [
    {
      "id": "chart_0",
      "chart_type": "bar",
      "category": "销售分析",
      "title": "各区域销售额排名",
      "description": "展示各区域的销售额排名对比情况",
      "sql": "SELECT `区域`, SUM(CAST(REPLACE(REPLACE(REPLACE(`销售额`, ',', ''), '￥', ''), '%', '') AS DECIMAL(18,4))) AS `销售额` FROM `table_name` GROUP BY `区域` ORDER BY `销售额` DESC LIMIT 10",
      "x_field": "区域",
      "y_field": "销售额",
      "aggregation": "sum",
      "table_name": "完整的表名",
      "filters": [
        {
          "field": "城市",
          "type": "enum",
          "sample_values": ["北京", "上海", "广州"]
        }
      ]
    }
  ]
}
```

## 重要规则

1. **表名必须使用完整的数据库表名**（如 "data_xxx_sheet0"），不能省略或编造
2. **SQL 必须使用反引号包裹列名和表名**（MySQL 语法，支持中文列名）
3. **SQL 不要包含 WHERE 条件**，筛选条件由系统动态追加
4. **每个图表必须指定 category**，与 categories 列表中的 name 一致
5. **icon 必须是以下之一**：trend（趋势）、money（财务）、people（人力）、project（项目）、customer（客户）、chart（数据）
6. **每个图表必须包含 filters 数组**，至少包含 2-3 个枚举类型或低基数文本字段作为筛选维度，sample_values 从原始数据中提取
7. **filters 中的字段必须存在于 columns 中**，优先选择 type 为 "enum" 且 unique_count <= 50 的字段
8. **尽可能多生成图表**，利用不同的维度组合和指标组合
9. **日期字段适合做折线图**，枚举字段适合做饼图/柱状图/排名图
10. **数值指标适合做 KPI 组**展示汇总情况
11. **对于 ranking 类型，SQL 应包含 ORDER BY DESC（Top）逻辑，Bottom 部分由系统自动生成**
12. **字段展示必须可读**：不要只展示 id/编号/编码，优先选择名称、客户、产品、区域等可理解字段

## 图表数量建议

- 每个 Sheet 至少生成 3-5 个图表
- 充分利用不同维度组合（如：按区域、按产品、按时间、按人员等）
- 充分利用不同指标（如：销售额、数量、利润、完成率等）
- 如果只有一个Sheet且有足够维度，通过不同维度+指标组合生成 6-10 个图表
"""

# 单图表重新生成 Prompt
CHART_REGENERATION_SYSTEM_PROMPT = """你是一个专业的BI数据分析师和数据可视化专家。用户对当前图表不满意，要求你根据他的需求重新生成一个图表配置。

## 当前图表配置
{current_chart_json}

## 数据表 Schema 信息
{sheet_schema_info}

## 你的任务
根据用户需求，结合当前图表配置和数据表结构，生成一个新的图表配置。

## 输出格式
严格输出一个 JSON 对象（不要包含 markdown 代码块标记），格式如下：
{{
  "chart_type": "kpi_group|bar|line|pie|combo|ranking|table|detail_table",
  "category": "分类名称",
  "title": "图表标题",
  "description": "图表描述",
  "sql": "SELECT ... FROM ... GROUP BY ... ORDER BY ...",
  "encoding": {{
    "x": {{"field": "前端展示字段名", "label": "用户可读名称", "role": "dimension|time"}},
    "y": [
      {{"field": "指标别名", "label": "用户可读名称", "axis": "left|right", "series_type": "bar|line", "format": "number|percent|integer"}}
    ]
  }},
  "x_field": "维度字段名",
  "y_field": "指标字段名",
  "aggregation": "sum|count|avg|max|min",
  "table_name": "数据库表名",
  "filters": [
    {{"field": "字段名", "type": "enum", "sample_values": ["值1", "值2"]}}
  ]
}}

## 重要规则
1. table_name 必须使用原图表的 table_name: {table_name}
2. SQL 必须使用反引号包裹列名和表名（MySQL 语法，支持中文列名）
3. SQL 不要包含 WHERE 条件，筛选条件由系统动态追加
4. chart_type 必须是以下之一: kpi_group, bar, line, pie, combo, ranking, table, detail_table
5. aggregation 必须是以下之一: sum, count, avg, max, min
6. 只输出一个图表的 JSON，不要输出多个
7. 尽量满足用户需求，如果用户需求不合理，生成一个最接近的合理图表
8. 占比/构成问题优先 pie；时间变化优先 line；Top/排名优先 ranking；金额/数量 + 毛利率/占比/达成率优先 combo；明细/异常清单优先 detail_table。
9. SELECT 出来的字段别名必须是用户能看懂的业务名称，禁止输出“左表指标/右表指标/id”这类技术名称；遇到 id 字段，优先改用名称、编码、对象名等可读字段。
10. 百分比字段默认输出 0 位小数，例如 ROUND(..., 0) AS `毛利率`。
"""


class BIClassificationAgent(BaseAgent):
    """BI 分类智能体 - 分析数据Schema并生成BI配置"""

    VALID_CHART_TYPES = {"kpi_group", "bar", "line", "pie", "combo", "ranking", "table", "detail_table"}
    VALID_AGGREGATIONS = {"sum", "count", "avg", "max", "min"}
    VALID_ICONS = {"trend", "money", "people", "project", "customer", "chart"}

    def __init__(self):
        self.llm_client = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 BI 分类分析

        Args:
            input_data: {
                "sheets": [
                    {
                        "sheet_name": str,
                        "table_name": str,
                        "columns": [{"name": str, "type": str, "unique_count": int, "sample_values": [...]}],
                        "row_count": int,
                        "summary": str,
                        "key_dimensions": [...],
                        "key_metrics": [...],
                        "data_granularity": str,
                        "time_range": str,
                    }
                ]
            }

        Returns:
            {
                "categories": [...],
                "charts": [...]
            }
        """
        self.validate_input(input_data, ["sheets"])

        logger.info(f"BI 分类智能体开始分析 {len(input_data['sheets'])} 个 Sheet")

        # 构建用户消息
        user_message = self._build_user_message(input_data["sheets"])

        messages = [
            {"role": "system", "content": BI_CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        result = await self.llm_client.chat_completion_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
            timeout=180.0,
        )

        # 验证结果
        result = self._validate_and_fix(result, input_data["sheets"])

        logger.info(f"BI 分类完成: {len(result.get('categories', []))} 个分类, {len(result.get('charts', []))} 个图表")

        return result

    async def regenerate_chart(
        self,
        user_requirement: str,
        current_chart: Dict[str, Any],
        sheet_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        根据用户需求重新生成单个图表配置

        Args:
            user_requirement: 用户的需求描述（最多50字）
            current_chart: 当前图表配置
            sheet_meta: 对应的 sheet 元数据（columns, summary, key_dimensions 等）

        Returns:
            新的图表配置 dict（不含 id，id 由调用方赋值）
        """
        # 解析 columns
        columns_raw = sheet_meta.get("columns", [])
        if isinstance(columns_raw, str):
            try:
                columns = json.loads(columns_raw)
                if isinstance(columns, str):
                    columns = json.loads(columns)
            except json.JSONDecodeError:
                columns = []
        elif isinstance(columns_raw, list):
            columns = columns_raw
        else:
            columns = []

        # 构建 sheet schema 信息
        table_name = current_chart.get("table_name", "")
        schema_parts = [
            f"- 数据库表名: `{table_name}`",
            f"- 数据行数: {sheet_meta.get('row_count', '未知')}",
            f"- 数据摘要: {sheet_meta.get('summary', '无')}",
        ]
        key_dims = sheet_meta.get("key_dimensions", [])
        if isinstance(key_dims, str):
            try:
                key_dims = json.loads(key_dims)
            except json.JSONDecodeError:
                key_dims = []
        if key_dims:
            schema_parts.append(f"- 关键维度: {', '.join(key_dims)}")

        key_mets = sheet_meta.get("key_metrics", [])
        if isinstance(key_mets, str):
            try:
                key_mets = json.loads(key_mets)
            except json.JSONDecodeError:
                key_mets = []
        if key_mets:
            schema_parts.append(f"- 关键指标: {', '.join(key_mets)}")

        if columns:
            shown = columns[:40]
            schema_parts.append(f"\n字段列表（共 {len(columns)} 个）：")
            schema_parts.append("| 字段名 | 类型 | 唯一值数 | 示例值 |")
            schema_parts.append("|--------|------|----------|--------|")
            for col in shown:
                name = col.get("name", "")
                col_type = col.get("type", "text")
                unique = col.get("unique_count", 0)
                samples = col.get("sample_values", [])[:2]
                samples_str = ", ".join(str(s)[:20] for s in samples) if samples else ""
                schema_parts.append(f"| {name} | {col_type} | {unique} | {samples_str} |")

        sheet_schema_info = "\n".join(schema_parts)

        # 格式化 prompt
        current_chart_json = json.dumps(current_chart, ensure_ascii=False, indent=2)
        prompt = CHART_REGENERATION_SYSTEM_PROMPT.format(
            current_chart_json=current_chart_json,
            sheet_schema_info=sheet_schema_info,
            table_name=table_name,
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"请根据我的需求重新生成图表：{user_requirement}"},
        ]

        result = await self.llm_client.chat_completion_json(
            messages=messages,
            temperature=0.4,
            max_tokens=2048,
            timeout=60.0,
        )

        # 验证结果
        result = self._validate_single_chart(result, current_chart)

        return result

    def _validate_single_chart(
        self, chart: Dict[str, Any], original: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证单个重新生成的图表配置"""
        table_name = original.get("table_name", "")

        if not isinstance(chart, dict):
            raise ValueError("图表重新生成结果不是 JSON 对象")

        # 确保 chart_type 有效
        if chart.get("chart_type") not in self.VALID_CHART_TYPES:
            raise ValueError(f"不支持的图表类型: {chart.get('chart_type')}")

        # 确保 category 存在
        if not chart.get("category"):
            raise ValueError("图表缺少 category")

        # 确保 aggregation 有效
        if chart.get("aggregation") and chart["aggregation"] not in self.VALID_AGGREGATIONS:
            raise ValueError(f"不支持的聚合方式: {chart.get('aggregation')}")

        # SQL 安全检查
        sql = chart.get("sql", "")
        sanitized_sql = SQLValidator.sanitize_sql(sql)
        if not sanitized_sql:
            raise ValueError("图表 SQL 必须是只读 SELECT/WITH 查询")
        chart["sql"] = sanitized_sql

        # 确保 table_name 正确
        if not chart.get("table_name"):
            raise ValueError("图表缺少 table_name")
        if chart.get("table_name") != table_name:
            raise ValueError("单图重生成不允许切换 table_name")

        # 确保 title 存在
        if not chart.get("title"):
            raise ValueError("图表缺少 title")

        # 确保 description 存在
        if not chart.get("description"):
            raise ValueError("图表缺少 description")

        # 确保 filters 是有效列表
        if not isinstance(chart.get("filters"), list):
            raise ValueError("图表 filters 必须是数组")

        return chart

    def _build_user_message(self, sheets: List[Dict]) -> str:
        """构建发送给 LLM 的用户消息"""
        parts = ["## 数据表Schema信息\n"]

        for i, sheet in enumerate(sheets):
            parts.append(f"### Sheet {i + 1}: {sheet.get('sheet_name', 'Unknown')}")
            parts.append(f"- 数据库表名: `{sheet.get('table_name', '')}`")
            parts.append(f"- 数据行数: {sheet.get('row_count', 0)}")
            parts.append(f"- 数据粒度: {sheet.get('data_granularity', '未知')}")
            parts.append(f"- 时间范围: {sheet.get('time_range', '未知')}")

            if sheet.get("summary"):
                parts.append(f"- 数据摘要: {sheet['summary']}")

            if sheet.get("key_dimensions"):
                parts.append(f"- 关键维度: {', '.join(sheet['key_dimensions'])}")

            if sheet.get("key_metrics"):
                parts.append(f"- 关键指标: {', '.join(sheet['key_metrics'])}")

            # 列信息（限制列数和样本值长度，避免 prompt 过大导致 LLM 超时）
            columns = sheet.get("columns", [])
            if columns:
                # 最多展示 40 列，优先展示维度和指标
                shown_columns = columns[:40]
                parts.append(f"\n**字段列表：**（共 {len(columns)} 个字段，展示前 {len(shown_columns)} 个）")
                parts.append("| 字段名 | 类型 | 唯一值数 | 示例值 |")
                parts.append("|--------|------|----------|--------|")
                for col in shown_columns:
                    name = col.get("name", "")
                    col_type = col.get("type", "text")
                    unique = col.get("unique_count", 0)
                    samples = col.get("sample_values", [])[:2]  # 只取前2个样本值
                    samples_str = ", ".join(str(s)[:20] for s in samples) if samples else ""
                    parts.append(f"| {name} | {col_type} | {unique} | {samples_str} |")

            parts.append("")

        parts.append("请根据以上Schema信息，生成BI看板配置。严格输出JSON格式。")

        return "\n".join(parts)

    def _validate_and_fix(self, result: Dict, sheets: List[Dict]) -> Dict:
        """验证 LLM 输出的配置"""
        # 确保 categories 存在
        if "categories" not in result:
            result["categories"] = [{"name": "数据分析", "icon": "chart", "description": "数据分析与洞察"}]

        categories = result.get("categories", [])
        allowed_category_names = {c["name"] for c in categories}

        # 确保每个 category 有必填字段
        for cat in categories:
            if "icon" not in cat or cat["icon"] not in self.VALID_ICONS:
                cat["icon"] = "chart"
            if "description" not in cat:
                cat["description"] = f"{cat.get('name', '')}相关分析"

        # 验证 charts
        charts = result.get("charts", [])
        validated_charts = []
        table_names = {s.get("table_name", "") for s in sheets}
        all_columns = {}
        for s in sheets:
            tn = s.get("table_name", "")
            if tn:
                all_columns[tn] = {c["name"]: c for c in s.get("columns", [])}

        for i, chart in enumerate(charts):
            if not isinstance(chart, dict):
                continue

            # 确保 id
            if "id" not in chart:
                chart["id"] = f"chart_{i}"

            # 验证 chart_type
            if chart.get("chart_type") not in self.VALID_CHART_TYPES:
                chart["chart_type"] = "bar"

            # 验证 category
            if chart.get("category") not in allowed_category_names and categories:
                chart["category"] = categories[0]["name"]

            # 验证 aggregation
            if chart.get("aggregation") and chart["aggregation"] not in self.VALID_AGGREGATIONS:
                chart["aggregation"] = "sum"

            # SQL 安全检查：确保是 SELECT 语句
            sql = chart.get("sql", "")
            if sql and not sql.strip().upper().startswith("SELECT"):
                chart["sql"] = f"SELECT * FROM \"{chart.get('table_name', '')}\" LIMIT 100"

            # 验证 table_name 存在
            if chart.get("table_name") not in table_names and table_names:
                chart["table_name"] = list(table_names)[0]

            if not isinstance(chart.get("filters"), list):
                chart["filters"] = []

            validated_charts.append(chart)

        if len(validated_charts) < 6:
            raise ValueError(
                f"BI 图表数量不足：LLM 仅返回 {len(validated_charts)} 个，要求至少 6 个"
            )

        result["charts"] = validated_charts
        return result
