"""Tests for notification utilities."""

from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.utils.notifications import NotificationService


@pytest.mark.asyncio
async def test_send_slack_no_webhook(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_WEBHOOK_URL", "")

    called = False

    async def fake_post(*_args, **_kwargs):
        nonlocal called
        called = True
        return SimpleNamespace(raise_for_status=lambda: None)

    class DummyClient:
        async def __aenter__(self):  # pragma: no cover - used implicitly
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return await fake_post(*args, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", DummyClient)

    await NotificationService.send_slack("hello")
    assert called is False


@pytest.mark.asyncio
async def test_send_slack_posts_message(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_WEBHOOK_URL", "https://slack.test/webhook")

    recorded = {}

    class DummyResponse:
        def raise_for_status(self):
            return None

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, timeout):
            recorded.update({"url": url, "json": json, "timeout": timeout})
            return DummyResponse()

    monkeypatch.setattr("httpx.AsyncClient", DummyClient)

    await NotificationService.send_slack("ping", channel="#alerts")
    assert recorded["url"] == "https://slack.test/webhook"
    assert recorded["json"]["text"] == "ping"
    assert recorded["json"]["channel"] == "#alerts"


def test_send_email_without_configuration(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    NotificationService.send_email("ops@example.com", "Subject", "Body")


def test_send_email_sends_message(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USER", "alerts@test")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret")

    class DummySMTP:
        def __init__(self, host, port):
            self.host = host
            self.port = port
            self.started = False
            self.logged_in = False
            self.sent = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            self.started = True

        def login(self, user, password):
            assert user == "alerts@test"
            assert password == "secret"
            self.logged_in = True

        def sendmail(self, sender, to, message):
            assert sender == "alerts@test"
            assert to == "ops@example.com"
            assert "Subject" in message
            self.sent = True

    instance = DummySMTP("smtp.test", 587)

    def smtp_factory(host, port):
        assert host == "smtp.test"
        assert port == 587
        return instance

    monkeypatch.setattr("smtplib.SMTP", smtp_factory)

    NotificationService.send_email("ops@example.com", "Subject", "Body", "<b>Body</b>")
    assert instance.started and instance.logged_in and instance.sent


@pytest.mark.asyncio
async def test_notification_wrappers(monkeypatch):
    captured = []

    async def fake_send(message, channel=None):
        captured.append((message, channel))

    monkeypatch.setattr(NotificationService, "send_slack", fake_send)

    await NotificationService.notify_data_health_degraded(
        {"degraded": 1, "failed": 2, "total_sources": 3}
    )
    await NotificationService.notify_schema_drift("source", ["new_column"])
    await NotificationService.notify_high_311_surge("123 Main", 10, 5)
    await NotificationService.notify_insurance_renewal("Park", 15)

    assert len(captured) == 4
