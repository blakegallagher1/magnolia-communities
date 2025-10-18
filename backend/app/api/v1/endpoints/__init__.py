"""
Convenience exports for API v1 endpoint routers.

This allows ``from app.api.v1.endpoints import parcels_router`` style imports
used by the aggregate router module.
"""

from .health import router as health_router
from .parcels import router as parcels_router
from .crm import router as crm_router
from .financial import router as financial_router
from .dd import router as dd_router
from .campaigns import router as campaigns_router
from .data_catalog import router as data_catalog_router
from .parcel_hunter import router as parcel_hunter_router
from .underwriting import router as underwriting_router

__all__ = [
    "health_router",
    "parcels_router",
    "crm_router",
    "financial_router",
    "dd_router",
    "campaigns_router",
    "data_catalog_router",
    "parcel_hunter_router",
    "underwriting_router",
]
