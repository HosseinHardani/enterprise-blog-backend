"""
Simple fixed-window rate limiter backed by Redis. Keyed by client IP
(falls back to a shared bucket if the IP can't be determined, e.g. tests).
Skips docs/openapi/health endpoints so tooling never gets throttled.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.dependencies.redis_client import get_redis_pool

EXEMPT_PATHS = {"/docs", "/redoc", "/openapi.json", "/health", "/"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        window = f"ratelimit:{client_ip}"

        redis = get_redis_pool()
        try:
            current = await redis.incr(window)
            if current == 1:
                await redis.expire(window, 60)
            if current > settings.RATE_LIMIT_PER_MINUTE:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests. Please try again later.",
                        "details": None,
                    },
                )
        except Exception:
            # If Redis is unavailable, fail open rather than taking the API down.
            pass

        return await call_next(request)
