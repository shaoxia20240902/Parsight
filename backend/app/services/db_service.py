from sqlalchemy.ext.asyncio import AsyncSession

from app.services.db.mixins import (
    BIMixin,
    FileMixin,
    KnowledgeMixin,
    RelationsMixin,
    TableMixin,
    UnderstandingMixin,
)
from app.services.db.utils import json_default, json_safe


class DBService(
    FileMixin,
    TableMixin,
    BIMixin,
    KnowledgeMixin,
    UnderstandingMixin,
    RelationsMixin,
):
    """数据库服务：由多个职责单一的数据访问 mixin 组合而成。"""

    def __init__(self, db: AsyncSession):
        self.db = db


__all__ = ["DBService", "json_default", "json_safe"]
