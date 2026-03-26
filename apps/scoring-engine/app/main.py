from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.health import router as health_router
from app.api.v1.scoring import router as scoring_router
from app.api.middleware import APIKeyMiddleware

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])
app.add_middleware(APIKeyMiddleware)

app.include_router(health_router)
app.include_router(scoring_router)
