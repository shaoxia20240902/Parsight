"""将 BI 流水线步骤转为自然语言思考记录，持久化供前端展示与搜索。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.bi_pipeline_logger import (
    STEP_BLUEPRINT_COMPLETE,
    STEP_BLUEPRINT_FAILED,
    STEP_CHART_DROPPED,
    STEP_CHART_DRAFT,
    STEP_COMPILE_SQL,
    STEP_GENERATE_END,
    STEP_GENERATE_START,
    STEP_INDUSTRY,
    STEP_QUESTIONS,
    STEP_REPAIR,
    STEP_REVIEW,
    STEP_ROLE_PICKER,
    STEP_SCENARIOS,
    STEP_SHEET_PIPELINE,
    STEP_SQL_PREVIEW,
    STEP_UNDERSTANDING_GATE,
)


def _loc_suffix(
    *,
    sheet_name: Optional[str] = None,
    table_name: Optional[str] = None,
    role_name: Optional[str] = None,
    scenario_name: Optional[str] = None,
) -> str:
    parts: List[str] = []
    if sheet_name:
        parts.append(f"「{sheet_name}」")
    elif table_name:
        parts.append(f"表 {table_name}")
    if role_name:
        parts.append(f"角色「{role_name}」")
    if scenario_name:
        parts.append(f"场景「{scenario_name}」")
    return " · ".join(parts) if parts else ""


def step_to_natural_language(
    step: str,
    message: str,
    *,
    level: str = "INFO",
    sheet_name: Optional[str] = None,
    table_name: Optional[str] = None,
    role_name: Optional[str] = None,
    scenario_name: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """把流水线 step + message 转成用户可读的一句思考。"""
    loc = _loc_suffix(
        sheet_name=sheet_name,
        table_name=table_name,
        role_name=role_name,
        scenario_name=scenario_name,
    )
    prefix = f"{loc}：" if loc else ""
    extra = extra or {}

    if step == STEP_GENERATE_START:
        return "正在建立数据资产视图：读取 Sheet 粒度、字段角色和业务口径，准备把 Excel 转成可审计的 BI 蓝图。"
    if step == STEP_UNDERSTANDING_GATE:
        pending = extra.get("pending_tables") or []
        if pending:
            return f"六维理解检查发现仍有 {len(pending)} 张表未就绪，先暂停生成，避免用不完整口径产出错误看板。"
        return "校验每张表是否已完成业务定义、字段语义、指标口径、数据质量、关联关系和分析建议六维理解。"
    if step == STEP_INDUSTRY:
        industry = extra.get("industry_guess") or {}
        primary = industry.get("primary") or industry.get("industry") or "业务"
        hints = industry.get("analysis_hints") or []
        suffix = f"，优先关注「{hints[0]}」" if hints else ""
        return f"综合表间关系、关键指标和样例值，判断当前数据更接近「{primary}」场景{suffix}。"
    if step == STEP_SHEET_PIPELINE:
        return f"{prefix}启动单表分析流水线，后续会依次完成角色选择、场景拆解、问题生成、SQL 编写和图表契约校验。"
    if step == STEP_ROLE_PICKER:
        if "选角完成" in message or "个角色" in message:
            n = extra.get("perspective_ids") or []
            count = len(n) if isinstance(n, list) else 0
            one_liner = extra.get("business_one_liner") or ""
            suffix = f"判断依据：{one_liner}" if one_liner else "后续会让不同角色提出互补问题，避免看板集中在单一视角。"
            return f"{prefix}选定 {count} 个业务视角，覆盖经营、运营和管理决策入口。{suffix}"
        return f"{prefix}正在从字段、粒度和业务描述中识别谁最需要这张表，以及他们会用它做什么决策。"
    if step == STEP_SCENARIOS:
        scenario_ids = extra.get("scenario_ids") or []
        if scenario_ids:
            return f"{prefix}拆出 {len(scenario_ids)} 个可落地分析场景，确保问题不是泛泛统计，而是对应真实复盘、预警或经营动作。"
        return f"{prefix}为当前角色拆解可执行的分析场景，先定义业务动作，再生成图表问题。"
    if step == STEP_QUESTIONS:
        question_ids = extra.get("question_ids") or []
        if question_ids:
            return f"{prefix}生成 {len(question_ids)} 个可被 SQL 回答的问题，并同步约束分析意图、推荐图表、必需字段和展示字段名称。"
        return f"{prefix}把业务场景落成可计算问题，同时约束指标、维度、时间字段和图表表达方式。"
    if step == STEP_REVIEW:
        gaps = extra.get("gaps") or []
        if gaps:
            return f"{prefix}完成问题审视，发现 {len(gaps)} 个覆盖缺口，已补充更能支撑决策的规模、趋势、结构或异常类问题。"
        return f"{prefix}完成问题审视：口径可量化、字段可落地、图表意图清晰，暂不需要补题。"
    if step == STEP_BLUEPRINT_COMPLETE:
        role_count = extra.get("role_count")
        warning_count = extra.get("warning_count")
        detail = []
        if role_count is not None:
            detail.append(f"{role_count} 个有效角色")
        if warning_count is not None:
            detail.append(f"{warning_count} 条覆盖提醒")
        suffix = f"（{ '，'.join(detail) }）" if detail else ""
        return f"{prefix}蓝图组装完成{suffix}，进入 SQL 与图表契约生成阶段。"
    if step == STEP_BLUEPRINT_FAILED:
        return f"{prefix}蓝图某步未能完成：{message}"
    if step == STEP_COMPILE_SQL or step == STEP_CHART_DRAFT:
        chart_type = extra.get("chart_type")
        note = extra.get("calculation_note")
        if chart_type:
            suffix = f"计算口径：{note}" if note else "同时完成只读 SQL 安全检查、字段别名检查和前端渲染契约绑定。"
            return f"{prefix}基于问题、表理解和字段样例生成单题 SQL，图表契约判定为「{chart_type}」。{suffix}"
        return f"{prefix}将问题编译为指标口径、只读 SQL 与图表契约，优先让图表类型服从业务意图。"
    if step == STEP_SQL_PREVIEW:
        row_count = extra.get("row_count")
        columns = extra.get("columns") or []
        if row_count is not None:
            col_text = "、".join(str(c) for c in columns[:4])
            return f"{prefix}SQL 预执行通过，返回 {row_count} 行样例数据，字段「{col_text}」可直接供前端渲染。"
        return f"{prefix}预执行 SQL，校验结果非空、字段别名友好，并确认结果结构匹配当前图表类型。"
    if step == STEP_REPAIR:
        action = extra.get("repair_action")
        reason = extra.get("diagnosis_reason")
        if action:
            return f"{prefix}预览诊断后执行一次自动修复，动作={action}。{reason or '修复目标是让 SQL、指标口径和图表契约重新对齐。'}"
        return f"{prefix}预览结果未达标，正在诊断字段、聚合口径和图表契约，只执行一次受控修复。"
    if step == STEP_CHART_DROPPED:
        failure_type = extra.get("failure_type")
        reason = extra.get("error_message") or extra.get("reason")
        return f"{prefix}该候选图未通过校验，已从看板中剔除，原因={failure_type or '未知'}。{reason or ''}".strip()
    if step == STEP_GENERATE_END:
        count = extra.get("chart_count")
        dropped = extra.get("charts_dropped_count")
        if count is not None:
            suffix = f"，剔除 {dropped} 张未达标候选图" if dropped is not None else ""
            return f"看板生成完成，共纳入 {count} 张可预览图表{suffix}，配置正在同步保存。"
        return "看板生成完成，正在保存配置。"
    if level.upper() == "ERROR":
        return f"{prefix}遇到问题：{message}"
    if level.upper() == "WARN":
        return f"{prefix}{message}"
    if message:
        return f"{prefix}{message}" if prefix else message
    return prefix or "继续处理中…"


def make_journal_entry(
    step: str,
    message: str,
    *,
    run_id: Optional[str] = None,
    level: str = "INFO",
    sheet_name: Optional[str] = None,
    table_name: Optional[str] = None,
    role_name: Optional[str] = None,
    scenario_name: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    text = step_to_natural_language(
        step,
        message,
        level=level,
        sheet_name=sheet_name,
        table_name=table_name,
        role_name=role_name,
        scenario_name=scenario_name,
        extra=extra,
    )
    return {
        "id": uuid.uuid4().hex[:12],
        "ts": datetime.now().isoformat(timespec="seconds"),
        "step": step,
        "level": level.upper(),
        "text": text,
        "run_id": run_id,
        "sheet_name": sheet_name,
        "table_name": table_name,
        "role_name": role_name,
        "scenario_name": scenario_name,
    }


class BIThinkingJournal:
    """单次生成 run 的思考记录，可序列化入库。"""

    def __init__(self, file_id: str, run_id: str):
        self.file_id = file_id
        self.run_id = run_id
        self.entries: List[Dict[str, Any]] = []

    def append(
        self,
        step: str,
        message: str,
        *,
        level: str = "INFO",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        entry = make_journal_entry(
            step,
            message,
            run_id=self.run_id,
            level=level,
            **kwargs,
        )
        self.entries.append(entry)
        return entry

    def to_list(self) -> List[Dict[str, Any]]:
        return list(self.entries)

    @staticmethod
    def from_list(file_id: str, run_id: str, data: Optional[List[Any]]) -> BIThinkingJournal:
        journal = BIThinkingJournal(file_id, run_id)
        if isinstance(data, list):
            journal.entries = [e for e in data if isinstance(e, dict) and e.get("text")]
        return journal

    def search(self, query: str) -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        if not q:
            return self.entries
        out = []
        for e in self.entries:
            blob = " ".join(
                str(x or "")
                for x in (
                    e.get("text"),
                    e.get("step"),
                    e.get("sheet_name"),
                    e.get("table_name"),
                    e.get("role_name"),
                    e.get("scenario_name"),
                )
            ).lower()
            if q in blob:
                out.append(e)
        return out
