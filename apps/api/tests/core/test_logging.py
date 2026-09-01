"""Security regression tests for structured logging."""

import logging

from meetinghq_api.core.logging import SensitiveQueryFilter, configure_logging


def test_sensitive_query_filter_redacts_websocket_access_token() -> None:
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "WebSocket %s" [accepted]',
        args=("127.0.0.1", "/api/v1/notifications/ws?token=secret-value&mode=live"),
        exc_info=None,
    )

    assert SensitiveQueryFilter().filter(record)
    rendered = record.getMessage()

    assert "secret-value" not in rendered
    assert "token=[REDACTED]&mode=live" in rendered


def test_logging_configuration_filters_uvicorn_websocket_logs() -> None:
    configure_logging("INFO", json_output=False)

    assert any(
        isinstance(item, SensitiveQueryFilter)
        for item in logging.getLogger("uvicorn.error").filters
    )
