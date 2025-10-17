"""
Notification utilities for Slack and Email alerts.
"""

import logging
from typing import Optional, Dict, Any
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via Slack and Email."""

    @staticmethod
    async def send_slack(message: str, channel: Optional[str] = None):
        """
        Send Slack notification.

        Args:
            message: Message to send
            channel: Optional channel override
        """
        if not settings.SLACK_WEBHOOK_URL:
            logger.warning("Slack webhook URL not configured")
            return

        payload = {"text": message}
        if channel:
            payload["channel"] = channel

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.SLACK_WEBHOOK_URL,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
            logger.info("Slack notification sent")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    @staticmethod
    def send_email(
        to: str,
        subject: str,
        body: str,
        html: Optional[str] = None,
    ):
        """
        Send email notification.

        Args:
            to: Recipient email
            subject: Email subject
            body: Plain text body
            html: Optional HTML body
        """
        if not all(
            [
                settings.SMTP_HOST,
                settings.SMTP_USER,
                settings.SMTP_PASSWORD,
            ]
        ):
            logger.warning("SMTP not configured")
            return

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_USER
            msg["To"] = to

            # Attach parts
            part1 = MIMEText(body, "plain")
            msg.attach(part1)

            if html:
                part2 = MIMEText(html, "html")
                msg.attach(part2)

            # Send
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, to, msg.as_string())

            logger.info(f"Email sent to {to}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")

    @staticmethod
    async def notify_data_health_degraded(health_summary: Dict[str, Any]):
        """Send alert when data sources are degraded."""
        message = (
            f"⚠️ *Data Health Alert*\n"
            f"Degraded: {health_summary['degraded']}\n"
            f"Failed: {health_summary['failed']}\n"
            f"Total sources: {health_summary['total_sources']}"
        )

        await NotificationService.send_slack(message)

    @staticmethod
    async def notify_schema_drift(source_name: str, changes: list):
        """Alert on schema drift detection."""
        message = (
            f"🔄 *Schema Drift Detected*\n"
            f"Source: {source_name}\n"
            f"Changes: {', '.join(changes)}"
        )

        await NotificationService.send_slack(message)

    @staticmethod
    async def notify_high_311_surge(
        parcel_address: str,
        sr_count: int,
        threshold: int,
    ):
        """Alert on 311 request surge near target parcel."""
        message = (
            f"🚨 *311 Surge Alert*\n"
            f"Location: {parcel_address}\n"
            f"Requests: {sr_count} (threshold: {threshold})"
        )

        await NotificationService.send_slack(message)

    @staticmethod
    async def notify_insurance_renewal(
        park_name: str,
        days_until: int,
    ):
        """Remind about upcoming insurance renewal."""
        message = (
            f"📋 *Insurance Renewal Reminder*\n"
            f"Park: {park_name}\n"
            f"Days until renewal: {days_until}"
        )

        await NotificationService.send_slack(message)
