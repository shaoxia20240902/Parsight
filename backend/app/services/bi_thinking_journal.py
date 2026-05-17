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

    if step == STEP_GENERATE_START:
        return "开始阅读你的工作簿，准备搭建 BI 看板。"
    if step == STEP_UNDERSTANDING_GATE:
        return "检查各表是否已完成六维业务理解。"
    if step == STEP_INDUSTRY:
        industry = (extra or {}).get("industry_guess") or {}
        primary = industry.get("primary") or industry.get("industry") or "业务"
        return f"根据表结构与理解内容，推断整体行业语境为「{primary}」。"
    if step == STEP_SHEET_PIPELINE:
        return f"{prefix}启动该 Sheet 的分析流水线。"
    if step == STEP_ROLE_PICKER:
        if "选角完成" in message or "个角色" in message:
            n = (extra or {}).get("perspective_ids") or []
            count = len(n) if n else message
            return f"{prefix}选定 {len(n) if isinstance(n, list) else ''} 个业务视角，从不同角色出发提问。".replace("  ", " ")
        return f"{prefix}为这张表挑选合适的业务角色。"
    if step == STEP_SCENARIOS:
        return f"{prefix}为当前角色构思分析场景。"
    if step == STEP_QUESTIONS:
        return f"{prefix}把场景落实为可回答的业务问题。"
    if step == STEP_REVIEW:
        return f"{prefix}审视问题是否清晰、可量化，并做取舍。"
    if step == STEP_BLUEPRINT_COMPLETE:
        return f"{prefix}蓝图组装完成，准备生成图表。"
    if step == STEP_BLUEPRINT_FAILED:
        return f"{prefix}蓝图某步未能完成：{message}"
    if step == STEP_COMPILE_SQL or step == STEP_CHART_DRAFT:
        return f"{prefix}将问题编译为指标与 SQL，并选定图表类型。"
    if step == STEP_SQL_PREVIEW:
        return f"{prefix}试跑 SQL，确认能返回有效数据。"
    if step == STEP_REPAIR:
        return f"{prefix}结果不理想，尝试修复 SQL 或图表配置（仅一次）。"
    if step == STEP_CHART_DROPPED:
        return f"{prefix}该图未能通过校验，已从看板候选中移除。"
    if step == STEP_GENERATE_END:
        count = (extra or {}).get("chart_count")
        if count is not None:
            return f"看板生成完成，共纳入 {count} 张图表。"
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
