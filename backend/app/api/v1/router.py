"""
API v1 router - aggregates all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.campaigns import router as campaigns_router
from app.api.v1.endpoints.crm import router as crm_router
from app.api.v1.endpoints.data_catalog import router as data_catalog_router
from app.api.v1.endpoints.dd import router as dd_router
from app.api.v1.endpoints.financial import router as financial_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.parcel_hunter import router as parcel_hunter_router
from app.api.v1.endpoints.parcels import router as parcels_router
try:  # pragma: no cover - optional endpoint depending on feature flag
    from app.api.v1.endpoints.underwriting import router as underwriting_router
except ImportError:  # pragma: no cover - backward compatibility
    underwriting_router = None

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(parcels_router, prefix="/parcels", tags=["parcels"])
api_router.include_router(crm_router, prefix="/crm", tags=["crm"])
api_router.include_router(financial_router, prefix="/financial", tags=["financial"])
api_router.include_router(dd_router, prefix="/dd", tags=["due-diligence"])
api_router.include_router(campaigns_router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(
    data_catalog_router, prefix="/data-catalog", tags=["data-catalog"]
)
api_router.include_router(
    parcel_hunter_router, prefix="/parcel-hunter", tags=["agents"]
)
if underwriting_router:
    api_router.include_router(
        underwriting_router, prefix="/underwriting", tags=["underwriting"]
    )
