import uuid
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from passlib.hash import pbkdf2_sha256
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from app.models.database import get_db
from app.models.user import User
from app.models.space import Space
from app.models.file_record import FileRecord
from app.models.sheet_meta import SheetMeta
from app.models.chat_history import ChatHistory
from app.routers.auth import get_current_admin_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

LOG_ROOT = Path(__file__).resolve().parent.parent.parent / "logs"
BI_PIPELINE_LOG = LOG_ROOT / "bi_pipeline.log"

LOG_SOURCE_META = {
    "bi": {
        "key": "bi",
        "name": "BI 看板生成",
        "description": "BI 蓝图、SQL、图表预览、修复和剔除日志",
        "enabled": True,
    },
    "qa": {
        "key": "qa",
        "name": "问答日志",
        "description": "预留：后续接入问答链路、SQL 和工具调用日志",
        "enabled": False,
    },
}


class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class UserInfo(BaseModel):
    id: str
    username: str
    display_name: str
    is_admin: bool
    created_at: str


def _read_recent_lines(path: Path, max_lines: int = 5000) -> List[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    return lines[-max_lines:]


def _parse_bi_log_entries(max_lines: int = 5000) -> List[Dict[str, Any]]:
    lines = _read_recent_lines(BI_PIPELINE_LOG, max_lines=max_lines)
    entries: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    extra_key: Optional[str] = None
    header_re = re.compile(
        r"\[(?P<level>\w+)\]\s+(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+\|\s+step=(?P<step>[^|]+)\|\s+run_id=(?P<run_id>\S+)"
    )
    file_re = re.compile(r"file_id=(?P<file_id>\S+)\s+\|\s+(?P<message>.*)")

    def finish() -> None:
        nonlocal current
        if current:
            entries.append(current)
            current = None

    for raw in lines:
        line = raw.rstrip("\n")
        header = header_re.search(line)
        if header:
            finish()
            current = {
                "time": header.group("time"),
                "level": header.group("level"),
                "step": header.group("step").strip(),
                "run_id": header.group("run_id"),
                "file_id": "",
                "message": "",
                "location": {},
                "extra": {},
            }
            extra_key = None
            continue
        if not current:
            continue
        stripped = line.strip()
        if stripped.startswith("file_id="):
            m = file_re.search(stripped)
            if m:
                current["file_id"] = m.group("file_id")
                current["message"] = m.group("message")
            continue
        if stripped.startswith("位置:"):
            raw_loc = stripped.replace("位置:", "", 1).strip()
            try:
                current["location"] = json.loads(raw_loc)
            except json.JSONDecodeError:
                current["location"] = {"raw": raw_loc}
            continue
        if stripped == "详情:":
            extra_key = ""
            continue
        if stripped.startswith("异常:"):
            current["exception"] = stripped.replace("异常:", "", 1).strip()
            extra_key = None
            continue
        if line.startswith("    ") and extra_key is not None:
            item = stripped
            if ": " in item:
                key, value = item.split(": ", 1)
                current["extra"][key] = value
                extra_key = key
            elif extra_key:
                current["extra"][extra_key] = f"{current['extra'].get(extra_key, '')}\n{item}".strip()

    finish()
    return entries


def _summarize_bi_runs(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        run_id = entry.get("run_id")
        if run_id and run_id != "-":
            grouped[run_id].append(entry)

    runs = []
    for run_id, items in grouped.items():
        items.sort(key=lambda x: x.get("time") or "")
        levels = defaultdict(int)
        steps = set()
        file_id = ""
        chart_count = None
        dropped_count = None
        for item in items:
            levels[item.get("level", "INFO")] += 1
            steps.add(item.get("step"))
            file_id = item.get("file_id") or file_id
            if item.get("step") == "generate_end":
                extra = item.get("extra") or {}
                chart_count = extra.get("chart_count")
                dropped_count = extra.get("charts_dropped_count")
        if file_id == "test":
            continue
        last = items[-1]
        status = "completed" if any(i.get("step") == "generate_end" for i in items) else "running_or_interrupted"
        if levels.get("ERROR"):
            status = "failed"
        runs.append({
            "run_id": run_id,
            "file_id": file_id,
            "started_at": items[0].get("time"),
            "updated_at": last.get("time"),
            "status": status,
            "entry_count": len(items),
            "step_count": len(steps),
            "error_count": levels.get("ERROR", 0),
            "warn_count": levels.get("WARN", 0),
            "chart_count": chart_count,
            "dropped_count": dropped_count,
            "last_step": last.get("step"),
            "last_message": last.get("message"),
        })
    runs.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return runs


@router.get("/users")
async def list_users(
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取所有用户列表（仅管理员）"""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return {
        "code": 200,
        "data": [
            {
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name or "",
                "is_admin": u.is_admin or False,
                "created_at": u.created_at.isoformat() if u.created_at else ""
            }
            for u in users
        ]
    }


@router.get("/logs/sources")
async def list_log_sources(
    _admin: User = Depends(get_current_admin_user),
):
    """日志中心来源列表。先开放 BI，问答等链路预留。"""
    return {"code": 200, "data": list(LOG_SOURCE_META.values())}


@router.get("/logs/bi/runs")
async def list_bi_log_runs(
    limit: int = 50,
    _admin: User = Depends(get_current_admin_user),
):
    """按 run_id 汇总 BI 生成日志。"""
    entries = _parse_bi_log_entries()
    runs = _summarize_bi_runs(entries)
    safe_limit = max(1, min(limit, 200))
    return {"code": 200, "data": runs[:safe_limit]}


@router.get("/logs/bi/runs/{run_id}")
async def get_bi_log_run(
    run_id: str,
    _admin: User = Depends(get_current_admin_user),
):
    """查看单次 BI 生成的完整流水线日志。"""
    entries = [e for e in _parse_bi_log_entries(max_lines=12000) if e.get("run_id") == run_id]
    if not entries:
        raise HTTPException(status_code=404, detail="未找到该 BI 生成日志")
    entries.sort(key=lambda x: x.get("time") or "")
    summary = _summarize_bi_runs(entries)[0]
    return {"code": 200, "data": {"summary": summary, "entries": entries}}


@router.post("/users")
async def create_user(
    req: CreateUserRequest,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """创建用户并自动创建默认空间（仅管理员）"""
    # 检查用户名唯一
    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建用户
    user = User(
        id=str(uuid.uuid4()),
        username=req.username,
        hashed_password=pbkdf2_sha256.hash(req.password),
        display_name=req.display_name or req.username,
        is_admin=False
    )
    db.add(user)
    await db.flush()  # 获取user.id

    # 为用户自动创建默认空间
    default_space = Space(
        id=str(uuid.uuid4()),
        name="默认空间",
        code=f"default_{user.username}",
        description="系统自动创建的默认空间",
        owner_id=user.id,
        is_active=True
    )
    db.add(default_space)
    await db.commit()
    await db.refresh(user)

    return {
        "code": 200,
        "data": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name or "",
            "is_admin": False,
            "created_at": user.created_at.isoformat() if user.created_at else "",
            "default_space_id": default_space.id
        }
    }


async def _delete_space_data(db: AsyncSession, space_id: str) -> None:
    """删除空间下聊天、文件、动态表及 sheet 元数据"""
    files_result = await db.execute(
        select(FileRecord).where(FileRecord.space_id == space_id)
    )
    files = files_result.scalars().all()
    for file_rec in files:
        metas_result = await db.execute(
            select(SheetMeta).where(SheetMeta.file_id == file_rec.id)
        )
        for meta in metas_result.scalars().all():
            if meta.table_name:
                await db.execute(
                    text(f'DROP TABLE IF EXISTS "{meta.table_name}"')
                )
        await db.execute(delete(SheetMeta).where(SheetMeta.file_id == file_rec.id))

    await db.execute(delete(ChatHistory).where(ChatHistory.space_id == space_id))
    await db.execute(delete(FileRecord).where(FileRecord.space_id == space_id))


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除用户及其空间、文件、动态表（仅管理员；不可删自己或其他管理员）"""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    if target.is_admin:
        raise HTTPException(status_code=400, detail="不能删除管理员账号")

    spaces_result = await db.execute(select(Space).where(Space.owner_id == user_id))
    spaces = spaces_result.scalars().all()
    for space in spaces:
        await _delete_space_data(db, space.id)
        await db.delete(space)

    await db.delete(target)
    await db.commit()

    return {"code": 200, "message": f"用户「{target.username}」已删除"}
