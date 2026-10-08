"""Structured JSON Logging for DeployOS."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add custom structured attributes attached to record
        if hasattr(record, "workflow_id"):
            log_payload["workflow_id"] = record.workflow_id
        if hasattr(record, "run_id"):
            log_payload["run_id"] = record.run_id
        if hasattr(record, "agent"):
            log_payload["agent"] = record.agent
        if hasattr(record, "event"):
            log_payload["event"] = record.event
        if hasattr(record, "tool"):
            log_payload["tool"] = record.tool
        if hasattr(record, "latency_ms"):
            log_payload["latency_ms"] = record.latency_ms
        if hasattr(record, "status"):
            log_payload["status"] = record.status
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_payload.update(record.extra_data)

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def get_logger(name: str = "deployos") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    return logger


class StructuredLogger:
    def __init__(self, name: str = "deployos"):
        self.logger = get_logger(name)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, kwargs)

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, kwargs)

    def _log(self, level: int, msg: str, extra: dict[str, Any]) -> None:
        record = self.logger.makeRecord(
            self.logger.name, level, "(unknown)", 0, msg, (), None
        )
        for k, v in extra.items():
            setattr(record, k, v)
        self.logger.handle(record)


logger = StructuredLogger()
