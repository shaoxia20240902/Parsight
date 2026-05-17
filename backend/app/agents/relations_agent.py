"""
空间级 Sheet 关联分析智能体 — Markdown 输出
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from app.config import AGENT_MAX_RETRIES, LLM_MODEL_DEEPSEEK_PRIMARY
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

RELATIONS_SYSTEM_PROMPT = """你是一位企业级数据仓库架构师，擅长从多张业务表中识别实体关系、主外键与星型/雪花模型结构。

## 输入
你会收到同一数据空间下多个 Sheet 的：
1. 各表 AI 单表理解（六维分析摘要）
2. 各表随机 20 行样本数据
3. 表名、字段列表、行数

## 分析原则
1. **证据驱动**：关联判断必须基于字段名语义、单表理解、样本值重叠，禁止臆造不存在的表或字段。
2. **明确关联键**：每一条关联必须写清 from_table、to_table、from_field、to_field。
3. **诚实边界**：若关联不确定，在「业务解释」或「置信度」中标注「待确认」，并说明依据不足。
4. **中文输出**，专业术语可保留英文（如 KPI、FK）。

## 输出格式（严格遵守）
只输出 Markdown 正文，不要用代码块包裹全文。必须包含以下章节：

## 一、数据域与整体概览

用 2-3 段说明：这些 Sheet 共同描述什么业务域？数据是否来自同一业务流程？整体适合何种分析范式（星型、雪花、平行明细等）？

## 二、各 Sheet 角色定位

用 Markdown 表格，列：**Sheet 名称** | **数据库表名** | **角色** | **说明**

角色取值：事实表 / 维度表 / 桥表 / 对照表 / 独立明细 / 待确认

## 三、Sheet 间关联关系

用 Markdown 表格，列：
**源表** | **源字段** | **目标表** | **目标字段** | **关系类型** | **置信度** | **业务解释**

- 关系类型：多对一 / 一对多 / 一对一 / 多对多（需桥表）
- 置信度：高 / 中 / 待确认
- 只写你认为存在关联的表对；无关联的 Sheet 在第四章说明

## 四、无直接关联或弱关联的 Sheet

列出暂未发现可靠关联的 Sheet 及原因（每条以「- 」开头）。

## 五、推荐跨表分析场景

列出 6-10 个可执行的跨表业务问题或分析路径（每条以「- 」开头）。

## 六、数据质量与关联风险

列出 5-8 条跨表层面的质量风险（键不一致、粒度不匹配、空值、编码体系不同等）。有不确定处明确写「待确认」。"""

EXTRACT_DISPUTED_RELATIONS_PROMPT = """你是跨表数据关联审核专家。阅读一份「多 Sheet 关联分析」Markdown 文档，提取其中**不确定或待确认**的关联关系。

## 识别标准
- 置信度为「待确认」或「中」的关联行
- 业务解释中含：待确认、不确定、可能、或有异议、建议核实、样本不足
- 第六章点名的跨表风险所涉及的表与字段

## 输出 JSON（仅 JSON）
{
  "disputed_relations": [
    {
      "from_table": "数据库表名",
      "to_table": "数据库表名",
      "from_field": "源字段名",
      "to_field": "目标字段名",
      "issue_summary": "异议说明一句话"
    }
  ]
}

若无异议关联，返回 {"disputed_relations": []}
表名与字段名必须来自合法列表，不得编造。"""

REGENERATE_RELATIONS_PROMPT = (
    RELATIONS_SYSTEM_PROMPT
    + """

## 修订任务
你正在修订先前的多 Sheet 关联分析。初稿中部分关联存在不确定，系统已对异议关联执行 SQL 核实（JOIN 匹配行数、取值重叠等）。

