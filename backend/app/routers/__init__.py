from .upload import router as upload_router
from .chat import router as chat_router
from .health import router as health_router
from .data import router as data_router
from .auth import router as auth_router
from .space import router as space_router
from .admin import router as admin_router
from .understanding import router as understanding_router
from .relations import router as relations_router
from .bi import router as bi_router

__all__ = [
    "upload_router", "chat_router", "health_router",
    "data_router", "auth_router", "space_router", "admin_router",
    "understanding_router", "relations_router", "bi_router"
]
