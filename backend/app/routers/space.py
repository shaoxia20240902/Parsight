import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from app.models.database import get_db
from app.models.space import Space
from app.models.file_record import FileRecord
from app.models.chat_history import ChatHistory
from app.routers.auth import get_current_user
from app.models.user import User
from app.services.db_service import DBService

router = APIRouter(prefix="/api/spaces", tags=["spaces"])

MAX_SPACES_PER_USER = 5


class CreateSpaceRequest(BaseModel):
    name: str
    code: str
    description: str = ""


class SpaceResponse(BaseModel):
    id: str
    seq_id: int
    name: str
    code: str
    description: str
    is_active: bool
    created_at: str


@router.get("")
async def list_spaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的空间列表"""
    result = await db.execute(
        select(Space).where(Space.owner_id == user.id).order_by(Space.created_at)
    )
    spaces = result.scalars().all()
    return {
        "code": 200,
        "data": [
            {
                "id": s.id,
                "seq_id": s.seq_id,
                "name": s.name,
                "code": s.code,
                "description": s.description or "",
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else ""
            }
            for s in spaces
        ]
    }


@router.post("")
async def create_space(
    req: CreateSpaceRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建空间（最多5个）"""
    # 检查数量上限
    result = await db.execute(
        select(Space).where(Space.owner_id == user.id)
    )
    existing = result.scalars().all()
    if len(existing) >= MAX_SPACES_PER_USER:
        raise HTTPException(status_code=400, detail=f"最多创建 {MAX_SPACES_PER_USER} 个空间")

    # 检查code唯一性
    result = await db.execute(select(Space).where(Space.code == req.code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="空间编码已存在")

    db_service = DBService(db)
    seq_id = await db_service.get_next_space_seq_id()
    space = Space(
        id=str(uuid.uuid4()),
        seq_id=seq_id,
        name=req.name,
        code=req.code,
        description=req.description,
        owner_id=user.id,
        is_active=True
    )
    db.add(space)
    await db.commit()
    await db.refresh(space)

    return {
        "code": 200,
        "data": {
            "id": space.id,
            "seq_id": space.seq_id,
            "name": space.name,
            "code": space.code,
            "description": space.description or "",
            "is_active": space.is_active,
            "created_at": space.created_at.isoformat() if space.created_at else ""
        }
    }


@router.delete("/{space_id}")
async def delete_space(
    space_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除空间（级联删除关联数据）"""
    result = await db.execute(
        select(Space).where(Space.id == space_id, Space.owner_id == user.id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail="空间不存在")

    # 级联删除：先删聊天记录，再删文件记录
    await db.execute(delete(ChatHistory).where(ChatHistory.space_id == space_id))
    await db.execute(delete(FileRecord).where(FileRecord.space_id == space_id))
    await db.delete(space)
    await db.commit()

    return {"code": 200, "message": "空间已删除"}


@router.put("/{space_id}/active")
async def set_active_space(
    space_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """切换当前活跃空间"""
    result = await db.execute(
        select(Space).where(Space.id == space_id, Space.owner_id == user.id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail="空间不存在")

    # 将所有空间设为非活跃
    await db.execute(
        update(Space).where(Space.owner_id == user.id).values(is_active=False)
    )
    space.is_active = True
    await db.commit()

    return {"code": 200, "message": "空间切换成功", "data": {"active_space_id": space.id}}
