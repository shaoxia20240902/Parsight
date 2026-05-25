"""
表理解智能体 — 基于六维框架输出 Markdown 格式的深度业务理解
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from app.config import AGENT_MAX_RETRIES
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

UNDERSTANDING_SYSTEM_PROMPT = """你是一位拥有 15 年经验的资深数据分析师与业务顾问，擅长从原始表格数据中提炼业务洞察。
你的读者是业务负责人和数据分析师，他们需要快速理解一张陌生数据表能回答什么业务问题。

## 你的分析原则
1. **证据驱动**：所有判断必须基于提供的表头、字段样本值和 100 行采样数据，禁止凭空编造表中不存在的字段或业务场景。
2. **业务视角**：不要只做字段名翻译，要结合样本值推断真实业务含义（例如「城市ID」可能是行政区划编码而非简单序号）。
3. **深度优先**：宁可少写废话，每条洞察都要有具体依据；避免「该表数据丰富」「适合分析」等空洞表述。
4. **诚实边界**：若样本不足以判断，明确写「样本中暂未观察到…，建议进一步核实」。
5. **中文输出**：全文使用简体中文，专业术语可保留英文缩写（如 KPI、GMV）。

## 输出格式（严格遵守）
你必须且只能输出 Markdown 正文，不要输出 JSON，不要用 ```markdown 代码块包裹全文。
必须包含以下六个二级标题，顺序不可调换：

## 一、这个是什么表？

用 2-4 段话回答：
- 这张表在业务上记录的是什么实体/事件/状态？
- 数据粒度是什么（逐笔、逐日汇总、主数据快照等）？
- 表在典型分析链路中可能扮演什么角色（事实表、维度表、桥表等）？
- 若能从样本推断时间跨度、覆盖范围、核心业务域，请具体写出。

## 二、字段解释

输出一个 Markdown 表格，表头固定为三列：**字段名** | **中文含义** | **业务解释**

要求：
- 覆盖输入中的每一个字段，不得遗漏
- 「中文含义」用简短名词短语（5-15 字）
- 「业务解释」说明该字段在业务上的用途、与其他字段的可能关系、从样本值观察到的特征（如编码规则、枚举取值、是否可能为主键/外键）
- 若某字段含义不确定，在业务解释中标注「待确认」并说明依据不足的原因

## 三、核心业务分析维度

列出 4-8 个适合作为切片/分组/下钻的**业务维度**（不是字段名列举，而是业务分析视角），每条格式：
- **维度名称**：（对应字段：xxx）— 一句话说明该维度能支持什么分析场景

## 四、关键业务指标（KPI）

列出 3-6 个可从该表直接或间接计算/观察的 KPI，每条格式：
- **指标名称**：（计算逻辑或来源字段）— 业务意义 + 若样本支持，补充观察到的数量级或分布特征

若表中无明显数值指标，说明应以计数类、占比类或关联其他表后的派生指标为主。

## 五、数据质量提示与注意事项

列出 5-8 条具体的数据质量与使用注意，例如：
- 空值、重复、异常值、编码不一致、单位混用、时间断层、主键完整性
- 必须基于样本中的真实观察，每条以「- 」开头

## 六、推荐分析切入点（业务问题）

列出 6-10 个可直接交给分析师或 BI 系统的**业务问题**（用问句或「分析…」的祈使句），要求：
- 具体、可执行、与表内容强相关
- 覆盖对比、趋势、结构、关联、异常检测等不同角度
- 每条以「- 」开头"""

EXTRACT_DISPUTED_FIELDS_PROMPT = """你是数据质量审核专家。阅读一份数据表的 AI 业务理解文档，找出其中**存在异议、不确定、待核实**表述所涉及的字段。

## 识别标准（满足任一即纳入）
- 业务解释中含：待确认、不确定、可能、或有异议、建议核实、样本不足、无法判断、尚不明确
- 「五、数据质量提示」中点名存在问题的字段
- 对字段含义、编码规则、单位、取值范围存疑的表述

## 输出要求
严格输出 JSON，不要输出其他文字：
{
  "disputed_fields": [
    {
      "field_name": "必须与合法字段列表完全一致",
      "issue_summary": "原文中的异议说明（一句话）"
    }
  ]
}

若无任何异议字段，返回 {"disputed_fields": []}"""

REGENERATE_WITH_VERIFICATION_PROMPT = (
    UNDERSTANDING_SYSTEM_PROMPT
    + """

## 修订任务（重要）
你正在**修订**先前版本的表理解。初稿中对部分字段存在不确定或异议，系统已针对这些字段执行 `SELECT DISTINCT` 全量去重查询（最多 500 个取值）完成核实。

请结合核实结果：
1. 修正「二、字段解释」中相关字段的业务解释，删除或更新「待确认」类表述
2. 更新「五、数据质量提示」中与核实结果相关的条目
3. 若 KPI 或分析维度受影响，同步调整第三、四、六章

必须输出**完整**六维 Markdown（不是 diff），格式与初稿相同。"""
)


class TableUnderstandingAgent:
    """生成表六维理解的智能体"""

    def __init__(self):
        self.llm = LLMClient()

    async def run(self, input_data: Dict[str, Any]) -> str:
        sheet_name = input_data.get("sheet_name", "未命名表")
        table_name = input_data.get("table_name", sheet_name)
        columns = input_data.get("columns", [])
        sample_rows = input_data.get("sample_rows", [])
        row_count = input_data.get("row_count", 0)
        first_n_count = input_data.get("first_n_count", 10)
        random_n_count = input_data.get("random_n_count", 0)

        col_lines = []
        for col in columns:
            samples = col.get("sample_values", [])[:5]
            col_lines.append(
                f"- {col['name']}（类型={col.get('type', 'text')}，"
                f"唯一值数={col.get('unique_count', '?')}，样本值={samples}）"
            )

        sample_preview = sample_rows[:100]
        user_msg = f"""请对以下数据表进行六维深度理解分析。

## 表基本信息
- 业务表名（Sheet）：{sheet_name}
- 数据库表名：{table_name}
- 总行数：{row_count}
- 字段数：{len(columns)}

## 字段列表（含样本值）
{chr(10).join(col_lines)}

## 采样数据说明
以下共 {len(sample_preview)} 行：前 {first_n_count} 行为顺序采样，其余为随机采样（共 {random_n_count} 行随机样本）。

## 采样数据
{json.dumps(sample_preview, ensure_ascii=False, indent=2, default=str)}"""

        messages = [
            {"role": "system", "content": UNDERSTANDING_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        content = await self._chat_with_retry(messages)
        return self._strip_code_fence(content)

    async def run_stream(self, input_data: Dict[str, Any]):
        """流式生成表六维理解，逐块 yield content"""
        sheet_name = input_data.get("sheet_name", "未命名表")
        table_name = input_data.get("table_name", sheet_name)
        columns = input_data.get("columns", [])
        sample_rows = input_data.get("sample_rows", [])
        row_count = input_data.get("row_count", 0)
        first_n_count = input_data.get("first_n_count", 10)
        random_n_count = input_data.get("random_n_count", 0)

        col_lines = []
        for col in columns:
            samples = col.get("sample_values", [])[:5]
            col_lines.append(
                f"- {col['name']}（类型={col.get('type', 'text')}，"
                f"唯一值数={col.get('unique_count', '?')}，样本值={samples}）"
            )

        sample_preview = sample_rows[:100]
        user_msg = f"""请对以下数据表进行六维深度理解分析。

## 表基本信息
- 业务表名（Sheet）：{sheet_name}
- 数据库表名：{table_name}
- 总行数：{row_count}
- 字段数：{len(columns)}

## 字段列表（含样本值）
{chr(10).join(col_lines)}

## 采样数据说明
以下共 {len(sample_preview)} 行：前 {first_n_count} 行为顺序采样，其余为随机采样（共 {random_n_count} 行随机样本）。

## 采样数据
{json.dumps(sample_preview, ensure_ascii=False, indent=2, default=str)}"""

        messages = [
            {"role": "system", "content": UNDERSTANDING_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        async for chunk in self.llm.chat_completion_stream(
            messages=messages,
            temperature=0.4,
            max_tokens=4096,
            timeout=300.0,
        ):
            yield chunk

    async def extract_disputed_fields(
        self,
        understanding_content: str,
        table_name: str,
        column_names: List[str],
    ) -> List[Dict[str, str]]:
        """从理解文档中提取有异议的字段"""
        user_msg = f"""请从以下表理解文档中提取存在异议的字段。

## 表名
{table_name}

## 合法字段列表（field_name 只能从此列表选取）
{json.dumps(column_names, ensure_ascii=False)}

## 表理解文档
{understanding_content}"""

        result = await self._chat_json_with_retry([
            {"role": "system", "content": EXTRACT_DISPUTED_FIELDS_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        fields = result.get("disputed_fields", [])
        if not isinstance(fields, list):
            raise ValueError("异议字段解析结果格式错误")
        valid = {n for n in column_names}
        normalized = []
        for item in fields:
            if not isinstance(item, dict):
                continue
            name = (item.get("field_name") or "").strip()
            if name in valid:
                normalized.append({
                    "field_name": name,
                    "issue_summary": (item.get("issue_summary") or "").strip(),
                })
        return normalized

    async def regenerate_with_verification(
        self,
        input_data: Dict[str, Any],
        previous_content: str,
        verification_results: List[Dict[str, Any]],
    ) -> str:
        """结合字段核实结果重新生成完整表理解"""
        sheet_name = input_data.get("sheet_name", "未命名表")
        table_name = input_data.get("table_name", sheet_name)
        columns = input_data.get("columns", [])
        sample_rows = input_data.get("sample_rows", [])
        row_count = input_data.get("row_count", 0)

        verification_block = json.dumps(
            verification_results, ensure_ascii=False, indent=2, default=str
        )

        col_lines = [
            f"- {col['name']}（类型={col.get('type', 'text')}）"
            for col in columns
        ]

        user_msg = f"""请修订以下数据表的六维业务理解。

## 表基本信息
- 业务表名：{sheet_name}
- 数据库表名：{table_name}
- 总行数：{row_count}

## 字段列表
{chr(10).join(col_lines)}

## 初稿（待修订）
{previous_content}

## 异议字段核实结果
以下字段已针对异议执行 SELECT DISTINCT 查询（最多 500 个去重值）：
{verification_block}

## 原始采样数据（供参考）
{json.dumps(sample_rows[:100], ensure_ascii=False, indent=2, default=str)}

请输出修订后的完整六维 Markdown。"""

        messages = [
            {"role": "system", "content": REGENERATE_WITH_VERIFICATION_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        content = await self._chat_with_retry(messages, max_tokens=4096, timeout=300.0)
        return self._strip_code_fence(content)

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
                    timeout=120.0,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Understanding JSON LLM attempt %s/%s failed: %s",
                    attempt + 1,
                    max_retries + 1,
                    e,
                )
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
        raise RuntimeError(
            f"异议字段提取 LLM 调用失败: {last_error}"
        )

    async def _chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = None,
        max_tokens: int = 4096,
        timeout: float = 180.0,
    ) -> str:
        if max_retries is None:
            max_retries = AGENT_MAX_RETRIES
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await self.llm.chat_completion(
                    messages=messages,
                    temperature=0.4,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Understanding LLM attempt %s/%s failed: %s",
                    attempt + 1,
                    max_retries + 1,
                    e,
                )
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
        raise RuntimeError(
            f"表理解 LLM 调用在 {max_retries + 1} 次尝试后仍失败: {last_error}"
        )

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
