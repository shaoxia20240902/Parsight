"""BI Builder prompt templates and local LLM agents.

The current BIBuilderService uses deterministic planning first so the feature is
usable without extra LLM latency. These prompts define the contract for replacing
that planner with LLM-backed agents.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.agents.base import BaseAgent
from app.config import LLM_MODEL_QWEN_PRIMARY
from app.services.llm_client import LLMClient

BI_BUILDER_INTENT_ROUTER_PROMPT = """你是 BI 构建者的意图路由器。
只输出 JSON：
{
  "intent": "non_bi|bi_lookup|bi_create|bi_modify|bi_supplement|explore_dataset",
  "force_create": false,
  "requires_existing_match": true,
  "confidence": 0.0,
  "reason": ""
}
规则：
- 用户明确说不要用已有、重新创建、新建、重做时 force_create=true。
- 用户点“基于此图调整”时 intent=bi_modify，必须保留 base_chart_id。
- 用户对候选图补充“加筛选/换图/改分类”时 intent=bi_supplement，必须保留上下文图表。
- 用户问“这份数据能做什么分析”时 intent=explore_dataset。
"""


BI_BUILDER_SCOPE_PLANNER_PROMPT = """你是 BI 构建者的 ScopePlanning 智能体。
一次性完成：需求探索、搭配推荐、批量范围判断、缺失信息判断、推荐分类。
只输出 JSON：
{
  "readiness": 0.0,
  "can_execute": true,
  "mode": "chart_list",
  "write_strategy": "append|adjust_existing|replace_category",
  "chart_list": [],
  "missing_required": [],
  "missing_advanced": [],
  "recommended_categories": [],
  "impact": {"will_create": 0, "will_replace_existing": 0, "requires_rebuild_confirmation": false},
  "explain_for_user": ""
}
硬规则：
- 永远输出 chart_list，单图只是 chart_list 长度为 1。
- Top 5 可以推荐 Bottom 5，但必须标记 source=companion_recommendation。
- 分类推荐必须基于最终字段和跨表关系，不要提前锁定。
- 必填缺失放 missing_required，可选项放 missing_advanced。
- 不编造字段，所有字段必须来自输入上下文。
"""


BI_BUILDER_KNOWLEDGE_PREFERENCE_PROMPT = """你是业务知识和用户偏好检测器。
只在 ScopePlanning 已明确需求后运行。只输出与本次 chart_list 有关的卡片。
只输出 JSON：
{
  "cards": [
    {
      "card_type": "business_knowledge|user_preference",
      "title": "",
      "payload": {},
      "options": []
    }
  ]
}
规则：
- 业务别名、指标口径、分群规则属于 business_knowledge。
- “以后/默认/总是”这类稳定表达属于 user_preference。
- 不确定时提供“本次使用但不保存”。
"""


BI_BUILDER_CONFIRM_COMPOSER_PROMPT = """你是 BI 生成确认摘要编写器。
根据 chart_list、推荐分类、写入策略和影响范围生成富消息 blocks。
只输出 JSON：
{
  "content": "",
  "blocks": []
}
规则：
- 多图必须用 Markdown 表格。
- 表格图字段确认必须用 Markdown 表格。
- 必须展示推荐分类和写入策略。
- 必须给出 confirm_generate、modify_chart_list、modify_fields、modify_filters、modify_category 动作。
"""


BI_BUILDER_REPAIR_OPTIONS_PROMPT = """你是 BI 图表生成失败修正选项生成器。
根据失败图表、错误信息和字段上下文，给用户可选修正项。
只输出 JSON：
{
  "repair_options": [
    {"label": "", "action": "", "payload": {}}
  ]
}
规则：
- 不编造数据。
- 只给可执行的修正项。
- 自动修复最多一次；仍失败时必须让用户选择。
"""


class _LocalBIBuilderJSONAgent(BaseAgent):
    system_prompt = ""
    required_keys: List[str] = []
    temperature = 0.2
    max_tokens = 2048

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, self.required_keys)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, default=str)},
        ]
        return await self.llm.chat_completion_json(
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=25.0,
            model_override=LLM_MODEL_QWEN_PRIMARY,
        )


class LocalBIBuilderIntentRouterAgent(_LocalBIBuilderJSONAgent):
    system_prompt = BI_BUILDER_INTENT_ROUTER_PROMPT
    required_keys = ["message"]
    temperature = 0.1
    max_tokens = 512


class LocalBIBuilderScopePlannerAgent(_LocalBIBuilderJSONAgent):
    system_prompt = BI_BUILDER_SCOPE_PLANNER_PROMPT
    required_keys = ["message", "context", "intent"]
    temperature = 0.25
    max_tokens = 4096


class LocalBIBuilderKnowledgePreferenceAgent(_LocalBIBuilderJSONAgent):
    system_prompt = BI_BUILDER_KNOWLEDGE_PREFERENCE_PROMPT
    required_keys = ["message", "chart_list", "context"]
    temperature = 0.2
    max_tokens = 2048


class LocalBIBuilderConfirmComposerAgent(_LocalBIBuilderJSONAgent):
    system_prompt = BI_BUILDER_CONFIRM_COMPOSER_PROMPT
    required_keys = ["chart_list", "scope_plan"]
    temperature = 0.2
    max_tokens = 2048


class LocalBIBuilderRepairOptionsAgent(_LocalBIBuilderJSONAgent):
    system_prompt = BI_BUILDER_REPAIR_OPTIONS_PROMPT
    required_keys = ["failed", "context"]
    temperature = 0.1
    max_tokens = 1024
