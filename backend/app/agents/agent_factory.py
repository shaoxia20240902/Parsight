"""
Agent 工厂 — 根据 AGENT_BACKEND 配置选择 Agent 实现

支持:
- local:    本地 LLM 提示词模式（DashScope / 阿里云百炼）
- shenzhou: 神州问学平台（需单独对接，未实现则报错）
"""

import logging
from typing import Dict

from app.config import AGENT_BACKEND, AgentBackend
from app.agents.base import BaseAgent
from app.agents.local_agents import (
    LocalSheetSummaryAgent,
    LocalKeywordConfirmAgent,
    LocalRoleDecompositionAgent,
    LocalSubQuestionSelectorAgent,
    LocalSQLGeneratorAgent,
    LocalChartGeneratorAgent,
    LocalReportGeneratorAgent,
    LocalQuickQAAgent,
)
from app.agents.dashboard_agents import (
    LocalDashboardBuilderAgent,
    LocalDashboardLayoutAgent,
)
from app.agents.bi_builder_agents import (
    LocalBIBuilderConfirmComposerAgent,
    LocalBIBuilderIntentRouterAgent,
    LocalBIBuilderKnowledgePreferenceAgent,
    LocalBIBuilderRepairOptionsAgent,
    LocalBIBuilderScopePlannerAgent,
)

logger = logging.getLogger(__name__)

_LOCAL_AGENTS: Dict[str, type] = {
    "sheet_summary": LocalSheetSummaryAgent,
    "keyword_confirm": LocalKeywordConfirmAgent,
    "role_decomposition": LocalRoleDecompositionAgent,
    "sub_question_selector": LocalSubQuestionSelectorAgent,
    "sql_generator": LocalSQLGeneratorAgent,
    "chart_generator": LocalChartGeneratorAgent,
    "report_generator": LocalReportGeneratorAgent,
    "quick_qa": LocalQuickQAAgent,
    "dashboard_builder": LocalDashboardBuilderAgent,
    "dashboard_layout": LocalDashboardLayoutAgent,
    "bi_builder_intent_router": LocalBIBuilderIntentRouterAgent,
    "bi_builder_scope_planner": LocalBIBuilderScopePlannerAgent,
    "bi_builder_knowledge_preference": LocalBIBuilderKnowledgePreferenceAgent,
    "bi_builder_confirm_composer": LocalBIBuilderConfirmComposerAgent,
    "bi_builder_repair_options": LocalBIBuilderRepairOptionsAgent,
}


class AgentFactory:
    """Agent 工厂 — 单 Agent 创建"""

    def __init__(self):
        self.backend = AGENT_BACKEND
        logger.info(f"Agent 工厂初始化: backend={self.backend.value}")

        if self.backend == AgentBackend.LOCAL:
            self._registry = _LOCAL_AGENTS
        elif self.backend == AgentBackend.SHENZHOU:
            raise NotImplementedError("神州问学后端尚未对接，请将 AGENT_BACKEND 设为 local")
        else:
            raise ValueError(f"未知的 Agent 后端: {self.backend}")

    def create(self, agent_type: str, **kwargs) -> BaseAgent:
        agent_cls = self._registry.get(agent_type)
        if agent_cls is None:
            raise ValueError(
                f"未知的 Agent 类型: {agent_type}，有效值: {list(self._registry.keys())}"
            )
        return agent_cls(**kwargs)

    @property
    def backend_name(self) -> str:
        return self.backend.value


class AgentService:
    """Agent 服务 — 统一管理所有 Agent 实例的生命周期"""

    def __init__(self):
        self.factory = AgentFactory()

        self.sheet_summary_agent = self.factory.create("sheet_summary")
        self.keyword_confirm_agent = self.factory.create("keyword_confirm")
        self.role_agents = {
            "业务分析师": self.factory.create("role_decomposition", role="业务分析师"),
            "数据分析师": self.factory.create("role_decomposition", role="数据分析师"),
            "管理决策者": self.factory.create("role_decomposition", role="管理决策者"),
        }
        self.sub_question_selector = self.factory.create("sub_question_selector")
        self.sql_generator = self.factory.create("sql_generator")
        self.chart_generator = self.factory.create("chart_generator")
        self.report_generator = self.factory.create("report_generator")
        self.quick_qa_agent = self.factory.create("quick_qa")
        self.dashboard_builder_agent = self.factory.create("dashboard_builder")
        self.dashboard_layout_agent = self.factory.create("dashboard_layout")
        self.bi_builder_intent_router_agent = self.factory.create("bi_builder_intent_router")
        self.bi_builder_scope_planner_agent = self.factory.create("bi_builder_scope_planner")
        self.bi_builder_knowledge_preference_agent = self.factory.create("bi_builder_knowledge_preference")
        self.bi_builder_confirm_composer_agent = self.factory.create("bi_builder_confirm_composer")
        self.bi_builder_repair_options_agent = self.factory.create("bi_builder_repair_options")

        logger.info(
            f"Agent 服务初始化完成: backend={self.factory.backend_name}"
        )
