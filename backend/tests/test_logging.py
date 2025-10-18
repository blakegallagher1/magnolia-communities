"""Tests for structured logging configuration."""

import logging

from app.core.logging import (
    RequestContextFilter,
    request_id_ctx,
    setup_logging,
    user_agent_ctx,
)


def test_request_context_filter_injects_fields():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )

    token_id = request_id_ctx.set("req-123")
    token_agent = user_agent_ctx.set("pytest-agent")
    try:
        context_filter = RequestContextFilter()
        assert context_filter.filter(record) is True
        assert record.request_id == "req-123"
        assert record.user_agent == "pytest-agent"
    finally:
        request_id_ctx.reset(token_id)
        user_agent_ctx.reset(token_agent)


def test_setup_logging_attaches_json_handler():
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level

    try:
        setup_logging()
        assert root_logger.handlers, "expected a handler after setup"
        handler = root_logger.handlers[0]
        filters = handler.filters
        assert any(isinstance(filter_, RequestContextFilter) for filter_ in filters)
        # Ensure formatter renders request fields even when unset.
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="message",
            args=(),
            exc_info=None,
        )
        for filter_ in filters:
            filter_.filter(record)
        formatted = handler.format(record)
        assert "request_id" in formatted
        assert "user_agent" in formatted
    finally:
        root_logger.handlers = original_handlers
        root_logger.setLevel(original_level)
