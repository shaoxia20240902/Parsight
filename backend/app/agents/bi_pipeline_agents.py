"""
BI 看板流水线智能体：分步蓝图（角色→场景→问题→审视）、行业推断、单图修复。

蓝图不一次性生成，每步专注单一任务，提示词更深；最终由 BIBlueprintPipeline 组装为统一 JSON。
"""

import json
import logging
import re
from typing import Any, Dict, List

from app.agents.base import BaseAgent
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

BI_INDUSTRY_MAX_TOKENS = 4096
BI_ROLE_MAX_TOKENS = 4096
BI_SCENARIO_MAX_TOKENS = 6144
BI_QUESTION_MAX_TOKENS = 8192
BI_REVIEW_MAX_TOKENS = 8192
BI_REPAIR_MAX_TOKENS = 8192

# sql_template_hint 供 SQL 编译器选模板（模型可选填，非 analysis_type 本身）
SQL_TEMPLATE_HINTS = (
    "kpi, trend, growth_rate, mom, yoy, share, structure, ranking, "
    "target_achievement, derived_kpi, anomaly_list, detail, distribution, funnel, cohort"
)

# ─── 行业推断 ─────────────────────────────────────────────

INDUSTRY_SYSTEM = """你是资深数据咨询顾问。根据多张 Excel Sheet 的表名、完整字段画像、样本值与「六维理解」全文，推断整体业务类型。

必须遵守：
1. 只输出 JSON 对象，不要 Markdown 代码块。
2. 不要编造表中不存在的字段或业务事实。
3. primary 必须是以下之一：sales, operations, supply_chain, hr, finance, general
4. analysis_hints 写 2～4 条，指导后续分析应关注什么，不要写 SQL。

返回格式：
{
  "industry_guess": {
    "primary": "sales",
    "confidence": 0.85,
    "signals": ["依据1", "依据2"],
    "analysis_hints": ["建议关注…"]
  },
  "file_summary": "一句话描述该文件整体业务"
}"""


# ─── 蓝图 Step 1：业务一句话 + 选角 ─────────────────────

ROLE_PICKER_SYSTEM = """你是资深 BI 分析负责人。请完整阅读输入中的 understanding_content（六维理解全文）与 fields（全部字段画像）。

本步骤**只做两件事**：
1. 用一句话概括这张表的业务本质（business_one_liner）。
2. 选定 2～4 个**分析角色**（不同岗位/视角），每个角色写清 role_background（他关心什么、用什么 KPI 语言），**不要写场景、不要写问题**。

选角原则：
- 结合 industry_guess、表粒度、字段类型；销售/运营/财务/供应链等表应选不同角色。
- 角色之间视角互补，不要四个角色都说同一类事。
- 每个 perspective_id 使用 snake_case，全局唯一。

只输出 JSON：
{
  "business_one_liner": "…",
  "perspectives": [
    {
      "perspective_id": "regional_sales_lead",
      "role_name": "区域销售负责人",
      "role_background": "…",
      "priority": 90
    }
  ],
  "warnings": []
}"""


# ─── 蓝图 Step 2：定场景（每角色一次）─────────────────────

SCENARIO_SYSTEM = """你是业务分析顾问。当前任务：为**某一个分析角色**设计 1～3 个**业务场景**。

场景是什么：
- 描述「在什么业务情境下、要做什么判断」（陈述句，不是问句）。
- 写清决策目标、可能关注的指标类型、可用的维度/时间范围（结合 fields 与 time_coverage）。
- **禁止**在本步骤输出 questions、analysis_type 或 SQL。

深度要求：
- 场景名 scenario_name 简短（4～12 字）。
- scenario_context 至少 2 句话：情境 + 分析目标。
- focus_areas 列出 2～4 个关注点（自由文本，如「区域贡献均衡」「尾部客户风险」）。
- 若 time_coverage.period_count 不足 2，不要设计依赖「环比/同比」的场景。

输入含 sheet_payload（完整理解+字段）与当前 perspective（角色信息）。

只输出 JSON：
{
  "perspective_id": "与输入一致",
  "scenarios": [
    {
      "scenario_id": "monthly_region_review",
      "scenario_name": "月底区域复盘",
      "scenario_context": "…",
      "focus_areas": ["区域贡献", "结构集中度"],
      "suggested_analysis_directions": ["结构拆解", "排名对比"]
    }
  ],
  "warnings": []
}"""


