from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "code": 200,
        "status": "healthy",
        "service": "xlsx-to-bi-backend"
    }
