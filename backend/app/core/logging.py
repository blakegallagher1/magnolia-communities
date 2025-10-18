"""
Logging configuration with structured JSON logging and request context support.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import Request
from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
user_agent_ctx: ContextVar[str] = ContextVar("user_agent", default="-")


class RequestContextFilter(logging.Filter):
    """Inject request metadata into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        record.user_agent = user_agent_ctx.get("-")
        return True


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Populate context variables for request scoped logging."""

    async def dispatch(self, request: Request, call_next) -> Any:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        user_agent = request.headers.get("user-agent", "unknown")

        request.state.request_id = request_id
        token_id = request_id_ctx.set(request_id)
        token_agent = user_agent_ctx.set(user_agent)

        try:
            response = await call_next(request)
        except Exception:
            request_id_ctx.reset(token_id)
            user_agent_ctx.reset(token_agent)
            raise

        response.headers["X-Request-ID"] = request_id
        request_id_ctx.reset(token_id)
        user_agent_ctx.reset(token_agent)
        return response


def _build_formatter() -> jsonlogger.JsonFormatter:
    """Create JSON formatter with default field set."""
    return jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d %(request_id)s %(user_agent)s"
    )


def setup_logging():
    """Configure structured JSON logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_build_formatter())
    handler.addFilter(RequestContextFilter())
    root_logger.addHandler(handler)

    # Ensure uvicorn loggers propagate to root for consistent formatting.
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Quiet noisy libraries while preserving error output.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


__all__ = [
    "RequestContextMiddleware",
    "RequestContextFilter",
    "setup_logging",
    "request_id_ctx",
    "user_agent_ctx",
]
