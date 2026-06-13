from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class ChatModeProfile:
    label: str
    intent: str
    purpose: str
    steps: List[str]
    confirm_question: str


MODE_PROFILES: Dict[str, ChatModeProfile] = {
    "quick": ChatModeProfile(
        label="快速问答",
        intent="quick_qa",
        purpose="快速读取字段、查询关键结果，并给出简洁业务回答。",
        steps=["识别问题指向", "选择相关 Sheet/字段", "执行必要查询", "生成答案和追问"],
        confirm_question="我会按快速问答处理，直接给你结论和可追问方向。是否继续？",
    ),
    "insight": ChatModeProfile(
        label="快速问答",
        intent="quick_qa",
        purpose="快速读取字段、查询关键结果，并给出简洁业务回答。",
        steps=["识别问题指向", "选择相关 Sheet/字段", "执行必要查询", "生成答案和追问"],
        confirm_question="我会按快速问答处理，直接给你结论和可追问方向。是否继续？",
    ),
    "deep": ChatModeProfile(
        label="深度洞察",
        intent="deep_insight",
        purpose="按 ReAct 流程做多角色拆解、SQL 验证、图表和结论综合。",
        steps=["装配数据上下文", "意图与关键词澄清", "多角色拆解子问题", "生成并执行 SQL", "沉淀图表证据", "输出洞察报告"],
        confirm_question="这个问题适合进入深度洞察链路，我会多步分析并生成结构化报告。是否继续？",
    ),
    "builder": ChatModeProfile(
        label="生成 BI",
        intent="bi_builder",
        purpose="把业务语言转成可执行的 BI 图表方案，并在确认后写入 BI 看板。",
        steps=["识别报表意图", "匹配已有图表", "规划指标/维度/筛选", "确认报表方案", "生成或更新 BI 图表"],
        confirm_question="我会按生成 BI 处理，先确认报表方案，再写入 BI 看板。是否继续？",
    ),
}


class ChatIntentService:
    """轻量意图预检服务。

    这个服务不调用 LLM，避免每次发送消息都额外消耗一次模型调用。它把三种问答
    的执行边界显式化，让前端在进入耗时链路前与用户确认。
    """

    def classify(
        self,
        question: str,
        mode: str,
        table_schemas: Dict[str, Any],
        sheets_summary: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        normalized_mode = self._normalize_mode(mode, question)
        profile = MODE_PROFILES[normalized_mode]
        coverage = self._estimate_coverage(question, table_schemas, sheets_summary)
        ambiguity = self._detect_ambiguity(question, table_schemas)
        should_confirm = self._should_confirm(question, ambiguity)

        return {
            "status": "need_confirm" if should_confirm else "ready",
            "mode": normalized_mode,
            "mode_label": profile.label,
            "intent": profile.intent,
            "confidence": coverage["confidence"],
            "purpose": profile.purpose,
            "requires_confirmation": should_confirm,
            "auto_execute": not should_confirm,
            "execution_note": "已完成意图识别，将继续调用真实 Agent 执行。" if not should_confirm else "问题还不够明确，建议补充后再执行。",
            "confirm_question": self._confirm_question(profile, coverage, ambiguity),
            "evidence": coverage["evidence"],
            "warnings": ambiguity,
            "plan_steps": profile.steps,
            "actions": [
                {"type": "confirm_intent", "label": "确认并调用 LLM 执行", "variant": "primary"},
                {"type": "refine_intent", "label": "我补充一下", "variant": "secondary"},
                {"type": "cancel_intent", "label": "先不执行", "variant": "secondary"},
            ],
        }

    def _normalize_mode(self, mode: str, question: str) -> str:
        mode = (mode or "quick").strip()
        if mode == "insight":
            mode = "quick"
        if mode in {"quick", "deep", "builder"}:
            return mode
        text = question.lower()
        if any(token in question for token in ("生成", "创建", "看板", "报表", "图表")):
            return "builder"
        if any(token in question for token in ("为什么", "原因", "根因", "深度", "趋势", "异常", "对比")):
            return "deep"
        if any(token in text for token in ("dashboard", "chart", "bi")):
            return "builder"
        return "quick"

    def _estimate_coverage(
        self,
        question: str,
        table_schemas: Dict[str, Any],
        sheets_summary: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        fields: List[str] = []
        for table_name, info in table_schemas.items():
            columns = info.get("columns", []) if isinstance(info, dict) else []
            for col in columns:
                if isinstance(col, dict) and col.get("name"):
                    fields.append(str(col["name"]))
            if isinstance(info, dict):
                fields.append(str(info.get("sheet_name") or table_name))
        for sheet in sheets_summary:
            fields.extend([str(x) for x in sheet.get("key_dimensions") or []])
            fields.extend([str(x) for x in sheet.get("key_metrics") or []])

        matched = []
        for field in dict.fromkeys(fields):
            if field and field in question:
                matched.append(field)

        if matched:
            confidence = min(0.92, 0.58 + len(matched) * 0.08)
            evidence = [f"命中数据字段：{name}" for name in matched[:5]]
        else:
            confidence = 0.62
            evidence = ["未直接命中字段名，将结合表理解、字段样本和问题语义推断。"]
        return {"confidence": round(confidence, 2), "evidence": evidence}

    def _detect_ambiguity(self, question: str, table_schemas: Dict[str, Any]) -> List[str]:
        warnings: List[str] = []
        if len(question.strip()) < 6:
            warnings.append("问题较短，可能需要补充指标或维度。")
        if any(token in question for token in ("这个", "那个", "它", "上面")):
            warnings.append("问题包含指代词，我会结合最近对话理解；如理解不对可补充说明。")

        numeric_fields = []
        for info in table_schemas.values():
            columns = info.get("columns", []) if isinstance(info, dict) else []
            for col in columns:
                if isinstance(col, dict) and col.get("type") == "number":
                    numeric_fields.append(col.get("name"))
        if numeric_fields and not any(str(field) in question for field in numeric_fields if field):
            warnings.append("未明确指标，我会优先使用表理解中的核心指标。")
        return warnings[:3]

    def _confirm_question(
        self,
        profile: ChatModeProfile,
        coverage: Dict[str, Any],
        warnings: List[str],
    ) -> str:
        if warnings:
            return f"{profile.confirm_question} 我发现还有 {len(warnings)} 个可能影响结果的点，会在执行时显式处理。"
        if coverage["confidence"] >= 0.8:
            return f"{profile.confirm_question} 当前数据命中度较高。"
        return profile.confirm_question

    def _should_confirm(self, question: str, ambiguity: List[str]) -> bool:
        stripped = question.strip()
        if len(stripped) < 6:
            return True
        if any(token in stripped for token in ("这个", "那个", "它", "上面")):
            return True
        return False
