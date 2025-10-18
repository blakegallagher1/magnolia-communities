"""
Health check endpoints.
"""

from typing import Dict

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis

router = APIRouter()


@router.get("/liveness", status_code=status.HTTP_200_OK)
async def liveness() -> Dict[str, str]:
    """Simple liveness probe."""
    return {"status": "alive"}


@router.get("/readiness")
async def readiness(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Readiness probe that verifies database and Redis connectivity."""
    checks: Dict[str, Dict[str, str]] = {}
    overall_status = status.HTTP_200_OK

    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        checks["database"] = {"status": "pass"}
    except Exception as exc:  # pragma: no cover - defensive guard
        checks["database"] = {"status": "fail", "reason": str(exc)}
        overall_status = status.HTTP_503_SERVICE_UNAVAILABLE

    try:
        await redis.ping()
        checks["redis"] = {"status": "pass"}
    except Exception as exc:  # pragma: no cover - defensive guard
        checks["redis"] = {"status": "fail", "reason": str(exc)}
        overall_status = status.HTTP_503_SERVICE_UNAVAILABLE

    body = {
        "status": "ready" if overall_status == status.HTTP_200_OK else "not_ready",
        "checks": checks,
    }
    return JSONResponse(status_code=overall_status, content=body)
