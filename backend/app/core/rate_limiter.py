"""SlowAPI rate limiting setup."""

from __future__ import annotations

from slowapi import Limiter, extension as slowapi_extension
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings


def _build_limiter() -> Limiter:
    try:
        return Limiter(
            key_func=get_remote_address,
            default_limits=["100/minute"],
            storage_uri=str(settings.REDIS_URL),
        )
    except Exception:  # pragma: no cover - fallback when Redis unavailable
        return Limiter(key_func=get_remote_address, default_limits=["100/minute"])


limiter = _build_limiter()


def _rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    detail = getattr(exc, "detail", str(exc))
    response = JSONResponse(
        {"error": f"Rate limit exceeded: {detail}"}, status_code=429
    )
    view_limit = getattr(request.state, "view_rate_limit", None)
    if view_limit is not None:
        response = limiter._inject_headers(response, view_limit)
    return response


slowapi_extension._rate_limit_exceeded_handler = _rate_limit_handler


class RateLimitMiddleware(SlowAPIMiddleware):
    exempt_paths = {
        "/metrics",
        "/health",
        "/api/v1/health/liveness",
        "/api/v1/health/readiness",
    }

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        return await super().dispatch(request, call_next)
