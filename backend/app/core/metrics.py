"""
Prometheus metrics and instrumentation helpers.
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


HTTP_REQUESTS_TOTAL = Counter(
    "app_http_requests_total",
    "Total count of HTTP requests processed.",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "app_http_request_duration_seconds",
    "Histogram of HTTP request durations in seconds.",
    ["method", "path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

HTTP_REQUEST_ERRORS = Counter(
    "app_http_request_errors_total",
    "Count of HTTP requests resulting in error responses.",
    ["method", "path", "status"],
)

CACHE_OPERATIONS = Counter(
    "app_cache_operations_total",
    "Cache operations partitioned by outcome.",
    ["operation"],
)

EXTERNAL_API_RETRIES = Counter(
    "app_external_api_retries_total",
    "Retries issued when calling external APIs.",
    ["service"],
)


def _normalise_path(request: Request) -> str:
    """Prefer route path templates to reduce cardinality in metrics."""
    route = request.scope.get("route")
    if route and hasattr(route, "path_format"):
        return route.path_format
    if route and hasattr(route, "path"):
        return route.path
    return request.url.path


def observe_http_request(method: str, path: str, status_code: int, duration: float) -> None:
    """Record metrics for an HTTP request."""
    status_str = str(status_code)
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status_str).inc()
    HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)

    if status_code >= 400:
        HTTP_REQUEST_ERRORS.labels(method=method, path=path, status=status_str).inc()


def record_cache_operation(operation: str) -> None:
    """Increment cache operation counters."""
    CACHE_OPERATIONS.labels(operation=operation).inc()


def record_external_api_retry(service: str) -> None:
    """Increment retry counter for an external service."""
    EXTERNAL_API_RETRIES.labels(service=service).inc()


class MetricsMiddleware(BaseHTTPMiddleware):
    """ASGI middleware for capturing request metrics."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        method = request.method
        path = _normalise_path(request)
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - start
            observe_http_request(method, path, 500, duration)
            raise

        duration = time.perf_counter() - start
        observe_http_request(method, path, response.status_code, duration)
        return response


__all__ = [
    "MetricsMiddleware",
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_DURATION",
    "HTTP_REQUEST_ERRORS",
    "CACHE_OPERATIONS",
    "EXTERNAL_API_RETRIES",
    "observe_http_request",
    "record_cache_operation",
    "record_external_api_retry",
]
