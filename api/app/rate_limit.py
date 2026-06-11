import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings

WINDOW_SECONDS = 60
AUTH_PATHS = {"/api/auth/login", "/api/auth/signup"}
EXEMPT_PATHS = {"/api/health"}
_SWEEP_THRESHOLD = 10_000


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding-window limiter, sized for a single-process deployment."""

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[tuple[str, str], deque[float]] = {}

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path
        if not settings.rate_limit_enabled or path in EXEMPT_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        if path in AUTH_PATHS:
            bucket, limit = "auth", settings.rate_limit_auth_per_minute
        else:
            bucket, limit = "global", settings.rate_limit_global_per_minute

        forwarded = request.headers.get("x-forwarded-for")
        client = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

        now = time.monotonic()
        hits = self._hits.setdefault((bucket, client), deque())
        while hits and hits[0] <= now - WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )
        hits.append(now)

        if len(self._hits) > _SWEEP_THRESHOLD:
            cutoff = now - WINDOW_SECONDS
            self._hits = {key: value for key, value in self._hits.items() if value and value[-1] > cutoff}

        return await call_next(request)
