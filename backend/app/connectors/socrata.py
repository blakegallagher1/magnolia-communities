"""Socrata SODA v2 API connector for Open Data BR."""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.core.config import settings
from app.core.redis import CacheService
from app.core.metrics import record_external_api_retry

logger = logging.getLogger(__name__)


def _record_socrata_retry(retry_state):
    """Tenacity before_sleep callback to track Socrata retries."""
    record_external_api_retry("socrata")


class SocrataConnector:
    """
    Connector for Socrata SODA v2 API with caching and retry logic.

    Example usage:
        connector = SocrataConnector(cache_service)
        results = await connector.query(
            dataset_id="re5c-hrw9",
            select=["parcel_id", "site_address", "owner_name"],
            where="upper(site_address) like '%CAPITOL%'",
            limit=100
        )
    """

    def __init__(self, cache_service: CacheService):
        self.base_url = settings.SOCRATA_BASE_URL
        self.app_token = settings.SOCRATA_APP_TOKEN
        self.cache = cache_service
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with app token."""
        headers = {"Accept": "application/json"}
        if self.app_token:
            headers["X-App-Token"] = self.app_token
        return headers

    def _build_cache_key(
        self,
        dataset_id: str,
        select: Optional[List[str]] = None,
        where: Optional[str] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> str:
        """Generate a deterministic cache key from query parameters."""

        payload = {
            "dataset": dataset_id,
            "select": sorted(select) if select else None,
            "where": where or None,
            "order": order or None,
            "limit": limit,
            "offset": offset,
        }
        serialized = json.dumps(
            payload,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        return f"socrata:{serialized}"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        before_sleep=_record_socrata_retry,
        reraise=True,
    )
    async def query(
        self,
        dataset_id: str,
        select: Optional[List[str]] = None,
        where: Optional[str] = None,
        order: Optional[str] = None,
        limit: Optional[int] = 1000,
        offset: Optional[int] = 0,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Query Socrata dataset with SoQL parameters.

        Args:
            dataset_id: Socrata dataset ID (e.g., "re5c-hrw9")
            select: List of fields to return
            where: WHERE clause (SoQL syntax)
            order: ORDER BY clause
            limit: Maximum records to return
            offset: Number of records to skip
            use_cache: Whether to use Redis cache

        Returns:
            List of result records as dictionaries
        """
        # Check cache first
        cache_key = self._build_cache_key(
            dataset_id, select, where, order, limit, offset
        )

        if use_cache:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "socrata_cache_hit",
                    extra={"dataset_id": dataset_id, "cache_key": cache_key},
                )
                return cached
            logger.info(
                "socrata_cache_miss",
                extra={"dataset_id": dataset_id, "cache_key": cache_key},
            )

        # Build query parameters
        params = {}
        if select:
            params["$select"] = ",".join(select)
        if where:
            params["$where"] = where
        if order:
            params["$order"] = order
        if limit:
            params["$limit"] = limit
        if offset:
            params["$offset"] = offset

        # Make request
        url = f"{self.base_url}/{dataset_id}.json"
        logger.info(
            "socrata_request",
            extra={"dataset_id": dataset_id, "url": url, "params": params},
        )

        response = await self.client.get(
            url,
            params=params,
            headers=self._build_headers(),
        )
        response.raise_for_status()

        results = response.json()

        # Cache results
        if use_cache:
            await self.cache.set(
                cache_key,
                results,
                ttl=settings.SOCRATA_CACHE_TTL,
            )
            logger.info(
                "socrata_cache_store",
                extra={
                    "dataset_id": dataset_id,
                    "cache_key": cache_key,
                    "ttl": settings.SOCRATA_CACHE_TTL,
                },
            )

        logger.info(
            "socrata_response",
            extra={"dataset_id": dataset_id, "record_count": len(results)},
        )
        return results

    async def get_metadata(self, dataset_id: str) -> Dict[str, Any]:
        """
        Get dataset metadata including last update time.

        Returns metadata with fields:
            - id: dataset ID
            - name: dataset name
            - description: description
            - updatedAt: last update timestamp
            - rowsUpdatedAt: last data update timestamp
            - columns: column definitions
        """
        url = f"https://data.brla.gov/api/views/{dataset_id}.json"

        response = await self.client.get(url, headers=self._build_headers())
        response.raise_for_status()

        metadata = response.json()

        return {
            "id": metadata.get("id"),
            "name": metadata.get("name"),
            "description": metadata.get("description"),
            "updatedAt": metadata.get("rowsUpdatedAt"),
            "rowsUpdatedAt": metadata.get("rowsUpdatedAt"),
            "columns": metadata.get("columns", []),
            "rowCount": metadata.get("viewCount", 0),
        }

    async def query_all(
        self,
        dataset_id: str,
        select: Optional[List[str]] = None,
        where: Optional[str] = None,
        order: Optional[str] = None,
        batch_size: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Query all records by paginating through dataset.

        Args:
            dataset_id: Socrata dataset ID
            select: Fields to return
            where: Filter clause
            order: Sort clause
            batch_size: Records per batch

        Returns:
            All matching records
        """
        all_results = []
        offset = 0

        while True:
            batch = await self.query(
                dataset_id=dataset_id,
                select=select,
                where=where,
                order=order,
                limit=batch_size,
                offset=offset,
                use_cache=False,  # Don't cache individual batches
            )

            if not batch:
                break

            all_results.extend(batch)
            offset += batch_size

            logger.info(f"Retrieved {len(all_results)} total records from {dataset_id}")

            # Stop if we got fewer records than requested
            if len(batch) < batch_size:
                break

        return all_results


# Property dataset configuration
PROPERTY_INFO_FIELDS = [
    "parcel_id",
    "site_address",
    "owner_name",
    "subdivision",
    "municipality",
    "zip",
    "land_use",
    "lot_id",
    "naics",
    "council_district",
    "latitude",
    "longitude",
    "last_update",
]
