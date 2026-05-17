import uvicorn
from app.config import SERVER_PORT

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=SERVER_PORT,
        reload=True
    )
