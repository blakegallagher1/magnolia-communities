"""Tests for freshness monitoring background job."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.tasks.freshness_job import FreshnessJob


@pytest.mark.asyncio
async def test_freshness_job_checks_all_sources():
    """Test that freshness job checks all registered sources."""
    job = FreshnessJob()
    
    # Mock services
    mock_source1 = MagicMock(source_name="source1")
    mock_source2 = MagicMock(source_name="source2")
    
    with patch("app.tasks.freshness_job.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        with patch("app.tasks.freshness_job.get_redis") as mock_redis:
            with patch("app.tasks.freshness_job.DataCatalogService") as mock_catalog_service:
                with patch("app.tasks.freshness_job.SocrataConnector") as mock_socrata:
                    with patch("app.tasks.freshness_job.ArcGISConnector") as mock_arcgis:
                        # Setup mocks
                        catalog_instance = mock_catalog_service.return_value
                        catalog_instance.get_all_sources.return_value = [mock_source1, mock_source2]
                        catalog_instance.check_freshness.side_effect = [
                            {"needs_refresh": False},
                            {"needs_refresh": True, "remote_updated_at": "2025-10-18"},
                        ]
                        catalog_instance.get_health_summary.return_value = {
                            "healthy": 1,
                            "degraded": 1,
                            "failed": 0
                        }
                        
                        # Run job
                        await job.run()
                        
                        # Verify all sources were checked
                        assert catalog_instance.check_freshness.call_count == 2
                        catalog_instance.get_health_summary.assert_called_once()


@pytest.mark.asyncio
async def test_freshness_job_triggers_re_ingestion():
    """Test that stale sources trigger re-ingestion."""
    job = FreshnessJob()
    
    mock_source = MagicMock(source_name="ebr_property_info")
    
    with patch("app.tasks.freshness_job.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        with patch("app.tasks.freshness_job.get_redis"):
            with patch("app.tasks.freshness_job.DataCatalogService") as mock_catalog:
                with patch("app.tasks.freshness_job.DataIngestionJob") as mock_ingestion:
                    with patch("app.tasks.freshness_job.SocrataConnector"):
                        with patch("app.tasks.freshness_job.ArcGISConnector"):
                            # Setup stale source
                            catalog_instance = mock_catalog.return_value
                            catalog_instance.get_all_sources.return_value = [mock_source]
                            catalog_instance.check_freshness.return_value = {"needs_refresh": True}
                            catalog_instance.get_health_summary.return_value = {
                                "healthy": 0,
                                "degraded": 0,
                                "failed": 0
                            }
                            
                            ingestion_instance = mock_ingestion.return_value
                            
                            # Run job
                            await job.run()
                            
                            # Verify ingestion was called
                            ingestion_instance.ingest_property_info.assert_called_once()


@pytest.mark.asyncio
async def test_freshness_job_sends_alert_on_degraded():
    """Test alert is sent when sources are degraded."""
    job = FreshnessJob()
    
    with patch("app.tasks.freshness_job.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        with patch("app.tasks.freshness_job.get_redis"):
            with patch("app.tasks.freshness_job.DataCatalogService") as mock_catalog:
                with patch("app.tasks.freshness_job.SocrataConnector"):
                    with patch("app.tasks.freshness_job.ArcGISConnector"):
                        with patch("app.tasks.freshness_job.NotificationService") as mock_notif:
                            # Setup degraded health
                            catalog_instance = mock_catalog.return_value
                            catalog_instance.get_all_sources.return_value = []
                            catalog_instance.get_health_summary.return_value = {
                                "healthy": 1,
                                "degraded": 2,
                                "failed": 1
                            }
                            
                            # Run job
                            await job.run()
                            
                            # Verify alert was sent
                            mock_notif.notify_data_health_degraded.assert_called_once()


@pytest.mark.asyncio
async def test_freshness_job_handles_ingestion_errors():
    """Test that job continues if ingestion fails for one source."""
    job = FreshnessJob()
    
    source1 = MagicMock(source_name="ebr_property_info")
    source2 = MagicMock(source_name="ebr_zoning")
    
    with patch("app.tasks.freshness_job.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        with patch("app.tasks.freshness_job.get_redis"):
            with patch("app.tasks.freshness_job.DataCatalogService") as mock_catalog:
                with patch("app.tasks.freshness_job.DataIngestionJob") as mock_ingestion:
                    with patch("app.tasks.freshness_job.SocrataConnector"):
                        with patch("app.tasks.freshness_job.ArcGISConnector"):
                            # Setup two stale sources
                            catalog_instance = mock_catalog.return_value
                            catalog_instance.get_all_sources.return_value = [source1, source2]
                            catalog_instance.check_freshness.return_value = {"needs_refresh": True}
                            catalog_instance.get_health_summary.return_value = {
                                "healthy": 0,
                                "degraded": 0,
                                "failed": 0
                            }
                            
                            ingestion_instance = mock_ingestion.return_value
                            # First ingestion fails, second succeeds
                            ingestion_instance.ingest_property_info.side_effect = Exception("API Error")
                            ingestion_instance.ingest_zoning.return_value = None
                            
                            # Run job (should not raise)
                            await job.run()
                            
                            # Both ingestions attempted
                            ingestion_instance.ingest_property_info.assert_called_once()
                            ingestion_instance.ingest_zoning.assert_called_once()

