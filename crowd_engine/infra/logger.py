"""
Infrastructure — structured logging with optional JSON format and correlation IDs.

Usage
-----
    from crowd_engine.infra.logger import get_logger
    log = get_logger(__name__)
    log.info("crowd estimated", extra={"count": 5, "provider": "opencv"})
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

from crowd_engine.infra.config import settings

# Per-request correlation ID stored in a context variable
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def set_correlation_id(cid: Optional[str] = None) -> str:
    cid = cid or str(uuid.uuid4())
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str:
    return _correlation_id.get()


class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Merge any extra fields the caller attached
        for key, val in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
            }:
                payload[key] = val
        return json.dumps(payload, default=str)


def _build_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s "
                "[corr=%(correlation_id_)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
    return handler


_handler = _build_handler()
_handler.setLevel(settings.log_level)


class _CorrelationFilter(logging.Filter):
    """Inject the current correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id_ = get_correlation_id() or "-"
        return True


_handler.addFilter(_CorrelationFilter())

_root = logging.getLogger("crowd_engine")
_root.setLevel(settings.log_level)
_root.addHandler(_handler)
_root.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger scoped under the crowd_engine hierarchy."""
    return logging.getLogger(f"crowd_engine.{name}" if not name.startswith("crowd_engine") else name)
