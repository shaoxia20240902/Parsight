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


async def seed_admin():
    """初始化管理员账号"""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            admin = User(
                username="admin",
                hashed_password=pbkdf2_sha256.hash("123456"),
                display_name="管理员",
                is_admin=True,
            )
            db.add(admin)
            await db.commit()
            print("管理员账号已创建: admin / 123456")
        else:
            print("管理员账号已存在，跳过创建")


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
            print(
                f"LLM 配置已加载: {active['name']} | "
                f"{active['api_base']} | 主模型 {active['primary_model']} | 备用 {alt}"
            )
        else:
            print("警告: 未找到已启用的 LLM 配置，所有 AI 调用将失败直至在管理端启用一条配置")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    print("数据库初始化完成")
    # 种子数据：管理员账号
    await seed_admin()
    # 种子数据：默认 LLM 配置
    await seed_llm_config()
    yield
    # 关闭时清理资源
    print("应用关闭")


app = FastAPI(
    title="XLSX to BI 智能看板",
    description="上传Excel文件，AI自动分析生成BI看板",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段允许所有来源
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
