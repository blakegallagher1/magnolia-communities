"""Utilities for generating presigned S3 URLs."""

from __future__ import annotations

from datetime import timedelta
from typing import Literal

import boto3
from botocore.client import Config

from app.core.config import settings

PresignMethod = Literal["get_object", "put_object"]


def _s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        config=Config(signature_version="s3v4"),
    )


def generate_presigned_url(
    key: str,
    method: PresignMethod,
    expires_in: int = 900,
    content_type: str | None = None,
    bucket: str | None = None,
) -> str:
    bucket_name = bucket or settings.S3_BUCKET_NAME
    if not bucket_name:
        raise ValueError("S3 bucket name is not configured")

    client = _s3_client()
    params: dict[str, str] = {"Bucket": bucket_name, "Key": key}
    if method == "put_object" and content_type:
        params["ContentType"] = content_type

    return client.generate_presigned_url(
        ClientMethod=method,
        Params=params,
        ExpiresIn=expires_in,
    )


def generate_presigned_put(
    key: str,
    expires: timedelta = timedelta(minutes=15),
    content_type: str | None = None,
) -> str:
    return generate_presigned_url(
        key=key,
        method="put_object",
        expires_in=int(expires.total_seconds()),
        content_type=content_type,
    )


def generate_presigned_get(
    key: str,
    expires: timedelta = timedelta(minutes=15),
) -> str:
    return generate_presigned_url(
        key=key,
        method="get_object",
        expires_in=int(expires.total_seconds()),
    )
