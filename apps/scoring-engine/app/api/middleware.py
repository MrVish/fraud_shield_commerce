from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import settings


class APIKeyMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != settings.internal_api_key:
            return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
        return await call_next(request)
