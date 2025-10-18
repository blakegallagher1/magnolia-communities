"""Placeholder endpoints for file operations."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.utils.signed_urls import generate_presigned_get, generate_presigned_put

router = APIRouter()


class PresignRequest(BaseModel):
    key: str = Field(..., min_length=1)
    mode: str = Field("put", pattern="^(put|get)$")
    content_type: str | None = None
    ttl_seconds: int = Field(900, ge=60, le=3600)


@router.post("/presign")
async def create_presigned_url(request: PresignRequest):
    ttl = timedelta(seconds=request.ttl_seconds)
    if request.mode == "put":
        url = generate_presigned_put(
            key=request.key, expires=ttl, content_type=request.content_type
        )
    else:
        url = generate_presigned_get(key=request.key, expires=ttl)
    if not url:
        raise HTTPException(status_code=500, detail="Failed to generate presigned URL")
    return {"url": url}
