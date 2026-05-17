import uuid
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
