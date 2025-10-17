"""
Logging configuration with structured JSON logging.
"""

import logging
import sys
from pythonjsonlogger import jsonlogger

from app.core.config import settings


def setup_logging():
    """Configure structured JSON logging."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
