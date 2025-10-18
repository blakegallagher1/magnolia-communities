"""Tests for Parcel Hunter scheduled job."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest

from app.tasks.parcel_hunter_job import run_parcel_hunter_job


@pytest.mark.asyncio
async def test_run_parcel_hunter_job_executes_service():
    """Test that scheduled job executes ParcelHunterService."""
    mock_run = MagicMock(
        id=uuid4(),
        status="completed",
        total_candidates=15,
        leads_created=3
    )
    
    with patch("app.tasks.parcel_hunter_job.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        with patch("app.tasks.parcel_hunter_job.get_redis"):
            with patch("app.tasks.parcel_hunter_job.SocrataConnector"):
                with patch("app.tasks.parcel_hunter_job.ArcGISConnector"):
                    with patch("app.tasks.parcel_hunter_job.ParcelHunterService") as mock_service:
                        # Setup mock service
                        service_instance = mock_service.return_value
                        service_instance.run.return_value = mock_run
                        
                        # Run job
                        await run_parcel_hunter_job()
                        
                        # Verify service was called
                        mock_service.assert_called_once()
                        service_instance.run.assert_called_once()


@pytest.mark.asyncio
async def test_run_parcel_hunter_job_logs_results():
    """Test that job logs execution results."""
    mock_run = MagicMock(
        id=uuid4(),
        status="completed",
        total_candidates=20,
        leads_created=5
    )
    
    with patch("app.tasks.parcel_hunter_job.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        
        with patch("app.tasks.parcel_hunter_job.get_redis"):
            with patch("app.tasks.parcel_hunter_job.SocrataConnector"):
                with patch("app.tasks.parcel_hunter_job.ArcGISConnector"):
                    with patch("app.tasks.parcel_hunter_job.ParcelHunterService") as mock_service:
                        with patch("app.tasks.parcel_hunter_job.logger") as mock_logger:
                            service_instance = mock_service.return_value
                            service_instance.run.return_value = mock_run
                            
                            await run_parcel_hunter_job()
                            
                            # Verify logging
                            mock_logger.info.assert_called_once()
                            log_call = mock_logger.info.call_args[0][0]
                            assert "completed" in log_call
                            assert "candidates=20" in str(mock_logger.info.call_args)
                            assert "leads=5" in str(mock_logger.info.call_args)

