from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.app_version,
        "services": {
            "database": "not_configured",
            "redis": "not_configured",
        },
    }
