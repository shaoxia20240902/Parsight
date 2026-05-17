"""
本地 LLM Agent 实现 — 完整复刻神州问学 13 个 Agent 能力

每个 Agent 包含：
- 参照神州问学手册的精校系统提示词
- 结构化 JSON 输入/输出
- 失败重试 + JSON 修复能力
- 根据任务复杂度自动选择主/备模型

Author: 张智家
Date:   2026-05-14
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent
from app.services.llm_client import LLMClient
from app.config import (
    LLM_MODEL_QWEN_PRIMARY,
    LLM_MODEL_QWEN_ALT,
    AGENT_MAX_RETRIES,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  共享工具
# ─────────────────────────────────────────────


def _extract_json(text: str) -> Dict[str, Any]:
    """从 LLM 返回文本中提取 JSON 对象，含容错修复"""
    text = text.strip()
    # 去 markdown 包裹
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 查找最外层花括号
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法解析 LLM 输出为 JSON，原始内容: {text[:500]}")


async def _call_llm_with_retry(
    llm: LLMClient,
    messages: List[Dict[str, str]],
    model: str = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    timeout: float = 60.0,
    max_retries: int = None,
) -> Dict[str, Any]:
    """调用 LLM 并解析 JSON，失败自动重试"""
    if max_retries is None:
        max_retries = AGENT_MAX_RETRIES

    model = model or LLM_MODEL_QWEN_PRIMARY
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = await llm.chat_completion_json(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                model_override=model,
            )
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"LLM call attempt {attempt + 1}/{max_retries + 1} failed: {e}")
            if attempt < max_retries:
                await asyncio.sleep(1.0 * (attempt + 1))

    raise RuntimeError(f"LLM 调用在 {max_retries + 1} 次尝试后仍失败: {last_error}")


# ─────────────────────────────────────────────
#  Agent A: Sheet 总结智能体
# ─────────────────────────────────────────────

AGENT_A_SYSTEM_PROMPT = """你是一个数据分析专家，负责理解一个数据表的结构和内容。

## 输入
你会收到一个数据表的元信息（表名、字段列表含类型和样本值、100条样本数据）。

## 任务
1. 理解每个字段的业务含义（不要只翻译字段名，结合样本值推断真实含义）
2. 区分维度字段和指标字段
3. 判断数据的粒度（逐笔？汇总到天/月？）
4. 识别数据的时间范围
5. 发现值得注意的数据特征（具体，不要笼统）

