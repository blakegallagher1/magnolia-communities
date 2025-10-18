"""Parcel Hunter agent core service."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.connectors.arcgis import ArcGISConnector, ArcGISService
from app.connectors.socrata import SocrataConnector
from app.models.agents import ParcelHunterResult, ParcelHunterRun
from app.models.crm import Lead, LeadSource, Park, PipelineStage
from app.models.parcels import Parcel
from app.models.sr_311 import ServiceRequest311

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ParcelCandidate:
    """Intermediate candidate parcel evaluation."""

    parcel: Parcel
    complaints: int
    complaints_per_unit: float
    is_in_floodplain: bool
    estimated_units: int
    acreage: float


class ParcelHunterConfig(BaseModel):
    """Configuration for Parcel Hunter thresholds."""

    min_units: int = 20
    max_complaints_per_unit: float = 2.0
    floodplain_exclusion: bool = True
    acreage_unit_factor: float = 8.0  # units per acre heuristic
    target_municipalities: tuple[str, ...] = (
        "BATON ROUGE",
        "CENTRAL",
        "ZACHARY",
        "BAKER",
    )

    @classmethod
    def from_settings(cls) -> "ParcelHunterConfig":
        """Create config using environment overrides if provided."""
        municipalities = getattr(settings, "TARGET_MUNICIPALITIES", None)
        target = tuple(municipalities) if municipalities else cls.model_fields["target_municipalities"].default
        return cls(target_municipalities=target)


class ParcelHunterService:
    """Service for sourcing and scoring parcel acquisition targets."""

    def __init__(
        self,
        db: AsyncSession,
        socrata: SocrataConnector,
        arcgis: ArcGISConnector,
        config: ParcelHunterConfig | None = None,
    ) -> None:
        self.db = db
        self.socrata = socrata
        self.arcgis = arcgis
        self.config = config or ParcelHunterConfig.from_settings()

    async def run(self) -> ParcelHunterRun:
        """Execute the parcel hunter pipeline."""

        run = ParcelHunterRun(status="running")
        self.db.add(run)
        await self.db.flush()

        try:
            logger.info("Parcel Hunter run %s started", run.id)
            candidates = await self._collect_candidates()
            scored = list(self._score_candidates(candidates))

            logger.info("Parcel Hunter run %s evaluated %s parcels", run.id, len(scored))

            leads_created = await self._persist_results(run, scored)

            run.status = "completed"
            run.completed_at = datetime.utcnow()
            run.total_candidates = len(scored)
            run.leads_created = leads_created

            await self.db.commit()
            logger.info(
                "Parcel Hunter run %s completed (candidates=%s, leads=%s)",
                run.id,
                run.total_candidates,
                run.leads_created,
            )
            return run

        except Exception:
            logger.exception("Parcel Hunter run %s failed", run.id)
            await self.db.rollback()
            run.status = "failed"
            run.completed_at = datetime.utcnow()
            await self.db.commit()
            raise

    async def _collect_candidates(self) -> Sequence[ParcelCandidate]:
        """Fetch parcels and compute candidate attributes."""

        stmt = select(Parcel).where(Parcel.land_use.ilike("%mobile home%"))

        if self.config.target_municipalities:
            stmt = stmt.where(Parcel.municipality.in_(self.config.target_municipalities))
        result = await self.db.execute(stmt)
        parcels = result.scalars().all()

        logger.info("Fetched %s parcels for evaluation", len(parcels))

        candidates: list[ParcelCandidate] = []
        for parcel in parcels:
            acreage = self._compute_acreage(parcel)
            estimated_units = int(acreage * self.config.acreage_unit_factor)

            complaints, per_unit = await self._compute_complaints(parcel, estimated_units)
            floodplain = await self._check_floodplain(parcel)

            candidates.append(
                ParcelCandidate(
                    parcel=parcel,
                    complaints=complaints,
                    complaints_per_unit=per_unit,
                    is_in_floodplain=floodplain,
                    estimated_units=estimated_units,
                    acreage=acreage,
                )
            )

        return candidates

    async def _compute_complaints(
        self, parcel: Parcel, estimated_units: int
    ) -> tuple[int, float]:
        stmt = (
            select(ServiceRequest311)
            .where(ServiceRequest311.parcel_id == parcel.parcel_id)
        )

        result = await self.db.execute(stmt)
        complaints = len(result.scalars().all())
        per_unit = complaints / estimated_units if estimated_units else complaints
        return complaints, per_unit

    async def _check_floodplain(self, parcel: Parcel) -> bool:
        geometry = parcel.geometry
        if not geometry:
            return False

        features = await self.arcgis.spatial_query(
            service=ArcGISService.SUBJECT_PROPERTY,
            geometry={"rings": geometry.desc},
            geometry_type="esriGeometryPolygon",
        )
        return any(
            str(f["attributes"].get("FLOOD_ZONE", "")).startswith("AE") for f in features
        )

    def _score_candidates(self, candidates: Iterable[ParcelCandidate]) -> Iterable[tuple[ParcelCandidate, int, str]]:
        """Yield candidate with composite score and recommendation."""

        for candidate in candidates:
            if candidate.estimated_units < self.config.min_units:
                recommendation = "PASS"
                score = 0
            elif (
                self.config.floodplain_exclusion
                and candidate.is_in_floodplain
            ):
                recommendation = "PASS"
                score = 5
            elif candidate.complaints_per_unit > self.config.max_complaints_per_unit:
                recommendation = "MONITOR"
                score = 40
            else:
                # Base score on unit density and complaint rate inverse
                density_score = min(60, int(candidate.estimated_units * 2))
                complaint_score = max(30, int((self.config.max_complaints_per_unit - candidate.complaints_per_unit) * 20))
                score = min(100, density_score + complaint_score)
                recommendation = "PURSUE" if score >= 70 else "MONITOR"

            yield candidate, score, recommendation

    async def _persist_results(
        self,
        run: ParcelHunterRun,
        scored: Iterable[tuple[ParcelCandidate, int, str]],
    ) -> int:
        leads_created = 0
        for candidate, score, recommendation in scored:
            parcel = candidate.parcel

            result = ParcelHunterResult(
                run_id=run.id,
                parcel_uid=parcel.parcel_uid,
                parcel_id=parcel.parcel_id,
                site_address=parcel.site_address,
                owner_name=parcel.owner_name,
                municipality=parcel.municipality,
                parcel_acres=candidate.acreage,
                estimated_units=candidate.estimated_units,
                complaints_per_unit=candidate.complaints_per_unit,
                annual_complaints=candidate.complaints,
                flood_risk="100-year" if candidate.is_in_floodplain else "none",
                recommendation=recommendation,
                score=score,
                reasoning=self._build_reasoning(candidate, score, recommendation),
                context={
                    "is_in_floodplain": candidate.is_in_floodplain,
                    "complaints": candidate.complaints,
                },
            )

            self.db.add(result)

            if recommendation == "PURSUE":
                leads_created += await self._create_lead_if_missing(parcel, score)

        return leads_created

    def _build_reasoning(
        self, candidate: ParcelCandidate, score: int, recommendation: str
    ) -> str:
        return (
            f"{recommendation}: {candidate.estimated_units} unit potential, "
            f"{candidate.complaints_per_unit:.2f} complaints/unit, "
            f"floodplain={'yes' if candidate.is_in_floodplain else 'no'}, score={score}."
        )

    async def _create_lead_if_missing(self, parcel: Parcel, score: int) -> int:
        """Create CRM lead/park if not already tracked."""

        park_result = await self.db.execute(
            select(Park).where(Park.parcel_uid == parcel.parcel_uid)
        )
        park = park_result.scalar_one_or_none()

        if not park:
            park = Park(
                name=parcel.site_address or parcel.parcel_id or "Unknown",
                address=parcel.site_address,
                city=parcel.city,
                state="LA",
                zip_code=parcel.zip_code,
                latitude=parcel.latitude,
                longitude=parcel.longitude,
                parcel_uid=parcel.parcel_uid,
            )
            self.db.add(park)
            await self.db.flush()

        lead_result = await self.db.execute(
            select(Lead).where(Lead.park_id == park.id)
        )
        if lead_result.scalar_one_or_none():
            return 0

        lead = Lead(
            park_id=park.id,
            source=LeadSource.DIRECT_MAIL,
            stage=PipelineStage.SOURCED,
            notes=f"Parcel Hunter score {score}",
        )
        self.db.add(lead)
        return 1

    @staticmethod
    def _compute_acreage(parcel: Parcel) -> float:
        if not parcel.raw_data:
            return 0.0
        acreage = parcel.raw_data.get("acres") or parcel.raw_data.get("parcel_acres")
        try:
            return float(acreage)
        except (TypeError, ValueError):
            return 0.0