请结合核实结果：
1. 更新第三章关联表：修正或删除无法成立的关联，将「待确认」改为基于证据的结论
2. 更新第六章：已解决的问题可删除，仍存在的保留
3. 输出完整 Markdown（六章齐全），修订后应尽量减少「待确认」表述"""
)


class RelationsAnalysisAgent:
    def __init__(self):
        self.llm = LLMClient()

    async def run(self, sheets_context: List[Dict[str, Any]]) -> str:
        user_msg = self._build_user_message(sheets_context)
        messages = [
            {"role": "system", "content": RELATIONS_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        content = await self._chat_with_retry(messages)
        return self._strip_code_fence(content)

    async def extract_disputed_relations(
        self,
        relations_content: str,
        valid_tables: List[str],
        table_columns: Dict[str, List[str]],
    ) -> List[Dict[str, str]]:
        cols_desc = {t: table_columns.get(t, []) for t in valid_tables}
        user_msg = f"""请从以下关联分析文档中提取待核实的关联。

## 合法表名
{json.dumps(valid_tables, ensure_ascii=False)}

## 各表字段
{json.dumps(cols_desc, ensure_ascii=False, indent=2)}

## 关联分析文档
{relations_content}"""

        result = await self._chat_json_with_retry([
            {"role": "system", "content": EXTRACT_DISPUTED_RELATIONS_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        items = result.get("disputed_relations", [])
        if not isinstance(items, list):
            raise ValueError("异议关联解析格式错误")

        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            ft = (item.get("from_table") or "").strip()
            tt = (item.get("to_table") or "").strip()
            ff = (item.get("from_field") or "").strip()
            tf = (item.get("to_field") or "").strip()
            if ft in valid_tables and tt in valid_tables:
                if ff in table_columns.get(ft, []) and tf in table_columns.get(tt, []):
                    normalized.append({
                        "from_table": ft,
                        "to_table": tt,
                        "from_field": ff,
                        "to_field": tf,
                        "issue_summary": (item.get("issue_summary") or "").strip(),
                    })
        return normalized

    async def regenerate_with_verification(
        self,
        sheets_context: List[Dict[str, Any]],
        previous_content: str,
        verification_results: List[Dict[str, Any]],
    ) -> str:
        user_msg = f"""请修订以下多 Sheet 关联分析。

## 各 Sheet 上下文
{self._build_user_message(sheets_context)}

## 初稿
{previous_content}

## 异议关联 SQL 核实结果
{json.dumps(verification_results, ensure_ascii=False, indent=2, default=str)}

请输出修订后的完整六章 Markdown。"""

        messages = [
            {"role": "system", "content": REGENERATE_RELATIONS_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        content = await self._chat_with_retry(messages, max_tokens=4096, timeout=120.0)
        return self._strip_code_fence(content)

    def _build_user_message(self, sheets_context: List[Dict[str, Any]]) -> str:
        parts = [f"共 {len(sheets_context)} 个 Sheet，请分析它们之间的关联。\n"]
        for s in sheets_context:
            col_names = [c["name"] for c in s.get("columns", [])]
            parts.append(f"""
### Sheet: {s.get('sheet_name')}（表 `{s.get('table_name')}`，{s.get('row_count', 0)} 行）

**字段列表**: {', '.join(col_names)}

**单表 AI 理解**:
{s.get('understanding', '')}

**随机样本 {len(s.get('sample_rows', []))} 行**:
{json.dumps(s.get('sample_rows', []), ensure_ascii=False, indent=2, default=str)}
""")
        return "\n".join(parts)

    async def _chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = None,
        max_tokens: int = 4096,
        timeout: float = 90.0,
    ) -> str:
        if max_retries is None:
            max_retries = AGENT_MAX_RETRIES
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await self.llm.chat_completion(
                    messages=messages,
                    temperature=0.35,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    model_override=LLM_MODEL_DEEPSEEK_PRIMARY,
                )
            except Exception as e:
                last_error = e
                logger.warning("Relations LLM attempt %s failed: %s", attempt + 1, e)
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
        raise RuntimeError(f"关联分析 LLM 调用失败: {last_error}")

    async def _chat_json_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = None,
    ) -> Dict[str, Any]:
        if max_retries is None:
            max_retries = AGENT_MAX_RETRIES
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await self.llm.chat_completion_json(
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2048,
                    timeout=60.0,
                    model_override=LLM_MODEL_DEEPSEEK_PRIMARY,
                )
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
        raise RuntimeError(f"异议关联提取失败: {last_error}")

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        text = (text or "").strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text
