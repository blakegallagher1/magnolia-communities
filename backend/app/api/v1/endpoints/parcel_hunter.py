"""Parcel Hunter agent endpoints."""
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import CacheService, get_redis
from app.connectors.arcgis import ArcGISConnector
from app.connectors.socrata import SocrataConnector
from app.services.parcel_hunter import ParcelHunterService, ParcelHunterConfig
from app.models.agents import ParcelHunterRun, ParcelHunterResult

router = APIRouter()


async def _build_service(db: AsyncSession) -> ParcelHunterService:
    redis = await get_redis()
    cache = CacheService(redis)
    socrata = SocrataConnector(cache)
    arcgis = ArcGISConnector(cache)
    return ParcelHunterService(db, socrata, arcgis, ParcelHunterConfig.from_settings())


@router.post("/runs", response_model=Dict[str, Any])
async def trigger_parcel_hunter(db: AsyncSession = Depends(get_db)):
    """Trigger a Parcel Hunter run immediately."""
    service = await _build_service(db)
    try:
        run = await service.run()
    finally:
        await service.socrata.close()
        await service.arcgis.close()
    return {
        "run_id": run.id,
        "status": run.status,
        "candidates": run.total_candidates,
        "leads_created": run.leads_created,
    }


@router.get("/runs", response_model=List[Dict[str, Any]])
async def list_runs(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(ParcelHunterRun)
        .order_by(ParcelHunterRun.started_at.desc())
        .limit(50)
    )
    runs = result.scalars().all()
    return [
        {
            "run_id": r.id,
            "status": r.status,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "total_candidates": r.total_candidates,
            "leads_created": r.leads_created,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=Dict[str, Any])
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    run = await db.get(ParcelHunterRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    stmt = (
        select(ParcelHunterResult)
        .where(ParcelHunterResult.run_id == run_id)
        .order_by(ParcelHunterResult.score.desc())
    )
    result = await db.execute(stmt)
    results = result.scalars().all()

    return {
        "run_id": run.id,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "total_candidates": run.total_candidates,
        "leads_created": run.leads_created,
        "results": [
            {
                "parcel_uid": r.parcel_uid,
                "recommendation": r.recommendation,
                "score": r.score,
                "reasoning": r.reasoning,
                "context": r.context,
            }
            for r in results
        ],
    }

