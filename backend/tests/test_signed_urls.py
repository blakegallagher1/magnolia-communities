"""Tests for signed URL utilities."""

from datetime import timedelta

import boto3
import pytest

from app.utils import signed_urls


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    monkeypatch.setattr("app.utils.signed_urls.settings.S3_BUCKET_NAME", "bucket")
    monkeypatch.setattr("app.utils.signed_urls.settings.AWS_REGION", "us-east-1")
    monkeypatch.setattr("app.utils.signed_urls.settings.AWS_ACCESS_KEY_ID", "key")
    monkeypatch.setattr("app.utils.signed_urls.settings.AWS_SECRET_ACCESS_KEY", "secret")


def test_generate_presigned_get(monkeypatch):
    called = {}

    class DummyClient:
        def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
            called.update(
                {
                    "ClientMethod": ClientMethod,
                    "Params": Params,
                    "ExpiresIn": ExpiresIn,
                }
            )
            return "https://signed"

    monkeypatch.setattr(signed_urls, "_s3_client", lambda: DummyClient())

    url = signed_urls.generate_presigned_get("path/to/object")
    assert url == "https://signed"
    assert called["ClientMethod"] == "get_object"
    assert called["Params"]["Key"] == "path/to/object"


def test_generate_presigned_put(monkeypatch):
    called = {}

    class DummyClient:
        def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
            called.update(
                {
                    "ClientMethod": ClientMethod,
                    "Params": Params,
                    "ExpiresIn": ExpiresIn,
                }
            )
            return "https://signed-put"

    monkeypatch.setattr(signed_urls, "_s3_client", lambda: DummyClient())

    expires = timedelta(minutes=5)
    url = signed_urls.generate_presigned_put(
        "upload/file", expires=expires, content_type="application/pdf"
    )
    assert url == "https://signed-put"
    assert called["ClientMethod"] == "put_object"
    assert called["Params"]["ContentType"] == "application/pdf"
    assert called["ExpiresIn"] == int(expires.total_seconds())


def test_generate_presigned_no_bucket(monkeypatch):
    monkeypatch.setattr("app.utils.signed_urls.settings.S3_BUCKET_NAME", "")
    with pytest.raises(ValueError):
        signed_urls.generate_presigned_get("missing")