## 输出格式
严格输出以下 JSON 结构，不要输出其他内容：
{
  "sheet_name": "表名",
  "summary": "用2-3句话描述这个表记录了什么业务数据，面向业务人员，中文自然语言",
  "key_dimensions": ["能做筛选/分组的维度字段列表"],
  "key_metrics": ["数值型指标字段列表"],
  "data_granularity": "数据粒度描述，如'逐笔交易/天级'",
  "time_range": "数据时间范围，如'2024-01 ~ 2024-12'，没有时间字段填'静态数据'",
  "notable_patterns": ["3-5个值得注意的具体发现，每条都是一个完整的事实描述"]
}"""


class LocalSheetSummaryAgent(BaseAgent):
    """Sheet 总结智能体 - 本地 LLM 实现"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["sheet_name", "columns", "sample_data"])

        sheet_name = input_data["sheet_name"]
        columns = input_data["columns"]
        sample_data = input_data.get("sample_data", [])
        row_count = input_data.get("row_count", 0)

        # 构建用户消息
        col_descriptions = []
        for col in columns:
            samples = col.get("sample_values", [])[:5]
            col_descriptions.append(
                f"  - {col['name']} (类型={col['type']}, 唯一值数={col.get('unique_count', '?')}, "
                f"样本值={samples})"
            )

        user_msg = f"""请分析以下数据表：

表名: {sheet_name}
总行数: {row_count}

字段列表:
{chr(10).join(col_descriptions)}

样本数据 (前 {min(len(sample_data), 20)} 行):
{json.dumps(sample_data[:20], ensure_ascii=False, indent=2)}"""

        messages = [
            {"role": "system", "content": AGENT_A_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        result = await _call_llm_with_retry(
            self.llm, messages,
            model=LLM_MODEL_QWEN_PRIMARY,
            temperature=0.3,
            max_tokens=2048,
            timeout=20.0,
        )
        result.setdefault("sheet_name", sheet_name)
        result.setdefault("notable_patterns", [])
        return result


# ─────────────────────────────────────────────
#  Agent C: 关键词确认智能体
# ─────────────────────────────────────────────

AGENT_C_SYSTEM_PROMPT = """你是关键词匹配助手，负责将用户问题中的实体词与数据库中的实际字段值做匹配。

## 输入
- 用户问题
- 所有可用字段及其实际枚举值（unique_values）
- 各 Sheet 的总结信息

## 任务
1. 从用户问题中提取关键实体词（如地名、产品名、人名、时间）
2. 在可用字段值中查找匹配
3. 返回三种结果之一：精确匹配 / 模糊匹配 / 无法匹配

## 匹配规则
- exact：字段中存在完全一致的值 → 直接使用，不需要 options
- fuzzy：无直接匹配但可推断 → 给用户 2-3 个选项
- no_match：数据中完全不包含此维度 → 给出建议

## 输出格式
严格输出：
{
  "match_type": "exact|fuzzy|no_match",
  "extracted_keywords": ["提取到的关键词"],
  "matched_fields": [{"field": "字段名", "sheet": "表名", "match_type": "exact", "matched_values": ["匹配值"], "description": "匹配说明"}],
  "options": [{"id": 0, "label": "选项显示文本", "description": "详细说明", "filter": {"sheet": "表名", "field": "字段名", "value": "筛选值"}}],
  "suggestion": "仅在 no_match 时输出建议，其他情况留空"
}"""


class LocalKeywordConfirmAgent(BaseAgent):
    """关键词确认智能体 - 本地 LLM 实现"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["question"])
        question = input_data["question"]
        available_fields = input_data.get("available_fields", [])
        sheets_summary = input_data.get("sheets_summary", [])

        user_msg = f"""用户问题: {question}

可用字段及枚举值:
{json.dumps(available_fields, ensure_ascii=False, indent=2)}

Sheet 总结:
{json.dumps(sheets_summary, ensure_ascii=False, indent=2)}"""

        messages = [
            {"role": "system", "content": AGENT_C_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        result = await _call_llm_with_retry(
            self.llm, messages,
            model=LLM_MODEL_QWEN_ALT,
            temperature=0.2,
            max_tokens=2048,
            timeout=15.0,
        )
        result.setdefault("match_type", "exact")
        result.setdefault("extracted_keywords", [])
        result.setdefault("matched_fields", [])
        result.setdefault("options", [])
        return result


# ─────────────────────────────────────────────
#  Agent D / E / F: 三角色并行的子问题拆解
# ─────────────────────────────────────────────

ROLE_PROMPTS = {
    "业务分析师": """你是业务分析师。你关注业务表现的现状描述。

## 分析视角
- 排名分析（Top N / Bottom N）
- 占比分析（各部分占总体的比例）
- 结构分析（按维度拆解的构成分布）

## 子问题要求
- 产出 3-4 个具体子问题
- 每个子问题必须指定：涉及的维度字段、指标字段、分析类型
- 子问题之间互补不重复
- 问题要用自然中文表达，仿佛你在向数据团队提需求""",

    "数据分析师": """你是数据分析师。你关注数据背后的规律和模式。

## 分析视角
- 趋势分析（随时间的变化趋势）
- 异常检测（离群值、突变点）
- 相关性分析（维度之间的关联关系）
- 波动分析（周期性和波动幅度）

## 子问题要求
- 产出 3-4 个具体子问题
- 每个子问题必须指定分析类型
- 侧重"为什么"而不是"是什么"
- 关注数据中的非显性信息""",

    "管理决策者": """你是管理决策者。你关注战略目标的对齐和业务决策支持。

## 分析视角
- 目标达成分析（实际 vs 目标）
- 同比环比分析（与历史对比）
- 跨区域/跨部门对标（横向对比）
- 重点关注清单（需要关注的异常项）

## 子问题要求
- 产出 3-4 个具体子问题
- 每个子问题必须指定分析类型
- 侧重"接下来怎么办"的决策支持
- 关注风险和机会""",
}

ROLE_OUTPUT_FORMAT = """
## 输出格式
严格输出以下 JSON：
{
  "role": "你的角色名",
  "perspective": "你的分析视角简述",
  "sub_questions": [
    {
      "id": 1,
      "question": "具体的分析子问题，用自然中文表达",
      "analysis_type": "ranking|structure|top_n|trend|anomaly|correlation|target_achievement|yoy_mom|comparison|attention",
      "dimensions": ["用到的维度字段"],
      "metrics": ["用到的指标字段"],
      "description": "这个子问题的简短说明"
    }
  ]
}"""


class LocalRoleDecompositionAgent(BaseAgent):
    """角色拆解智能体 - 本地 LLM 实现（支持三种角色）"""

    VALID_ROLES = {"业务分析师", "数据分析师", "管理决策者"}

    def __init__(self, role: str = "业务分析师"):
        if role not in self.VALID_ROLES:
            raise ValueError(f"无效角色: {role}，有效值: {self.VALID_ROLES}")
        self.role = role
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["main_question"])

        main_question = input_data["main_question"]
        confirmed_filters = input_data.get("confirmed_filters", [])
        available_dimensions = input_data.get("available_dimensions", [])
        available_metrics = input_data.get("available_metrics", [])
        data_context = input_data.get("data_context", {})

        system_prompt = ROLE_PROMPTS[self.role] + ROLE_OUTPUT_FORMAT

        user_msg = f"""主问题: {main_question}

已确认的筛选条件: {json.dumps(confirmed_filters, ensure_ascii=False)}
可用维度字段: {json.dumps(available_dimensions, ensure_ascii=False)}
可用指标字段: {json.dumps(available_metrics, ensure_ascii=False)}
数据上下文: {json.dumps(data_context, ensure_ascii=False)}
当前角色: {self.role}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        result = await _call_llm_with_retry(
            self.llm, messages,
            model=LLM_MODEL_QWEN_PRIMARY,
            temperature=0.5,
            max_tokens=2048,
            timeout=20.0,
        )
        result.setdefault("role", self.role)
        result.setdefault("perspective", "")
        result.setdefault("sub_questions", [])
        return result


# ─────────────────────────────────────────────
#  Agent G: 子问题筛选智能体
# ─────────────────────────────────────────────

AGENT_G_SYSTEM_PROMPT = """你是分析问题筛选专家。从多个角色产出的子问题中筛选出最优的 5 个。

## 筛选原则
1. 去重：语义相近的问题只保留表达更清晰的版本
2. 互补：确保最终 5 个问题覆盖全部 5 个分析维度：
   - drill_down（下钻）：细粒度分析
   - roll_up（上卷）：汇总/目标层面
   - trend（趋势）：时间维度的变化
   - structure（结构）：组成分布
   - comparison（对比）：跨维度/跨对象对比
3. 价值排序：对回答主问题贡献度高的优先
4. 可执行性：确保子问题能用数据查询实现

## 输出要求
- coverage_check 每个维度填 true/false
- 如果某维度缺失，说明原因
- 为每个 selected_question 写 selection_reason
- removed_questions 列出被移除的问题及原因

## 输出格式
严格输出 JSON：
{
  "selected_questions": [
    {
      "id": 1,
      "question": "子问题文本",
      "analysis_type": "类型",
      "dimensions": ["维度"],
      "metrics": ["指标"],
      "source_role": "来源角色",
      "selection_reason": "选择理由"
    }
  ],
  "coverage_check": {
    "drill_down": true, "roll_up": true, "trend": true, "structure": true, "comparison": true
  },
  "removed_questions": [
    {"question": "被移除的问题", "reason": "移除原因"}
  ]
}"""


class LocalSubQuestionSelectorAgent(BaseAgent):
    """子问题筛选智能体 - 本地 LLM 实现"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["role_questions"])

        role_questions = input_data["role_questions"]
        main_question = input_data.get("main_question", "")

        user_msg = f"""主问题: {main_question}

各角色产出的子问题:
{json.dumps(role_questions, ensure_ascii=False, indent=2)}"""

        messages = [
            {"role": "system", "content": AGENT_G_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        result = await _call_llm_with_retry(
            self.llm, messages,
            model=LLM_MODEL_QWEN_ALT,
            temperature=0.3,
            max_tokens=3072,
            timeout=20.0,
        )
        result.setdefault("selected_questions", [])
        result.setdefault("coverage_check", {})
        result.setdefault("removed_questions", [])
        return result


# ─────────────────────────────────────────────
#  Agent H: SQL 生成智能体
# ─────────────────────────────────────────────

AGENT_H_SYSTEM_PROMPT = """你是 SQL 专家，负责将自然语言分析问题转化为 MySQL 查询语句。

## 输入
- 分析问题列表（含维度、指标、分析类型）
- 所有可用表的完整 Schema（表名、字段名、字段类型）
- 已确认的筛选条件
- 数据库类型：MySQL

## SQL 编写规则
1. 只生成 SELECT 语句，禁止 INSERT/UPDATE/DELETE/DROP/ALTER
2. 使用提供的真实表名和字段名，不要自己编造
3. 聚合查询必须包含 GROUP BY
4. 百分比计算使用 ROUND(value * 100.0 / total, 2)
5. 排名使用 ORDER BY ... DESC LIMIT N
6. 趋势分析使用 DATE_FORMAT 按时间分组
7. 处理 NULL 值，使用 COALESCE 或 WHERE field IS NOT NULL
8. 涉及多表关联时使用 JOIN，指定正确的关联字段
9. 添加适当的 WHERE 条件（已确认的 filters）
10. 为每个 SQL 添加注释说明查询目的

## 表名规则
- 表名格式为 file_{file_id}_sheet_{index}
- 引用表名时必须使用完整名称
- 表名和字段名必须使用 MySQL 反引号包裹

## 输出格式
严格输出：
{
  "queries": [
    {
      "question_id": 1,
      "question": "原始问题",
      "sql": "完整的 SQL 语句",
      "tables_used": ["用到的表名"],
      "sql_type": "ranking|trend|structure|comparison|filter|target_achievement|detail"
    }
  ]
}"""


class LocalSQLGeneratorAgent(BaseAgent):
    """SQL 生成智能体 - 本地 LLM 实现"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["questions", "table_schemas"])

        questions = input_data["questions"]
        table_schemas = input_data["table_schemas"]
        filters = input_data.get("filters", [])
        db_type = input_data.get("db_type", "MySQL")

        # 简化表结构（减少 token）
        simplified_schemas = {}
        for tn, info in table_schemas.items():
            if isinstance(info, dict):
                cols = info.get("columns", info) if "columns" in info else info
            elif isinstance(info, list):
                cols = info
            else:
                cols = []
            simplified_schemas[tn] = {
                "columns": [
                    {"name": c.get("name", c) if isinstance(c, dict) else c,
                     "type": c.get("type", "text") if isinstance(c, dict) else "text"}
                    for c in cols
                ]
            }
            if isinstance(info, dict) and "sheet_name" in info:
                simplified_schemas[tn]["sheet_name"] = info["sheet_name"]

        user_msg = f"""数据库类型: {db_type}

表结构:
{json.dumps(simplified_schemas, ensure_ascii=False, indent=2)}

已确认的筛选条件: {json.dumps(filters, ensure_ascii=False)}

需要生成 SQL 的问题:
{json.dumps(questions, ensure_ascii=False, indent=2)}"""

        messages = [
            {"role": "system", "content": AGENT_H_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        result = await _call_llm_with_retry(
            self.llm, messages,
            model=LLM_MODEL_QWEN_PRIMARY,
            temperature=0.2,
            max_tokens=4096,
            timeout=30.0,
        )
        result.setdefault("queries", [])
        return result


# ─────────────────────────────────────────────
#  Agent I: 图表生成智能体
# ─────────────────────────────────────────────

AGENT_I_SYSTEM_PROMPT = """你是数据可视化专家，负责根据分析问题和数据生成 ECharts 图表配置。

## 图表类型选择规则
- ranking（排名）→ 横向柱状图（bar），Y 轴为维度，X 轴为数值
- trend（趋势）→ 折线图（line），X 轴为时间，smooth: true
- structure（占比）→ 环形饼图（pie），radius: ['45%', '70%']
- comparison（对比）→ 分组柱状图（bar），多系列
- target_achievement（达成率）→ 柱状图 + markLine 标注目标线
- detail（明细）→ 表格（table），直接返回原始数据

## ECharts 配置要求
1. 使用 Apple 风格配色：
   - 主系列 #007AFF
   - 次要系列 #34C759
   - 第三系列 #FF9500
   - 第四系列 #5AC8FA
2. 柱状图圆角 borderRadius: [0, 6, 6, 0]
3. 折线图 smooth: true，添加渐变面积填充
4. 字号：title 14px, axisLabel 11px
5. tooltip 必须有 formatter
6. grid 留白合理，避免文字溢出
7. 数据量大时（>10 项）考虑只显示 Top 10
8. 饼图显示百分比标签

## 输出格式
严格输出：
{
  "chart_type": "bar|line|pie|table",
  "title": "图表标题",
  "subtitle": "副标题（可选）",
  "chart_reason": "为什么选这个图表类型（一句话）",
  "echarts_option": {完整的 ECharts option JSON},
  "insight_text": "一句简短的数据洞察（20 字以内）"
}"""


class LocalChartGeneratorAgent(BaseAgent):
    """图表生成智能体 - 本地 LLM 实现"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["question", "data"])

        question = input_data["question"]
        data = input_data["data"]
        analysis_type = input_data.get("analysis_type", "auto")
        chart_preference = input_data.get("chart_preference", "auto")

        # 限制数据量
        truncated_data = data[:50] if len(data) > 50 else data

        user_msg = f"""问题: {question}
分析类型: {analysis_type}
图表偏好: {chart_preference}

查询结果数据 (共 {len(data)} 行，显示前 {len(truncated_data)} 行):
{json.dumps(truncated_data, ensure_ascii=False, indent=2)}"""

        messages = [
            {"role": "system", "content": AGENT_I_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        result = await _call_llm_with_retry(
            self.llm, messages,
            model=LLM_MODEL_QWEN_ALT,
            temperature=0.3,
            max_tokens=4096,
            timeout=20.0,
        )
        result.setdefault("chart_type", "bar")
        result.setdefault("title", question)
        result.setdefault("chart_reason", "")
        result.setdefault("echarts_option", {})
        result.setdefault("insight_text", "")
        return result


# ─────────────────────────────────────────────
#  Agent J: 总结报告智能体
# ─────────────────────────────────────────────

AGENT_J_SYSTEM_PROMPT = """你是商业分析报告撰写专家。基于多维度的数据分析和图表结果，撰写结构化的分析报告。

## 报告结构
1. 核心结论（2-3 句话）：直接回答用户的主问题，给出最关键的发现
2. 详细分析（按图表逐一解读）：每个图表对应一段分析文字
3. 洞察发现（3-5 条）：从数据中提炼的非显性规律
4. 行动建议（2-3 条）：面向业务的可执行建议

## 写作风格
- 面向业务管理者，语言简洁有力
- 每个结论都要有数据支撑
- 避免"可能""大概"等模糊表述
- 用具体数字说话

## 输出格式
严格输出 JSON：
{
  "report": {
    "title": "分析报告标题",
    "core_conclusion": "2-3句话的核心结论",
    "detailed_analysis": [
      {
        "chart_id": 1,
        "title": "对应图表的标题",
        "content": "分析文字，说清楚'是什么、为什么、怎么样'"
      }
    ],
    "insights": ["3-5条具体的洞察发现"],
    "recommendations": ["2-3条可执行的行动建议"]
  }
}"""


class LocalReportGeneratorAgent(BaseAgent):
    """总结报告智能体 - 本地 LLM 实现"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["main_question", "sub_questions", "data_results"])

        main_question = input_data["main_question"]
        sub_questions = input_data["sub_questions"]
        data_results = input_data["data_results"]
        confirmed_filters = input_data.get("confirmed_filters", [])
        data_context = input_data.get("data_context", {})

        # 构建精简输入（不传原始数据）
        simplified_results = []
        for i, dr in enumerate(data_results):
            item = {"question": dr.get("question", ""), "row_count": len(dr.get("data", []))}
            # 传入关键统计值而非全部数据
            data = dr.get("data", [])
            if data:
                item["sample"] = data[:3]
            simplified_results.append(item)

        user_msg = f"""主问题: {main_question}
筛选条件: {json.dumps(confirmed_filters, ensure_ascii=False)}
数据上下文: {json.dumps(data_context, ensure_ascii=False)}

子问题与数据结果概要:
{json.dumps(simplified_results, ensure_ascii=False, indent=2)}"""

        messages = [
            {"role": "system", "content": AGENT_J_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        result = await _call_llm_with_retry(
            self.llm, messages,
            model=LLM_MODEL_QWEN_PRIMARY,
            temperature=0.4,
            max_tokens=4096,
            timeout=30.0,
        )
        result.setdefault("report", {})
        return result


# ─────────────────────────────────────────────
#  Agent K: 快速问答智能体
# ─────────────────────────────────────────────

AGENT_K_SYSTEM_PROMPT = """你是 XLSX-BI 的数据分析助手，帮助用户快速查询和理解他们的业务数据。

## 可用数据上下文
每次对话开始时，系统会注入当前文件的数据概览：
- sheets_summary: 各 Sheet 的总结信息
- table_schemas: 各表的字段列表

## 你的能力
1. 理解用户的自然语言查询
2. 判断问题涉及哪个 Sheet
3. 生成相应的 SQL 查询（MySQL 语法）
4. 以自然语言解释查询结果
5. 主动推荐 3 个相关的追问方向

## 回答格式
当需要执行查询时，输出：
{
  "type": "query",
  "target_sheet": "目标 Sheet 名",
  "sql": "SELECT ... FROM <表名> WHERE ...",
  "answer": "根据查询结果，...（用自然语言总结）",
  "recommended_questions": ["追问1", "追问2", "追问3"]
}

当仅基于已有信息回答时（不需要新查询）：
{
  "type": "answer",
  "answer": "直接回答用户...",
  "recommended_questions": ["追问1", "追问2", "追问3"]
}

## 注意事项
- SQL 只生成 SELECT 语句，使用给定的真实表名和字段名
- 回答要简洁，用业务语言，不要技术术语
- 推荐追问要基于当前问题的上下文做合理延伸
- 如果用户问题超出数据范围，诚实告知"""


class LocalQuickQAAgent(BaseAgent):
    """快速问答智能体 - 本地 LLM 实现"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_input(input_data, ["question", "sheets_summary", "table_schemas"])

        question = input_data["question"]
        sheets_summary = input_data["sheets_summary"]
        table_schemas = input_data["table_schemas"]
        conversation_history = input_data.get("conversation_history", [])

        # 构建对话上下文
        history_text = ""
        if conversation_history:
            history_lines = []
            for msg in conversation_history[-10:]:
                role = msg.get("role", "")
                content = msg.get("content", "")
                history_lines.append(f"{role}: {content}")
            history_text = "\n".join(history_lines)

        user_msg_parts = [
            f"用户问题: {question}",
            "",
            "Sheet 总结:",
            json.dumps(sheets_summary, ensure_ascii=False, indent=2),
            "",
            "表结构:",
            json.dumps(table_schemas, ensure_ascii=False, indent=2),
        ]
        if history_text:
            user_msg_parts.extend(["", "对话历史:", history_text])

        user_msg = "\n".join(user_msg_parts)

        messages = [
            {"role": "system", "content": AGENT_K_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        result = await _call_llm_with_retry(
            self.llm, messages,
            model=LLM_MODEL_QWEN_PRIMARY,
            temperature=0.3,
            max_tokens=2048,
            timeout=20.0,
        )
        result.setdefault("type", "answer")
        result.setdefault("answer", "")
        result.setdefault("recommended_questions", [])
        return result
