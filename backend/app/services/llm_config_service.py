import uuid
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_config import LLMConfig
logger = logging.getLogger(__name__)


class LLMConfigService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_configs(self) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(LLMConfig).order_by(LLMConfig.created_at.desc())
        )
        rows = result.scalars().all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "api_base": c.api_base,
                "api_key": self._mask_key(c.api_key),
                "primary_model": c.primary_model,
                "alt_model": c.alt_model,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else "",
                "updated_at": c.updated_at.isoformat() if c.updated_at else "",
            }
            for c in rows
        ]

    async def get_active_config(self) -> Optional[Dict[str, Any]]:
        result = await self.db.execute(
            select(LLMConfig).where(LLMConfig.is_active == True).limit(1)
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {
            "id": row.id,
            "name": row.name,
            "api_base": row.api_base,
            "api_key": row.api_key,
            "primary_model": row.primary_model,
            "alt_model": row.alt_model,
            "is_active": row.is_active,
        }

    async def create_config(
        self,
        name: str,
        api_base: str,
        api_key: str,
        primary_model: str,
        alt_model: Optional[str] = None,
        is_active: bool = False,
    ) -> Dict[str, Any]:
        config = LLMConfig(
            id=str(uuid.uuid4()),
            name=name,
            api_base=api_base,
            api_key=api_key,
            primary_model=primary_model,
            alt_model=alt_model,
            is_active=is_active,
        )
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return {
            "id": config.id,
            "name": config.name,
            "api_base": config.api_base,
            "api_key": self._mask_key(config.api_key),
            "primary_model": config.primary_model,
            "alt_model": config.alt_model,
            "is_active": config.is_active,
        }

    async def update_config(
        self,
        config_id: str,
        **fields: Any,
    ) -> Optional[Dict[str, Any]]:
        result = await self.db.execute(
            select(LLMConfig).where(LLMConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            return None

        allowed = {"name", "api_base", "api_key", "primary_model", "alt_model", "is_active"}
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(config, k, v)

        await self.db.commit()
        await self.db.refresh(config)
        return {
            "id": config.id,
            "name": config.name,
            "api_base": config.api_base,
            "api_key": self._mask_key(config.api_key),
            "primary_model": config.primary_model,
            "alt_model": config.alt_model,
            "is_active": config.is_active,
        }

    async def delete_config(self, config_id: str) -> bool:
        result = await self.db.execute(
            select(LLMConfig).where(LLMConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            return False
        await self.db.delete(config)
        await self.db.commit()
        return True

    async def set_active(self, config_id: str) -> bool:
        # 先取消所有活跃配置
        await self.db.execute(
            text("UPDATE llm_configs SET is_active = FALSE")
        )
        # 设置指定配置为活跃
        result = await self.db.execute(
            text("UPDATE llm_configs SET is_active = TRUE WHERE id = :id"),
            {"id": config_id},
        )
        await self.db.commit()
        return result.rowcount > 0

    async def ensure_default_config(self) -> None:
        """检查是否存在 LLM 配置记录（不自动从环境变量写入，避免运行时兜底）。"""
        result = await self.db.execute(select(LLMConfig).limit(1))
        if result.scalar_one_or_none():
            return
        logger.warning(
            "数据库中尚无 LLM 配置，请在管理后台「LLM 配置」中创建并启用后再调用 AI 能力"
        )

    def _mask_key(self, key: str) -> str:
        if not key:
            return ""
        if len(key) <= 12:
            return "*" * len(key)
        return key[:6] + "****" + key[-6:]
