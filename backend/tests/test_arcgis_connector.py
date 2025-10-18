"""Tests for ArcGIS REST API connector."""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import Response

from app.connectors.arcgis import ArcGISConnector, ArcGISService


@pytest.fixture
def mock_cache():
    """Mock cache service."""
    cache = AsyncMock()
    cache.get.return_value = None
    return cache


@pytest.fixture
def arcgis(mock_cache):
    """ArcGIS connector with mocked cache."""
    return ArcGISConnector(mock_cache)


class TestArcGISConnector:
    """Test ArcGIS connector functionality."""
    
    @pytest.mark.asyncio
    async def test_query_layer_success(self, arcgis, mock_cache):
        """Test successful layer query."""
        mock_response = {
            "features": [
                {
                    "attributes": {"OBJECTID": 1, "ZONE_CODE": "R-1"},
                    "geometry": {"rings": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
                },
            ]
        }
        
        with patch.object(arcgis.client, "get") as mock_get:
            mock_get.return_value = Response(
                200,
                json=mock_response,
                headers={"content-type": "application/json"}
            )
            
            result = await arcgis.query_layer(
                ArcGISService.ZONING,
                where="1=1",
                out_fields="*",
                return_geometry=True
            )
            
            assert result == mock_response
            mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_query_layer_pagination(self, arcgis, mock_cache):
        """Test pagination with result_offset and result_record_count."""
        with patch.object(arcgis.client, "get") as mock_get:
            mock_get.return_value = Response(
                200,
                json={"features": []},
                headers={"content-type": "application/json"}
            )
            
            await arcgis.query_layer(
                ArcGISService.TAX_PARCELS,
                result_offset=1000,
                result_record_count=500
            )
            
            call_url = mock_get.call_args[0][0]
            assert "resultOffset=1000" in call_url
            assert "resultRecordCount=500" in call_url
    
    @pytest.mark.asyncio
    async def test_query_layer_caches_results(self, arcgis, mock_cache):
        """Test that results are cached with appropriate key."""
        with patch.object(arcgis.client, "get") as mock_get:
            mock_get.return_value = Response(
                200,
                json={"features": []},
                headers={"content-type": "application/json"}
            )
            
            await arcgis.query_layer(
                ArcGISService.ZONING,
                where="ZONE_CODE='R-1'"
            )
            
            # Verify cache.set was called
            mock_cache.set.assert_called_once()
            cache_key = mock_cache.set.call_args[0][0]
            assert "arcgis:" in cache_key
            assert ArcGISService.ZONING.value in cache_key
    
    @pytest.mark.asyncio
    async def test_query_layer_uses_cache(self, arcgis, mock_cache):
        """Test cache hit avoids API call."""
        cached_data = {"features": [{"cached": True}]}
        mock_cache.get.return_value = cached_data
        
        with patch.object(arcgis.client, "get") as mock_get:
            result = await arcgis.query_layer(ArcGISService.ZONING)
            
            assert result == cached_data
            mock_get.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_query_all_handles_pagination(self, arcgis, mock_cache):
        """Test query_all paginates through large result sets."""
        # First page
        page1 = {
            "features": [{"attributes": {"OBJECTID": i}} for i in range(1000)],
            "exceededTransferLimit": True,
        }
        # Second page
        page2 = {
            "features": [{"attributes": {"OBJECTID": i}} for i in range(1000, 1500)],
            "exceededTransferLimit": False,
        }
        
        with patch.object(arcgis.client, "get") as mock_get:
            mock_get.side_effect = [
                Response(200, json=page1, headers={"content-type": "application/json"}),
                Response(200, json=page2, headers={"content-type": "application/json"}),
            ]
            
            result = await arcgis.query_all(ArcGISService.TAX_PARCELS, where="1=1")
            
            assert len(result) == 1500
            assert mock_get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_query_layer_retry_on_timeout(self, arcgis, mock_cache):
        """Test retry on timeout errors."""
        with patch.object(arcgis.client, "get") as mock_get:
            # Timeout once, then succeed
            mock_get.side_effect = [
                Response(504, text="Gateway Timeout"),
                Response(200, json={"features": []}, headers={"content-type": "application/json"}),
            ]
            
            result = await arcgis.query_layer(ArcGISService.ZONING)
            
            assert result == {"features": []}
            assert mock_get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_layer_metadata_success(self, arcgis):
        """Test fetching layer metadata."""
        mock_metadata = {
            "currentVersion": 11.1,
            "id": 0,
            "name": "Zoning Districts",
            "type": "Feature Layer",
            "editingInfo": {"lastEditDate": 1697654400000}
        }
        
        with patch.object(arcgis.client, "get") as mock_get:
            mock_get.return_value = Response(
                200,
                json=mock_metadata,
                headers={"content-type": "application/json"}
            )
            
            result = await arcgis.get_layer_metadata(ArcGISService.ZONING)
            
            assert result == mock_metadata
            assert "f=json" in mock_get.call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_query_layer_handles_empty_response(self, arcgis, mock_cache):
        """Test handling of empty feature sets."""
        with patch.object(arcgis.client, "get") as mock_get:
            mock_get.return_value = Response(
                200,
                json={"features": []},
                headers={"content-type": "application/json"}
            )
            
            result = await arcgis.query_layer(ArcGISService.SR_311_OPEN)
            
            assert result == {"features": []}
    
    @pytest.mark.asyncio
    async def test_query_layer_with_geometry_parameters(self, arcgis, mock_cache):
        """Test geometry-related query parameters."""
        with patch.object(arcgis.client, "get") as mock_get:
            mock_get.return_value = Response(
                200,
                json={"features": []},
                headers={"content-type": "application/json"}
            )
            
            await arcgis.query_layer(
                ArcGISService.TAX_PARCELS,
                return_geometry=True,
                out_sr=4326
            )
            
            call_url = mock_get.call_args[0][0]
            assert "returnGeometry=true" in call_url
            assert "outSR=4326" in call_url
    
    @pytest.mark.asyncio
    async def test_close_releases_client(self, arcgis):
        """Test connector cleanup."""
        with patch.object(arcgis.client, "aclose") as mock_close:
            await arcgis.close()
            mock_close.assert_called_once()

