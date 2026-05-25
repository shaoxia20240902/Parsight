"""
看板构建 Agent — Agent L (看板构建助手) + Agent M (看板布局生成)

看板构建模式：用户通过自然语言描述需求 → Agent L 多轮对话收集配置
→ Agent M 将配置转化为完整的多图表看板

Author: 张智家
Date:   2026-05-14
"""

import json
import logging
from typing import Any, Dict, List

from app.agents.base import BaseAgent
from app.services.llm_client import LLMClient
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Agent L: 看板构建助手（Chat 应用 / 多轮对话）
# ─────────────────────────────────────────────

AGENT_L_SYSTEM_PROMPT = """你是 BI 看板构建顾问，帮助用户通过自然语言描述来创建自定义的数据看板。

## 可用数据上下文
每次对话开始时注入：
- table_schemas: 各表字段名+类型+枚举值
- sheets_summary: 各 Sheet 的总结

## 工作流程
1. 解析用户的自然语言描述，提取已明确的信息：主题、维度、指标、筛选条件
2. 识别缺失信息，按优先级反问：
   - 维度缺失（需要看什么角度？）
   - 指标缺失（需要看什么数字？）
   - 筛选条件模糊（具体看哪些？）
   - 布局偏好未指定（怎么排列？）
3. 反问时必须提供多选选项，选项值来自实际数据
4. 信息足够后输出 ready 状态配置

## 反问规则
- "维度缺失" → 列出所有可用维度字段，多选
  例："数据支持以下维度，请选择你关注的（可多选）："
- "指标缺失" → 列出所有可用数值字段，多选
  例："你想看哪些指标？（可多选）"
- "筛选模糊" → 列出该字段的实际枚举值
  例："'{keyword}'在数据中对应以下内容，请确认："
- "布局未指定" → 提供布局模板选项
  例："请选择看板布局偏好："

## 布局模板
1. 综合看板：排名柱状图 + 占比饼图 + 趋势折线图 + 明细表
2. 对比看板：分组柱状图 + 交叉对比表
3. 趋势看板：折线图 + 面积图 + 同比环比计算
4. 自动推荐：由 AI 根据数据特点自动选择

## 输出格式
当需要反问时：
{
  "status": "need_input",
  "question": "反问文本",
  "field": "dimensions|metrics|filters|layout",
  "options": [
    {"label": "选项显示文本", "value": "选项值", "description": "可选说明"}
  ],
  "multi_select": true
}

当配置完整时：
{
  "status": "ready",
  "config": {
    "topic": "看板标题",
    "dimensions": ["选中的维度"],
    "metrics": ["选中的指标"],
    "filters": [{"field": "字段名", "value": "筛选值", "sheet": "表名"}],
    "layout": "comprehensive|comparison|trend|auto"
  }
}

## 行为准则
- 信息足够时不啰嗦，直接 ready
- 每轮最多问一个问题（维度→指标→筛选→布局）
- 选项值必须来自实际数据，不要编造
- 如果用户说"随便""都行""你决定"，采用自动推荐策略"""


class LocalDashboardBuilderAgent(BaseAgent):
    """看板构建助手 - 本地 LLM 实现"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["question", "table_schemas", "sheets_summary"])

        question = input_data["question"]
        table_schemas = input_data["table_schemas"]
        sheets_summary = input_data["sheets_summary"]
        conversation_history = input_data.get("conversation_history", [])

        # 简化表结构（减少 token）
        simplified_schemas = {}
        for tn, info in table_schemas.items():
            if isinstance(info, dict) and "columns" in info:
                simplified_schemas[tn] = {
                    "sheet_name": info.get("sheet_name", tn),
                    "columns": [
                        {
                            "name": c.get("name", ""),
                            "type": c.get("type", "text"),
                            "sample_values": c.get("sample_values", [])[:10],
                        }
                        for c in info.get("columns", [])
                    ],
                }
            else:
                simplified_schemas[tn] = info

        user_msg_parts = [
            f"用户消息: {question}",
            "",
            "表结构:",
            json.dumps(simplified_schemas, ensure_ascii=False, indent=2),
            "",
            "Sheet 总结:",
            json.dumps(sheets_summary, ensure_ascii=False, indent=2),
        ]

        if conversation_history:
            history_lines = []
            for msg in conversation_history[-10:]:
                role = msg.get("role", "")
                content = msg.get("content", "")
                history_lines.append(f"{role}: {content}")
            user_msg_parts.extend(["", "对话历史:", "\n".join(history_lines)])

        user_msg = "\n".join(user_msg_parts)

        messages = [
            {"role": "system", "content": AGENT_L_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        result = await self.llm.chat_completion_json(
            messages=messages,
            temperature=0.4,
            max_tokens=2048,
            timeout=60.0,
        )

        result.setdefault("status", "need_input")
        return result

# ─────────────────────────────────────────────
#  Agent M: 看板布局生成智能体
# ─────────────────────────────────────────────

AGENT_M_SYSTEM_PROMPT = """你是看板布局生成专家。根据用户确认的看板配置，生成完整的多图表看板。

