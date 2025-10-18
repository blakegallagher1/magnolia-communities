"""Unit tests for DataCatalogService utilities."""

from datetime import datetime, timezone

import pytest

from app.services.data_catalog import DataCatalogService


class TestDataCatalogTimestampParsing:
    """Ensure remote timestamp normalisation behaves as expected."""

    def test_parse_none(self):
        assert DataCatalogService._parse_remote_timestamp(None) is None

    def test_parse_epoch_seconds(self):
        ts = 1_706_000_000
        parsed = DataCatalogService._parse_remote_timestamp(ts)
        assert parsed == datetime.fromtimestamp(ts, tz=timezone.utc)

    def test_parse_epoch_milliseconds(self):
        ms = 1_706_000_000_000
        parsed = DataCatalogService._parse_remote_timestamp(ms)
        assert parsed == datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)

    def test_parse_numeric_string(self):
        parsed = DataCatalogService._parse_remote_timestamp("1706000000")
        assert parsed == datetime.fromtimestamp(1_706_000_000, tz=timezone.utc)

    @pytest.mark.parametrize(
        "value",
        [
            "2025-02-16T12:34:56Z",
            "2025-02-16T12:34:56+00:00",
            "2025-02-16T12:34:56.123456+00:00",
        ],
    )
    def test_parse_iso_strings(self, value: str):
        parsed = DataCatalogService._parse_remote_timestamp(value)
        assert parsed == datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )

    def test_parse_invalid_input(self):
        assert DataCatalogService._parse_remote_timestamp("not-a-date") is None
        assert DataCatalogService._parse_remote_timestamp(object()) is None
