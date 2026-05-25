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
from app.services.llm_config_service import LLMConfigService
from app.services.llm_client import set_llm_config
from app.services.db_service import DBService

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
                    text(f"DROP TABLE IF EXISTS `{meta.table_name}`")
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


# ========== LLM 配置管理 ==========


def _assert_llm_config_complete(
    *,
    api_base: str,
    api_key: str,
    primary_model: str,
    alt_model: Optional[str],
) -> None:
    if not (api_base or "").strip():
        raise HTTPException(status_code=400, detail="api_base 不能为空")
    if not (api_key or "").strip():
        raise HTTPException(status_code=400, detail="api_key 不能为空")
    if not (primary_model or "").strip():
        raise HTTPException(status_code=400, detail="primary_model 不能为空")
    if not (alt_model or "").strip():
        raise HTTPException(status_code=400, detail="alt_model 不能为空（运行时主/备模型均来自管理端）")


def _apply_active_llm_config(active: Optional[dict]) -> dict:
    if not active:
        raise HTTPException(status_code=400, detail="没有可启用的 LLM 配置")
    _assert_llm_config_complete(
        api_base=active["api_base"],
        api_key=active["api_key"],
        primary_model=active["primary_model"],
        alt_model=active.get("alt_model"),
    )
    set_llm_config(active)
    return active


class LLMConfigCreateRequest(BaseModel):
    name: str
    api_base: str
    api_key: str
    primary_model: str
    alt_model: str = ""
    is_active: bool = False


class LLMConfigUpdateRequest(BaseModel):
    name: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    primary_model: Optional[str] = None
    alt_model: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/llm-configs")
async def list_llm_configs(
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有 LLM 配置列表"""
    service = LLMConfigService(db)
    configs = await service.list_configs()
    return {"code": 200, "data": configs}


@router.post("/llm-configs")
async def create_llm_config(
    req: LLMConfigCreateRequest,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """创建 LLM 配置"""
    _assert_llm_config_complete(
        api_base=req.api_base,
        api_key=req.api_key,
        primary_model=req.primary_model,
        alt_model=req.alt_model,
    )
    service = LLMConfigService(db)
    config = await service.create_config(
        name=req.name,
        api_base=req.api_base,
        api_key=req.api_key,
        primary_model=req.primary_model,
        alt_model=req.alt_model or None,
        is_active=req.is_active,
    )
    if req.is_active:
        active = await service.get_active_config()
        _apply_active_llm_config(active)
    return {"code": 200, "data": config}


@router.put("/llm-configs/{config_id}")
async def update_llm_config(
    config_id: str,
    req: LLMConfigUpdateRequest,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 LLM 配置"""
    service = LLMConfigService(db)
    config = await service.update_config(
        config_id,
        name=req.name,
        api_base=req.api_base,
        api_key=req.api_key,
        primary_model=req.primary_model,
        alt_model=req.alt_model,
        is_active=req.is_active,
    )
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    if req.is_active:
        active = await service.get_active_config()
        _apply_active_llm_config(active)
    return {"code": 200, "data": config}


@router.delete("/llm-configs/{config_id}")
async def delete_llm_config(
    config_id: str,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除 LLM 配置"""
    service = LLMConfigService(db)
    ok = await service.delete_config(config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="配置不存在")
    active = await service.get_active_config()
    if active:
        _apply_active_llm_config(active)
    else:
        set_llm_config(None)
    return {"code": 200, "message": "配置已删除"}


@router.post("/llm-configs/{config_id}/activate")
async def activate_llm_config(
    config_id: str,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """设为当前启用的 LLM 配置"""
    service = LLMConfigService(db)
    ok = await service.set_active(config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="配置不存在")
    active = await service.get_active_config()
    return {"code": 200, "data": _apply_active_llm_config(active)}


class LLMConfigTestRequest(BaseModel):
    api_base: str
    api_key: str
    primary_model: str


@router.post("/llm-configs/test")
async def test_llm_config(
    req: LLMConfigTestRequest,
    _admin: User = Depends(get_current_admin_user),
):
    """测试 LLM 配置连通性"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
            response = await client.post(
                f"{req.api_base.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {req.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": req.primary_model,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 5,
                },
            )
            response.raise_for_status()
            data = response.json()
            return {
                "code": 200,
                "data": {
                    "success": True,
                    "model": data.get("model", req.primary_model),
                },
            }
    except Exception as e:
        return {
            "code": 200,
            "data": {
                "success": False,
                "error": str(e),
            },
        }


# ========== 空间管理 ==========

class CreateSpaceRequest(BaseModel):
    name: str
    owner_id: str
    code: Optional[str] = None
    description: Optional[str] = None


class UpdateSpaceRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("/spaces")
async def list_spaces(
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有空间列表"""
    result = await db.execute(
        select(Space, User.username)
        .join(User, Space.owner_id == User.id)
        .order_by(Space.created_at.desc())
    )
    rows = result.all()
    return {
        "code": 200,
        "data": [
            {
                "id": space.id,
                "name": space.name,
                "code": space.code,
                "description": space.description or "",
                "owner_id": space.owner_id,
                "owner_name": username,
                "is_active": space.is_active,
                "created_at": space.created_at.isoformat() if space.created_at else "",
            }
            for space, username in rows
        ]
    }


@router.post("/spaces")
async def create_space(
    req: CreateSpaceRequest,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """创建空间（管理员可指定任意用户为拥有者）"""
    # 检查用户是否存在
    user_result = await db.execute(select(User).where(User.id == req.owner_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="指定的用户不存在")

    # 生成唯一 code
    code = req.code or f"space_{req.owner_id[:8]}_{uuid.uuid4().hex[:6]}"
    code_result = await db.execute(select(Space).where(Space.code == code))
    if code_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="空间代码已存在")

    db_service = DBService(db)
    seq_id = await db_service.get_next_space_seq_id()
    space = Space(
        id=str(uuid.uuid4()),
        seq_id=seq_id,
        name=req.name,
        code=code,
        description=req.description or "",
        owner_id=req.owner_id,
        is_active=True,
    )
    db.add(space)
    await db.commit()
    await db.refresh(space)
    return {
        "code": 200,
        "data": {
            "id": space.id,
            "name": space.name,
            "code": space.code,
            "owner_id": space.owner_id,
        }
    }


@router.put("/spaces/{space_id}")
async def update_space(
    space_id: str,
    req: UpdateSpaceRequest,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑空间名称和描述"""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail="空间不存在")

    if req.name is not None:
        space.name = req.name
    if req.description is not None:
        space.description = req.description

    await db.commit()
    await db.refresh(space)
    return {
        "code": 200,
        "data": {
            "id": space.id,
            "name": space.name,
            "description": space.description,
        }
    }


@router.delete("/spaces/{space_id}")
async def delete_space(
    space_id: str,
    _admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除空间及其全部数据（级联删除）"""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail="空间不存在")

    await _delete_space_data(db, space_id)
    await db.delete(space)
    await db.commit()
    return {"code": 200, "message": f"空间「{space.name}」已删除"}
