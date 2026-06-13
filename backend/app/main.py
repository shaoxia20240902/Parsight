import logging
import secrets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select
from passlib.hash import pbkdf2_sha256
from app.models.database import init_db, async_session
from app.models.user import User
from app.models.space import Space
from app.models.chat_history import ChatHistory
from app.routers import upload_router, chat_router, health_router, data_router, auth_router, space_router, admin_router, understanding_router, relations_router, bi_router
from app.config import ADMIN_INITIAL_PASSWORD, CORS_ALLOW_ORIGINS
from app.utils.task_manager import task_manager

logger = logging.getLogger(__name__)


def _generate_initial_password() -> str:
    """生成可读的一次性初始密码（12 位，包含字母和数字）。"""
    return secrets.token_urlsafe(9)


async def seed_admin():
    """初始化管理员账号"""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            password = ADMIN_INITIAL_PASSWORD or _generate_initial_password()
            admin = User(
                username="admin",
                hashed_password=pbkdf2_sha256.hash(password),
                display_name="管理员",
                is_admin=True,
            )
            db.add(admin)
            await db.commit()
            if ADMIN_INITIAL_PASSWORD:
                logger.info("管理员账号已创建: admin / 使用 ADMIN_INITIAL_PASSWORD 环境变量设置的密码")
            else:
                logger.warning(
                    "管理员账号已创建: admin / %s 。"
                    "请立即登录并修改密码，或在 .env 中设置 ADMIN_INITIAL_PASSWORD 以固定密码。",
                    password,
                )
        else:
            logger.info("管理员账号已存在，跳过创建")


async def seed_llm_config():
    """初始化默认 LLM 配置"""
    from app.services.llm_config_service import LLMConfigService
    from app.services.llm_client import set_llm_config
    async with async_session() as db:
        service = LLMConfigService(db)
        await service.ensure_default_config()
        active = await service.get_active_config()
        if active:
            from app.services.llm_client import require_active_llm_config, get_alt_model

            set_llm_config(active)
            require_active_llm_config()
            alt = get_alt_model()
            logger.info(
                "LLM 配置已加载: %s | %s | 主模型 %s | 备用 %s",
                active["name"], active["api_base"], active["primary_model"], alt
            )
        else:
            logger.warning("未找到已启用的 LLM 配置，所有 AI 调用将失败直至在管理端启用一条配置")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    logger.info("数据库初始化完成")
    # 种子数据：管理员账号
    await seed_admin()
    # 种子数据：默认 LLM 配置
    await seed_llm_config()
    yield
    # 关闭时清理资源
    await task_manager.shutdown(timeout=5.0)
    logger.info("应用关闭")


app = FastAPI(
    title="XLSX to BI 智能看板",
    description="上传Excel文件，AI自动分析生成BI看板",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health_router)
app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(data_router)
app.include_router(auth_router)
app.include_router(space_router)
app.include_router(admin_router)
app.include_router(understanding_router)
app.include_router(relations_router)
app.include_router(bi_router)


@app.get("/")
async def root():
    return {
        "service": "XLSX to BI 智能看板",
        "version": "1.0.0",
        "docs": "/docs"
    }
