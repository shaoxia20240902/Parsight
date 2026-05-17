import os
from enum import Enum
from pathlib import Path

# 加载 .env 文件（开发环境）
try:
    from dotenv import load_dotenv
    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
except ImportError:
    pass

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据库配置（仅 MySQL）
# 示例：mysql+aiomysql://user:password@host:3306/database?charset=utf8mb4
DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 未配置；本项目 BI 生成仅支持 MySQL")
if not DATABASE_URL.startswith("mysql+"):
    raise RuntimeError("DATABASE_URL 必须使用 MySQL async driver，例如 mysql+aiomysql://...")

# 文件上传配置
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 允许的文件类型
ALLOWED_EXTENSIONS = {".xlsx", ".xls"}

# 最大Sheet数量
MAX_SHEETS = 5

# 数据采样配置
SAMPLE_FIRST_N = 10  # 前N条数据
SAMPLE_RANDOM_N = 90  # 随机N条数据
RELATIONS_RANDOM_SAMPLE_N = 20  # 关联分析：每个 Sheet 随机采样行数


# ============================================================
# Agent 后端选型配置
# ============================================================

class AgentBackend(str, Enum):
    """Agent 后端类型"""
    LOCAL = "local"          # 本地 LLM 提示词模式
    SHENZHOU = "shenzhou"    # 神州问学平台（未对接前请勿使用）

# Agent 后端开关：local / shenzhou
AGENT_BACKEND = AgentBackend(os.getenv("AGENT_BACKEND", "local"))

# ============================================================
# 神州问学平台配置
# ============================================================
SHENZHOU_API_BASE = os.getenv("SHENZHOU_API_BASE", "https://api.shenzhou.com")
SHENZHOU_API_KEY = os.getenv("SHENZHOU_API_KEY", "")
SHENZHOU_TIMEOUT = int(os.getenv("SHENZHOU_TIMEOUT", "60"))

# ============================================================
# 本地 LLM 配置（DashScope / 阿里云百炼）
# ============================================================
DASHSCOPE_API_KEY = os.getenv(
    "DASHSCOPE_API_KEY",
    "sk-9c888698018d4181945bdadbbc555224"
)
# 主模型（用于复杂推理：总结、报告、图表、看板构建）
LLM_MODEL_QWEN_PRIMARY = os.getenv("LLM_MODEL_QWEN_PRIMARY", "qwen3-max")
# 备用模型（用于简单任务：关键词确认、子问题筛选）
LLM_MODEL_QWEN_ALT = os.getenv("LLM_MODEL_QWEN_ALT", "qwen3-235b")

# DashScope OpenAI 兼容 API 地址
DASHSCOPE_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 通用 LLM 配置（向后兼容，用于 BI 智能分类等）
LLM_API_BASE = os.getenv("LLM_API_BASE", DASHSCOPE_API_BASE)
LLM_API_KEY = os.getenv("LLM_API_KEY", DASHSCOPE_API_KEY)
LLM_MODEL = os.getenv("LLM_MODEL", LLM_MODEL_QWEN_PRIMARY)
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

# ============================================================
# Agent 运行时配置
# ============================================================
AGENT_MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "2"))
AGENT_DEFAULT_TIMEOUT = int(os.getenv("AGENT_DEFAULT_TIMEOUT", "60"))
AGENT_SQL_TIMEOUT = int(os.getenv("AGENT_SQL_TIMEOUT", "30"))
AGENT_SHEET_SUMMARY_TIMEOUT = int(os.getenv("AGENT_SHEET_SUMMARY_TIMEOUT", "20"))
AGENT_CHART_TIMEOUT = int(os.getenv("AGENT_CHART_TIMEOUT", "20"))
AGENT_REPORT_TIMEOUT = int(os.getenv("AGENT_REPORT_TIMEOUT", "30"))

# OSS 配置
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "")
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME", "xlsx-bi")
OSS_BASE_PATH = "xlsx-qa"

# 服务端口
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# JWT配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "xlsx-bi-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 默认24小时
