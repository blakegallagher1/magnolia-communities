"""
Underwriting autopilot API endpoints.

These routes expose the orchestration service that transforms T12 financials,
loan terms, and property assumptions into a complete underwriting package.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import limiter
from app.core.database import get_db
from app.schemas.underwriting import UnderwritingRunRequest, UnderwritingRunResponse
from app.services.underwriting_autopilot import UnderwritingAutopilotService

router = APIRouter()


@router.post(
    "/run",
    response_model=UnderwritingRunResponse,
    summary="Execute the underwriting autopilot workflow",
    response_description="Structured underwriting analysis including stress tests and projections",
)
@limiter.limit("20/minute", key_func=get_remote_address)
async def run_underwriting_autopilot(
    request: Request,
    payload: UnderwritingRunRequest,
    db: AsyncSession = Depends(get_db),
) -> UnderwritingRunResponse:
    """
    Trigger the underwriting autopilot for a deal.

    The request should include property metadata, trailing-twelve financials,
    and loan assumptions. In return the service delivers the base metrics,
    stress testing, a 10-year projection, and a recommendation verdict.
    """
    service = UnderwritingAutopilotService(db)
    try:
        return await service.run(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