## 输入
- 看板主题、维度、指标、筛选条件
- 布局模板类型
- 可用的数据表 Schema

## 任务
1. 根据布局模板拆解具体的图表任务
2. 为每个图表任务定义清晰的分析目标
3. 生成每个图表所需的数据查询 SQL
4. 确定图表的排列布局（12 栅格系统）
5. 生成全局筛选器配置

## 布局规则（12 栅格）
- full-width 图表（趋势折线图、表格）：span = 12
- half-width 图表（排名柱状图、饼图、仪表盘）：span = 6
- 同类图表尽量放在同一行
- 前两行放核心图表，后面放辅助图表

## 布局模板拆解
- comprehensive（综合看板）→ 4个图表：
  1. ranking: 各维度指标排名（柱状图，span=6）
  2. structure: 指标按维度的占比（饼图，span=6）
  3. trend: 月度指标趋势（折线图，span=12）
  4. detail: 数据明细表（表格，span=12）
- comparison（对比看板）→ 2个图表：
  1. 分组柱状图对比（span=12）
  2. 交叉对比表（span=12）
- trend（趋势看板）→ 2个图表：
  1. 折线图趋势（span=12）
  2. 面积图+同比环比（span=12）
- auto → 自动判断最佳布局

## 全局筛选器
- 基于用户选择的维度生成对应的筛选器
- date_range 类型用于时间字段
- select/multi_select 类型用于文本字段
- 选项值从实际数据中提取

## 输出格式
严格输出以下 JSON：
{
  "dashboard": {
    "title": "看板标题",
    "global_filters": [
      {"field": "字段名", "type": "select|multi_select|date_range", "default": "默认值", "options": ["选项"]}
    ],
    "rows": [
      {
        "row_id": 1,
        "charts": [
          {
            "chart_id": 1,
            "type": "bar|line|pie|table",
            "title": "图表标题",
            "subtitle": "副标题",
            "analysis_type": "ranking|structure|trend|comparison|detail",
            "dimensions": ["维度"],
            "metrics": ["指标"],
            "sql": "SELECT ... FROM ...",
            "span": 6
          }
        ]
      }
    ]
  }
}"""


class LocalDashboardLayoutAgent(BaseAgent):
    """看板布局生成智能体 - 本地 LLM 实现"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["config", "table_schemas"])

        config = input_data["config"]
        table_schemas = input_data["table_schemas"]

        topic = config.get("topic", "数据看板")
        dimensions = config.get("dimensions", [])
        metrics = config.get("metrics", [])
        filters = config.get("filters", [])
        layout = config.get("layout", "comprehensive")

        # 简化表结构
        simplified_schemas = {}
        for tn, info in table_schemas.items():
            if isinstance(info, dict) and "columns" in info:
                simplified_schemas[tn] = {
                    "sheet_name": info.get("sheet_name", tn),
                    "columns": [
                        {"name": c.get("name", ""), "type": c.get("type", "text")}
                        for c in info.get("columns", [])
                    ],
                }
            else:
                simplified_schemas[tn] = info

        user_msg = f"""看板配置:
- 主题: {topic}
- 维度: {json.dumps(dimensions, ensure_ascii=False)}
- 指标: {json.dumps(metrics, ensure_ascii=False)}
- 筛选条件: {json.dumps(filters, ensure_ascii=False)}
- 布局类型: {layout}

数据表结构:
{json.dumps(simplified_schemas, ensure_ascii=False, indent=2)}
"""

        messages = [
            {"role": "system", "content": AGENT_M_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        result = await self.llm.chat_completion_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
            timeout=60.0,
        )

        result.setdefault("dashboard", {})
        return result

    def _find_time_column(self, schemas: Dict) -> str:
        """查找 schema 中的第一个时间字段"""
        for tn, info in schemas.items():
            columns = info.get("columns", [])
            for col in columns:
                if col.get("type") == "date":
                    return col.get("name", "")
        return ""
