"""
AI 服务 — 统一管理所有 Agent 调用

通过环境变量 AGENT_BACKEND 切换 local / shenzhou（见 config.py）。
未配置 LLM 或 Agent 调用失败时直接抛出异常，不做 Mock 兜底。
"""

import asyncio
import logging
from typing import Any, Dict, List

from app.agents.agent_factory import AgentService

logger = logging.getLogger(__name__)


class AIService:
    """AI 服务 — 封装所有 Agent 调用，对上层透明"""

    def __init__(self):
        self.agents = AgentService()

    # ================================================================
    #  Agent A: Sheet 总结
    # ================================================================

    async def analyze_sheet(self, sheet_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析单个 Sheet"""
        return await self.agents.sheet_summary_agent.run(sheet_data)

    # ================================================================
    #  Agent C: 关键词确认
    # ================================================================

    async def confirm_keyword(
        self, question: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """关键词确认"""
        return await self.agents.keyword_confirm_agent.run({
            "question": question,
            **context,
        })

    # ================================================================
    #  Agent D/E/F: 多角色并行拆解
    # ================================================================

    async def decompose_by_roles(
        self,
        main_question: str,
        confirmed_filters: list,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """多角色并行拆解"""
        # 从 data_context 提取可用维度和指标
        sheets_summary = context.get("sheets_summary", [])
        available_dimensions = []
        available_metrics = []
        for s in sheets_summary:
            for dim in s.get("key_dimensions", []):
                if dim not in available_dimensions:
                    available_dimensions.append(dim)
            for metric in s.get("key_metrics", []):
                if metric not in available_metrics:
                    available_metrics.append(metric)

        # 从 table_schemas 补充
        table_schemas = context.get("table_schemas", {})
        for tn, info in table_schemas.items():
            columns = info.get("columns", []) if isinstance(info, dict) else []
            for col in columns:
                if isinstance(col, dict):
                    col_type = col.get("type", "text")
                    col_name = col.get("name", "")
                    if col_type in ("text", "date", "enum") and col_name not in available_dimensions:
                        available_dimensions.append(col_name)
                    elif col_type == "number" and col_name not in available_metrics:
                        available_metrics.append(col_name)

        input_data = {
            "main_question": main_question,
            "confirmed_filters": confirmed_filters,
            "available_dimensions": available_dimensions,
            "available_metrics": available_metrics,
            "data_context": context,
        }

        tasks = [agent.run(input_data) for agent in self.agents.role_agents.values()]
        results = await asyncio.gather(*tasks)
        return results

    # ================================================================
    #  Agent G: 子问题筛选
    # ================================================================

    async def select_sub_questions(
        self,
        role_questions: List[Dict[str, Any]],
        main_question: str = "",
    ) -> Dict[str, Any]:
        """筛选子问题"""
        return await self.agents.sub_question_selector.run({
            "role_questions": role_questions,
            "main_question": main_question,
        })

    # ================================================================
    #  Agent H: SQL 生成
    # ================================================================

    async def generate_sql(
        self,
        questions: List[Dict],
        table_schemas: Dict,
        filters: List[Dict] = None,
    ) -> Dict[str, Any]:
        """生成 SQL"""
        return await self.agents.sql_generator.run({
            "questions": questions,
            "table_schemas": table_schemas,
            "filters": filters or [],
        })

    # ================================================================
    #  Agent I: 图表生成
    # ================================================================

    async def generate_chart(
        self,
        question: str,
        data: List[Dict],
        columns: List[str] = None,
        analysis_type: str = "auto",
    ) -> Dict[str, Any]:
        """生成图表"""
        return await self.agents.chart_generator.run({
            "question": question,
            "data": data,
            "data_columns": columns or [],
            "analysis_type": analysis_type,
        })

    # ================================================================
    #  Agent J: 总结报告
    # ================================================================

    async def generate_report(
        self,
        main_question: str,
        sub_questions: List,
        data_results: List[Dict],
        confirmed_filters: List[Dict] = None,
        data_context: Dict = None,
    ) -> Dict[str, Any]:
        """生成报告"""
        return await self.agents.report_generator.run({
            "main_question": main_question,
            "sub_questions": sub_questions,
            "data_results": data_results,
            "confirmed_filters": confirmed_filters or [],
            "data_context": data_context or {},
        })

    async def route_bi_builder_intent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.agents.bi_builder_intent_router_agent.run(payload)

    async def plan_bi_builder_scope(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.agents.bi_builder_scope_planner_agent.run(payload)

    async def detect_bi_builder_knowledge_preferences(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.agents.bi_builder_knowledge_preference_agent.run(payload)

    async def compose_bi_builder_confirmation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.agents.bi_builder_confirm_composer_agent.run(payload)

    async def suggest_bi_builder_repairs(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.agents.bi_builder_repair_options_agent.run(payload)

    # ================================================================
    #  Agent K: 快速问答
    # ================================================================

    async def quick_qa(
        self,
        question: str,
        sheets_summary: List[Dict],
        table_schemas: Dict,
        conversation_history: List[Dict] = None,
    ) -> Dict[str, Any]:
        """快速问答"""
        return await self.agents.quick_qa_agent.run({
            "question": question,
            "sheets_summary": sheets_summary,
            "table_schemas": table_schemas,
            "conversation_history": conversation_history or [],
        })

    # ================================================================
    #  Agent L: 看板构建助手
    # ================================================================

    async def build_dashboard(
        self,
        question: str,
        table_schemas: Dict,
        sheets_summary: List[Dict],
        conversation_history: List[Dict] = None,
    ) -> Dict[str, Any]:
        """看板构建助手 — 交互式收集配置"""
        return await self.agents.dashboard_builder_agent.run({
            "question": question,
            "table_schemas": table_schemas,
            "sheets_summary": sheets_summary,
            "conversation_history": conversation_history or [],
        })

    # ================================================================
    #  Agent M: 看板布局生成
    # ================================================================

    async def generate_dashboard_layout(
        self,
        config: Dict[str, Any],
        table_schemas: Dict,
    ) -> Dict[str, Any]:
        """看板布局生成 — 将配置转化为完整多图表看板"""
        return await self.agents.dashboard_layout_agent.run({
            "config": config,
            "table_schemas": table_schemas,
        })
