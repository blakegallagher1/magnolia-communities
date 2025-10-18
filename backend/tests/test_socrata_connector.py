"""Tests for Socrata SODA v2 API connector."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import Response

from app.connectors.socrata import SocrataConnector


@pytest.fixture
def mock_cache():
    """Mock cache service."""
    cache = AsyncMock()
    cache.get.return_value = None
    return cache


@pytest.fixture
def socrata(mock_cache):
    """Socrata connector with mocked cache."""
    return SocrataConnector(mock_cache)


class TestSocrataConnector:
    """Test Socrata connector functionality."""
    
    @pytest.mark.asyncio
    async def test_query_dataset_success(self, socrata, mock_cache):
        """Test successful dataset query."""
        mock_response = {
            "data": [
                {"parcel_id": "123", "owner_name": "John Doe"},
                {"parcel_id": "456", "owner_name": "Jane Smith"},
            ]
        }
        
        with patch.object(socrata.client, "get") as mock_get:
            mock_get.return_value = Response(
                200,
                json=mock_response,
                headers={"content-type": "application/json"}
            )
            
            result = await socrata.query_dataset(
                "test-dataset",
                select="parcel_id,owner_name",
                where="1=1",
                limit=10
            )
            
            assert result == mock_response
            mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_query_dataset_caches_results(self, socrata, mock_cache):
        """Test that results are cached."""
        mock_response = {"data": [{"id": 1}]}
        
        with patch.object(socrata.client, "get") as mock_get:
            mock_get.return_value = Response(
                200,
                json=mock_response,
                headers={"content-type": "application/json"}
            )
            
            await socrata.query_dataset("test-dataset", limit=10)
            
            # Verify cache.set was called
            mock_cache.set.assert_called_once()
            args = mock_cache.set.call_args
            assert "socrata:test-dataset" in args[0][0]
    
    @pytest.mark.asyncio
    async def test_query_dataset_uses_cache_when_available(self, socrata, mock_cache):
        """Test cache hit returns cached data without API call."""
        cached_data = {"data": [{"cached": True}]}
        mock_cache.get.return_value = cached_data
        
        with patch.object(socrata.client, "get") as mock_get:
            result = await socrata.query_dataset("test-dataset")
            
            assert result == cached_data
            mock_get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_query_dataset_with_pagination(self, socrata, mock_cache):
        """Test pagination parameters are passed correctly."""
        with patch.object(socrata.client, "get") as mock_get:
            mock_get.return_value = Response(
                200,
                json={"data": []},
                headers={"content-type": "application/json"}
            )
            
            await socrata.query_dataset(
                "test-dataset",
                limit=100,
                offset=200
            )
            
            call_args = mock_get.call_args
            assert "$limit=100" in call_args[0][0]
            assert "$offset=200" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_query_dataset_retry_on_failure(self, socrata, mock_cache):
        """Test retry logic on transient failures."""
        with patch.object(socrata.client, "get") as mock_get:
            # Fail twice, then succeed
            mock_get.side_effect = [
                Response(503, text="Service Unavailable"),
                Response(503, text="Service Unavailable"),
                Response(200, json={"data": [{"success": True}]}, headers={"content-type": "application/json"}),
            ]
            
            result = await socrata.query_dataset("test-dataset")
            
            assert result == {"data": [{"success": True}]}
            assert mock_get.call_count == 3
    
    @pytest.mark.asyncio
    async def test_query_dataset_max_retries_exceeded(self, socrata, mock_cache):
        """Test failure after max retries."""
        with patch.object(socrata.client, "get") as mock_get:
            # Always fail
            mock_get.return_value = Response(503, text="Service Unavailable")
            
            with pytest.raises(Exception):
                await socrata.query_dataset("test-dataset")
            
            # Should retry up to max attempts
            assert mock_get.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_get_metadata_success(self, socrata):
        """Test fetching dataset metadata."""
        mock_metadata = {
            "id": "test-123",
            "name": "Test Dataset",
            "rowsUpdatedAt": "2025-10-18T12:00:00.000Z"
        }
        
        with patch.object(socrata.client, "get") as mock_get:
            mock_get.return_value = Response(
                200,
                json=mock_metadata,
                headers={"content-type": "application/json"}
            )
            
            result = await socrata.get_metadata("test-dataset")
            
            assert result == mock_metadata
            assert "views/test-dataset" in mock_get.call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_close_releases_client(self, socrata):
        """Test connector cleanup."""
        with patch.object(socrata.client, "aclose") as mock_close:
            await socrata.close()
            mock_close.assert_called_once()

