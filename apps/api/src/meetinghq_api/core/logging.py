"""Structured logging configuration."""

import logging
import re
import sys

import structlog

_SENSITIVE_QUERY_VALUE = re.compile(
    r"([?&](?:token|access_token|refresh_token)=)[^&\s\"]+",
    flags=re.IGNORECASE,
)


class SensitiveQueryFilter(logging.Filter):
    """Redact authentication material embedded in logged request URLs."""

    @staticmethod
    def _redact(value: object) -> object:
        if not isinstance(value, str):
            return value
        return _SENSITIVE_QUERY_VALUE.sub(r"\1[REDACTED]", value)

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(self._redact(value) for value in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: self._redact(value) for key, value in record.args.items()}
        return True


def configure_logging(log_level: str, *, json_output: bool) -> None:
    """Configure standard-library and structlog output."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level, force=True)
    sensitive_query_filter = SensitiveQueryFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(sensitive_query_filter)
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        server_logger = logging.getLogger(logger_name)
        server_logger.addFilter(sensitive_query_filter)
        for handler in server_logger.handlers:
            handler.addFilter(sensitive_query_filter)
    structlog.configure(
        processors=[*shared_processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(log_level)),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
