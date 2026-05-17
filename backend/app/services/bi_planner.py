import json
from typing import Any, Dict, List

from app.services.bi_context import profile_for_planner
from app.services.llm_client import LLMClient

# BI 规划类调用：输出 JSON 较长，提高 max_tokens
BI_PLANNER_MAX_TOKENS = 8192


SHEET_CATEGORY_SYSTEM_PROMPT = """你是资深 BI 产品架构师，负责把 Excel 多 Sheet 数据规划成 BI 看板分类。

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
"""


CUSTOM_CATEGORY_SYSTEM_PROMPT = """你是资深 BI 分析负责人，负责基于已验证的 Sheet 关联关系规划系统推荐的自定义分类。

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
"""


class BIPlanner:
    """LLM planning layer for BI categories and business labels.

    The planner decides business taxonomy and wording. The generator still owns
    table binding, MySQL SQL construction, and preview validation.
    """

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()

    async def plan_sheet_categories(
        self,
        profiles: List[Dict[str, Any]],
        filter_candidates: List[Dict[str, Any]],
        understanding_by_table: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        understanding_by_table = understanding_by_table or {}
        payload = {
            "sheets": [
                profile_for_planner(p, understanding_by_table.get(p["table_name"], ""))
                for p in profiles
            ],
            "filter_candidates": [
                {
                    "canonical_key": f.get("canonical_key"),
                    "label": f.get("label"),
                    "priority": f.get("priority"),
                    "applies_to": f.get("applies_to", []),
                }
                for f in filter_candidates
            ],
        }
        result = await self.llm.chat_completion_json(
            [
                {"role": "system", "content": SHEET_CATEGORY_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.15,
            max_tokens=BI_PLANNER_MAX_TOKENS,
            timeout=180,
        )
        self._validate_sheet_plan(result, profiles)
        return result

    async def plan_custom_categories(
        self,
        relationships: List[Dict[str, Any]],
        profiles: List[Dict[str, Any]],
        understanding_by_table: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        if not relationships:
            return {"custom_categories": [], "warnings": []}
        understanding_by_table = understanding_by_table or {}
        payload = {
            "relationships": relationships,
            "sheets": [
                profile_for_planner(p, understanding_by_table.get(p["table_name"], ""))
                for p in profiles
            ],
        }
        result = await self.llm.chat_completion_json(
            [
                {"role": "system", "content": CUSTOM_CATEGORY_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.15,
            max_tokens=BI_PLANNER_MAX_TOKENS,
            timeout=180,
        )
        self._validate_custom_plan(result, relationships)
        return result

    def _validate_sheet_plan(self, result: Dict[str, Any], profiles: List[Dict[str, Any]]) -> None:
        categories = result.get("sheet_categories")
        if not isinstance(categories, list):
            raise ValueError("BI Sheet 分类模型输出缺少 sheet_categories 数组")
        expected = {int(p.get("sheet_index") or 0) for p in profiles}
        actual = {int(c.get("sheet_index")) for c in categories if c.get("sheet_index") is not None}
        if actual != expected:
            raise ValueError(f"BI Sheet 分类必须与 Sheet 一一对应，expected={sorted(expected)}, actual={sorted(actual)}")
        labels = result.get("global_filter_labels", [])
        if labels is not None and not isinstance(labels, list):
            raise ValueError("BI 全局筛选命名输出 global_filter_labels 必须是数组")

    def _validate_custom_plan(self, result: Dict[str, Any], relationships: List[Dict[str, Any]]) -> None:
        categories = result.get("custom_categories")
        if not isinstance(categories, list):
            raise ValueError("BI 自定义分类模型输出缺少 custom_categories 数组")
        allowed = {r["id"] for r in relationships}
        for cat in categories:
            rel_id = cat.get("relationship_id")
            if rel_id not in allowed:
                raise ValueError(f"BI 自定义分类引用了不存在的关联关系：{rel_id}")
            if not cat.get("name"):
                raise ValueError("BI 自定义分类缺少 name")
