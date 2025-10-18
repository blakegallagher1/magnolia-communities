"""
API v1 router - aggregates all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    health_router,
    parcels_router,
    crm_router,
    financial_router,
    dd_router,
    campaigns_router,
    data_catalog_router,
    parcel_hunter_router,
    underwriting_router,
)

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
api_router.include_router(
    underwriting_router, prefix="/underwriting", tags=["underwriting"]
)
