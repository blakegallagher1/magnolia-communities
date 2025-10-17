import pytest
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.parcel_hunter import ParcelHunterService, ParcelHunterConfig


class StubSocrataConnector:
    async def close(self) -> None:
        return None


class StubArcGISConnector:
    async def spatial_query(self, *args, **kwargs):
        return []

    async def close(self) -> None:
        return None


@pytest.fixture
def mock_session() -> AsyncSession:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    return session


@dataclass
class CandidateStub:
    parcel_uid: str
    estimated_units: int
    complaints: int
    complaints_per_unit: float
    is_in_floodplain: bool
    acreage: float


@pytest.mark.asyncio
async def test_parcel_hunter_run_updates_status(mock_session: AsyncSession) -> None:
    service = ParcelHunterService(
        db=mock_session,
        socrata=StubSocrataConnector(),
        arcgis=StubArcGISConnector(),
        config=ParcelHunterConfig(min_units=10, floodplain_exclusion=False),
    )

    candidate = CandidateStub(
        parcel_uid="123",
        estimated_units=40,
        complaints=1,
        complaints_per_unit=0.05,
        is_in_floodplain=False,
        acreage=5.0,
    )

    with patch.object(service, "_collect_candidates", new=AsyncMock(return_value=[candidate])):
        with patch.object(service, "_persist_results", new=AsyncMock(return_value=1)):
            run = await service.run()

    assert run.status == "completed"
    assert run.leads_created == 1
    mock_session.add.assert_called()
    mock_session.commit.assert_awaited()


def test_parcel_hunter_scoring_pursue() -> None:
    service = ParcelHunterService(
        db=MagicMock(),
        socrata=StubSocrataConnector(),
        arcgis=StubArcGISConnector(),
        config=ParcelHunterConfig(min_units=10, floodplain_exclusion=False),
    )

    candidate = CandidateStub(
        parcel_uid="abc",
        estimated_units=30,
        complaints=0,
        complaints_per_unit=0.0,
        is_in_floodplain=False,
        acreage=4.0,
    )

    scored = list(service._score_candidates([candidate]))
    assert scored[0][1] >= 70
    assert scored[0][2] == "PURSUE"


def test_parcel_hunter_scoring_pass_when_low_units() -> None:
    service = ParcelHunterService(
        db=MagicMock(),
        socrata=StubSocrataConnector(),
        arcgis=StubArcGISConnector(),
        config=ParcelHunterConfig(min_units=20, floodplain_exclusion=False),
    )

    candidate = CandidateStub(
        parcel_uid="low",
        estimated_units=5,
        complaints=0,
        complaints_per_unit=0.0,
        is_in_floodplain=False,
        acreage=0.5,
    )

    scored = list(service._score_candidates([candidate]))
    assert scored[0][1] == 0
    assert scored[0][2] == "PASS"
