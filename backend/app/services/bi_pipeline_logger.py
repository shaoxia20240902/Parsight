"""
BI 生成流水线专用本地日志 — 写入 backend/logs/bi_pipeline.log

开发阶段用于排查：哪一步、哪张表、哪个角色/场景/问题出错。
与 ai_calls.log（LLM 请求全文）分离，本日志只记录流水线事件与错误摘要。
"""

from __future__ import annotations

import json
import logging
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

_BI_PIPELINE_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "logs" / "bi_pipeline.log"
_SEPARATOR = "═" * 72
_THIN = "─" * 72

# 流水线步骤常量（写入日志便于 grep）
STEP_GENERATE_START = "generate_start"
STEP_GENERATE_END = "generate_end"
STEP_UNDERSTANDING_GATE = "understanding_gate"
STEP_INDUSTRY = "industry_inference"
STEP_ROLE_PICKER = "role_picker"
STEP_SCENARIOS = "scenarios"
STEP_QUESTIONS = "questions"
STEP_REVIEW = "review"
STEP_BLUEPRINT_COMPLETE = "blueprint_complete"
STEP_BLUEPRINT_FAILED = "blueprint_failed"
STEP_COMPILE_SQL = "compile_sql"
STEP_CHART_DRAFT = "chart_draft"
STEP_SQL_PREVIEW = "sql_preview"
STEP_REPAIR = "repair"
STEP_CHART_DROPPED = "chart_dropped"
STEP_SHEET_PIPELINE = "sheet_pipeline"


def _init_logger() -> logging.Logger:
    lg = logging.getLogger("bi_pipeline")
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    if not lg.handlers:
        _BI_PIPELINE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(_BI_PIPELINE_LOG_PATH), encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(message)s"))
        lg.addHandler(handler)
    return lg


_bi_log = _init_logger()


class BIPipelineRunContext:
    """单次 BI 生成 run 的关联 ID，贯穿日志便于串联排查。"""

    def __init__(self, file_id: str, journal: Any = None):
        self.file_id = file_id
        self.run_id = uuid.uuid4().hex[:12]
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.journal = journal
        self.persist_journal_entry = None  # optional async callback(entry)

    def base(self) -> Dict[str, Any]:
        return {"run_id": self.run_id, "file_id": self.file_id}


def log_bi_event(
    level: str,
    step: str,
    message: str,
    *,
    run_ctx: Optional[BIPipelineRunContext] = None,
    skip_journal: bool = False,
    table_name: Optional[str] = None,
    sheet_name: Optional[str] = None,
    perspective_id: Optional[str] = None,
    role_name: Optional[str] = None,
    scenario_id: Optional[str] = None,
    scenario_name: Optional[str] = None,
    question_id: Optional[str] = None,
    chart_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    exc: Optional[BaseException] = None,
) -> None:
    """写入一条结构化流水线日志。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = {
        "time": ts,
        "level": level.upper(),
        "step": step,
        "message": message,
    }
    if run_ctx:
        header.update(run_ctx.base())
    loc = {
        k: v
        for k, v in {
            "table_name": table_name,
            "sheet_name": sheet_name,
            "perspective_id": perspective_id,
            "role_name": role_name,
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "question_id": question_id,
            "chart_id": chart_id,
        }.items()
        if v is not None
    }
    lines = [
        "",
        _SEPARATOR,
        f"  [{header['level']}] {ts}  |  step={step}  |  run_id={header.get('run_id', '-')}",
        f"  file_id={header.get('file_id', '-')}  |  {message}",
    ]
    if loc:
        lines.append(f"  位置: {json.dumps(loc, ensure_ascii=False)}")
    if extra:
        lines.append("  详情:")
        for k, v in extra.items():
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                try:
                    v_str = json.dumps(v, ensure_ascii=False, default=str)
                    if len(v_str) > 2000:
                        v_str = v_str[:2000] + "…(truncated)"
                except TypeError:
                    v_str = str(v)
            else:
                v_str = str(v)
            lines.append(f"    {k}: {v_str}")
    if exc is not None:
        lines.append(_THIN)
        lines.append(f"  异常: {type(exc).__name__}: {exc}")
        tb = traceback.format_exc()
        if tb and tb.strip() != "NoneType: None":
            lines.append("  Traceback:")
            for line in tb.strip().splitlines():
                lines.append(f"    {line}")
    lines.append(_SEPARATOR)
    text = "\n".join(lines)

    if run_ctx and not skip_journal:
        journal = getattr(run_ctx, "journal", None)
        if journal is not None:
            from app.services.bi_thinking_journal import make_journal_entry

            entry = make_journal_entry(
                step,
                message,
                run_id=run_ctx.run_id,
                level=level,
                sheet_name=sheet_name,
                table_name=table_name,
                role_name=role_name,
                scenario_name=scenario_name,
                extra=extra,
            )
            journal.entries.append(entry)
            persist = getattr(run_ctx, "persist_journal_entry", None)
            if callable(persist):
                try:
                    persist(entry)
                except Exception:
                    pass

    if level.upper() == "ERROR":
        _bi_log.error(text)
    elif level.upper() == "WARN":
        _bi_log.warning(text)
    else:
        _bi_log.info(text)


def log_step_ok(
    step: str,
    message: str,
    run_ctx: Optional[BIPipelineRunContext] = None,
    **kwargs: Any,
) -> None:
    log_bi_event("INFO", step, message, run_ctx=run_ctx, **kwargs)


def log_step_warn(
    step: str,
    message: str,
    run_ctx: Optional[BIPipelineRunContext] = None,
    exc: Optional[BaseException] = None,
    **kwargs: Any,
) -> None:
    log_bi_event("WARN", step, message, run_ctx=run_ctx, exc=exc, **kwargs)


def log_step_error(
    step: str,
    message: str,
    run_ctx: Optional[BIPipelineRunContext] = None,
    exc: Optional[BaseException] = None,
    **kwargs: Any,
) -> None:
    log_bi_event("ERROR", step, message, run_ctx=run_ctx, exc=exc, **kwargs)