# ─── 蓝图 Step 3：定问题（每场景一次）─────────────────────

QUESTION_SYSTEM = f"""你是 KPI 与分析问题设计专家。当前任务：在**给定业务场景**下，设计 1～3 个**可执行的数据分析问题**。

## 分析类型（analysis_type）— 不限制枚举
- analysis_type 由你根据业务**自由命名**（英文 snake_case），如：region_contribution、retention_cohort、sales_momentum、inventory_turnover。
- 不要用无意义名字如 type1；名称应体现业务含义。
- 同时填写 analysis_intent（中文，说明要算什么、为什么对这个场景重要）。
- 可选 sql_template_hint：从 [{SQL_TEMPLATE_HINTS}] 中选最接近的模板关键字，帮助系统生成 SQL；若没有合适的，填 closest 之一并靠 analysis_intent 说明。

## 字段约束
- metrics、dimensions、time_field 的字段名**必须**来自 sheet_payload.fields 中的 field，禁止编造。
- 若问题需要表中没有的 KPI（如留存率），在 derived_kpi_hint 说明推导思路；若无法推导则不要出该题。

## 图表与优先级
- preferred_chart_types 从 kpi, bar, line, pie, table 中选。
- priority 0～100，场景内最高题 ≤ 95。

只输出 JSON：
{{
  "scenario_id": "与输入一致",
  "questions": [
    {{
      "question_id": "q1",
      "title": "图表标题（简短）",
      "question": "完整业务问句",
      "user_intent": "用户想判断什么",
      "analysis_type": "region_contribution",
      "analysis_intent": "按区域汇总销售额并观察占比是否过度集中",
      "sql_template_hint": "structure",
      "metrics": ["销售额"],
      "dimensions": ["区域"],
      "time_field": null,
      "derived_kpi_hint": null,
      "preferred_chart_types": ["bar", "pie"],
      "priority": 92
    }}
  ],
  "warnings": []
}}"""


QUESTION_REVIEW_SYSTEM = """你是 BI 质量审核员。审查**某一个分析角色**下已有场景与问题是否充分。

请完整阅读 sheet_payload（含 understanding_content 与全部 fields）。

审查维度：
1. 是否覆盖该角色 role_background 中的核心关切？
2. 是否缺少：规模总览（若场景内没有）、趋势/节奏、结构拆解、达成/对比、异常/尾部清单等中的关键一类？
3. 已有问题的 analysis_intent 是否与字段、时间跨度一致？

补充规则：
- 若充分：need_more_questions=false，additional_questions=[]。
- 若需补充：最多 3 题，挂到已有 scenario_id 或 "_supplement"。
- 补充题同样使用自由 analysis_type + 必填 analysis_intent + 可选 sql_template_hint。
- 字段名必须存在于 sheet_payload.fields。

只输出 JSON：
{
  "perspective_id": "与输入一致",
  "coverage_ok": true,
  "gaps": ["缺少…"],
  "need_more_questions": false,
  "additional_questions": []
}"""


REPAIR_SYSTEM = """你是 BI 图表修复专家。某张图表 SQL 执行失败或结果为空，请判断原因并给出**一次**修复。

必须遵守：
1. 只输出 JSON，不要 Markdown。
2. diagnosis：sql_issue 或 question_issue。
3. repair_action：fix_sql 或 fix_question。
4. fix_sql：提供 revised_sql（MySQL，反引号，仅 SELECT）。
5. fix_question：修订问题及字段；analysis_type 可自由命名，并给 analysis_intent。
6. 对照完整 understanding_content 与 fields，不要编造列名。

返回格式：
{
  "diagnosis": "sql_issue|question_issue",
  "diagnosis_reason": "…",
  "repair_action": "fix_sql|fix_question",
  "revised_question": null,
  "revised_analysis_type": null,
  "revised_analysis_intent": null,
  "revised_sql_template_hint": null,
  "revised_metrics": [],
  "revised_dimensions": [],
  "revised_time_field": null,
  "revised_sql": null
}"""


