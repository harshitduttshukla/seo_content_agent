"""Small structured logging setup with secret-safe context fields."""

import json
import logging
from datetime import UTC, datetime

from app.observability.context import request_id_context


class JsonFormatter(logging.Formatter):
    """Render one JSON object per log record for collection by the platform."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for key in ("method", "path", "status_code", "duration_ms", "error_code"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            exception_type = record.exc_info[0]
            if exception_type is not None:
                payload["exception"] = exception_type.__name__
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
