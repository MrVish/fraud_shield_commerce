import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.health import router as health_router
from app.api.v1.scoring import router as scoring_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.chargebacks import router as chargebacks_router
from app.api.v1.merchants import router as merchants_router
from app.api.middleware import APIKeyMiddleware

logger = logging.getLogger(__name__)

# Startup validation: warn about insecure defaults
if not settings.debug:
    if settings.internal_api_key == "dev-key":
        logger.critical("SECURITY: Running with default API key in non-debug mode. Set SC_INTERNAL_API_KEY.")
    if settings.encryption_key == "change-me-in-production-32-bytes!":
        logger.critical("SECURITY: Running with default encryption key. Set SC_ENCRYPTION_KEY.")

app = FastAPI(title=settings.app_name, version=settings.app_version)

# CORS: restrict to known origins in production
allowed_origins = ["*"] if settings.debug else settings.allowed_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)
app.add_middleware(APIKeyMiddleware)

app.include_router(health_router)
app.include_router(scoring_router)
app.include_router(dashboard_router)
app.include_router(chargebacks_router)
app.include_router(merchants_router)
