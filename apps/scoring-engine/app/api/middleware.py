import hmac
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import settings


class APIKeyMiddleware(BaseHTTPMiddleware):
    EXEMPT_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")

    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(api_key, settings.internal_api_key):
            return JSONResponse(status_code=401, content={"detail": "Invalid API key"})

        return await call_next(request)
