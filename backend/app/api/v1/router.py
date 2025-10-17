"""
API v1 router - aggregates all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    parcels,
    crm,
    financial,
    dd,
    campaigns,
    data_catalog,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(parcels.router, prefix="/parcels", tags=["parcels"])
api_router.include_router(crm.router, prefix="/crm", tags=["crm"])
api_router.include_router(financial.router, prefix="/financial", tags=["financial"])
api_router.include_router(dd.router, prefix="/dd", tags=["due-diligence"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(
    data_catalog.router, prefix="/data-catalog", tags=["data-catalog"]
)
