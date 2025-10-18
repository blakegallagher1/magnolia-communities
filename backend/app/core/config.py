"""
Application configuration using Pydantic Settings.
"""

from typing import List
from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="allow"
    )

    # Environment
    ENVIRONMENT: str = "development"
    SECRET_KEY: str
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: PostgresDsn

    # Redis
    REDIS_URL: RedisDsn
    REDIS_CACHE_TTL: int = 3600  # 1 hour default

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # External APIs - Socrata
    SOCRATA_BASE_URL: str = "https://data.brla.gov/resource"
    SOCRATA_APP_TOKEN: str = ""
    SOCRATA_PROPERTY_DATASET: str = "re5c-hrw9"
    SOCRATA_RATE_LIMIT: int = 1000  # requests per hour

    # External APIs - ArcGIS
    ARCGIS_BASE_URL: str = "https://maps.brla.gov/gis/rest/services"
    ARCGIS_311_BASE_URL: str = (
        "https://services.arcgis.com/KYvXadMcgf0K1EzK/arcgis/rest/services"
    )
    ARCGIS_MAX_RECORD_COUNT: int = 1000
    SOCRATA_CACHE_TTL: int = 600  # seconds
    ARCGIS_CACHE_TTL: int = 600  # seconds

    # Data Catalog
    DATA_CATALOG_REFRESH_INTERVAL: int = 86400  # 24 hours
    DATA_QUALITY_CHECK_INTERVAL: int = 3600  # 1 hour

    # Observability
    SENTRY_DSN: str = ""
    LOG_LEVEL: str = "INFO"

    # Email/Notifications
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SLACK_WEBHOOK_URL: str = ""

    # AWS
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v


settings = Settings()
