"""Tests for campaign-related API endpoints."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.endpoints.campaigns import get_campaign_performance


class _ScalarResult:
    """Helper to mimic SQLAlchemy result objects."""

    def __init__(self, scalar_value, *, one_or_none: bool = False):
        self._scalar_value = scalar_value
        self._one_or_none = one_or_none

    def scalar_one_or_none(self):
        if not self._one_or_none:
            raise AttributeError("scalar_one_or_none unavailable")
        return self._scalar_value

    def scalar(self):
        return self._scalar_value


@pytest.mark.asyncio
async def test_campaign_performance_counts_leads(monkeypatch):
    campaign_id = uuid4()
    campaign = SimpleNamespace(
        id=campaign_id,
        name="Test Campaign",
        sent_count=100,
        response_count=20,
        status="active",
    )

    class StubSession:
        def __init__(self):
            self._executions = [
                _ScalarResult(campaign, one_or_none=True),
                _ScalarResult(7),
            ]

        async def execute(self, *_args, **_kwargs):
            return self._executions.pop(0)

    session = StubSession()

    payload = await get_campaign_performance(campaign_id, db=session)  # type: ignore[arg-type]

    assert payload["campaign_id"] == campaign_id
    assert payload["leads_generated"] == 7
    assert payload["response_rate"] == 0.2