class BIIndustryInferenceAgent(BaseAgent):
    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["file_payload"])
        result = await self.llm.chat_completion_json(
            [
                {"role": "system", "content": INDUSTRY_SYSTEM},
                {"role": "user", "content": json.dumps(input_data["file_payload"], ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=BI_INDUSTRY_MAX_TOKENS,
            timeout=120,
        )
        if "industry_guess" not in result:
            raise ValueError("行业推断输出缺少 industry_guess")
        return result


class BISheetRolePickerAgent(BaseAgent):
    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["sheet_payload"])
        result = await self.llm.chat_completion_json(
            [
                {"role": "system", "content": ROLE_PICKER_SYSTEM},
                {"role": "user", "content": json.dumps(input_data["sheet_payload"], ensure_ascii=False)},
            ],
            temperature=0.25,
            max_tokens=BI_ROLE_MAX_TOKENS,
            timeout=120,
        )
        if not result.get("perspectives"):
            raise ValueError("选角步骤未返回 perspectives")
        return result


class BIScenarioAgent(BaseAgent):
    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["perspective_payload"])
        result = await self.llm.chat_completion_json(
            [
                {"role": "system", "content": SCENARIO_SYSTEM},
                {"role": "user", "content": json.dumps(input_data["perspective_payload"], ensure_ascii=False)},
            ],
            temperature=0.25,
            max_tokens=BI_SCENARIO_MAX_TOKENS,
            timeout=150,
        )
        if not result.get("scenarios"):
            raise ValueError(f"角色 {result.get('perspective_id')} 未生成 scenarios")
        return result


class BIScenarioQuestionAgent(BaseAgent):
    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["scenario_payload"])
        result = await self.llm.chat_completion_json(
            [
                {"role": "system", "content": QUESTION_SYSTEM},
                {"role": "user", "content": json.dumps(input_data["scenario_payload"], ensure_ascii=False)},
            ],
            temperature=0.28,
            max_tokens=BI_QUESTION_MAX_TOKENS,
            timeout=180,
        )
        if not result.get("questions"):
            raise ValueError(f"场景 {result.get('scenario_id')} 未生成 questions")
        return result


class BIQuestionReviewAgent(BaseAgent):
    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["perspective_payload"])
        result = await self.llm.chat_completion_json(
            [
                {"role": "system", "content": QUESTION_REVIEW_SYSTEM},
                {"role": "user", "content": json.dumps(input_data["perspective_payload"], ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=BI_REVIEW_MAX_TOKENS,
            timeout=180,
        )
        if "perspective_id" not in result:
            result["perspective_id"] = input_data["perspective_payload"].get("perspective", {}).get("perspective_id", "")
        return result


class BIChartRepairAgent(BaseAgent):
    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["failure_type", "question", "sql"])
        result = await self.llm.chat_completion_json(
            [
                {"role": "system", "content": REPAIR_SYSTEM},
                {"role": "user", "content": json.dumps({
                    "failure_type": input_data["failure_type"],
                    "error_message": input_data.get("error_message", ""),
                    "question": input_data["question"],
                    "scenario_context": input_data.get("scenario_context", ""),
                    "metric_spec": input_data.get("metric_spec", {}),
                    "sql": input_data["sql"],
                    "understanding_content": input_data.get("understanding_content", ""),
                    "fields": input_data.get("fields", []),
                    "sheet_payload": input_data.get("sheet_payload", {}),
                }, ensure_ascii=False)},
            ],
            temperature=0.15,
            max_tokens=BI_REPAIR_MAX_TOKENS,
            timeout=120,
        )
        if result.get("repair_action") not in ("fix_sql", "fix_question"):
            raise ValueError(f"无效的 repair_action: {result.get('repair_action')}")
        return result


# 兼容旧引用（若有）
BISheetBlueprintAgent = BISheetRolePickerAgent
