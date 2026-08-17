"""
Structured logging + trace-ID correlation (roadmap Phase 1: "Full logging &
traceability").

Replaces ad hoc `print()` calls with structured JSON log lines, and threads a
single `trace_id` per user query through every agent call and MLflow run tag
via a contextvar — so "show me everything that happened for this one query"
is answerable by grepping one ID across logs and MLflow, instead of guessing
from timestamps.

Usage:
    from src.observability.logging_config import get_logger, new_trace_id, trace_id_scope

    logger = get_logger(__name__)

    trace_id = new_trace_id()
    with trace_id_scope(trace_id):
        logger.info("processing query")  # log line includes trace_id
"""

import json
import logging
import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_APP_LOGGER_NAME = "finance_compliance_rag"

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")

_configured = False


def new_trace_id() -> str:
    """Generate a fresh trace ID — call once per user query."""
    return uuid.uuid4().hex


def get_trace_id() -> str:
    """Current trace ID bound to this context, or "-" if none is set."""
    return _trace_id_var.get()


@contextmanager
def trace_id_scope(trace_id: str) -> Iterator[str]:
    """
    Bind trace_id to the current context for the duration of the block.

    Safe across asyncio.gather(): each gathered coroutine's Task captures a
    copy of the current context at creation time, so a trace_id set before
    `asyncio.gather(...)` is visible inside every task it spawns.
    """
    token = _trace_id_var.set(trace_id)
    try:
        yield trace_id
    finally:
        _trace_id_var.reset(token)


class _TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id_var.get()
        return True


# Standard LogRecord attributes, so `logger.info(..., extra={"confidence": x})`
# style calls surface their extra fields in the JSON payload automatically
# instead of silently being dropped.
_RESERVED_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
    "trace_id",
}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """
    Idempotent. Attaches a JSON handler to our own "finance_compliance_rag"
    logger namespace only (propagate=False) so this doesn't hijack logging
    config for third-party libraries (openai, streamlit, langchain, ...).
    """
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_TraceIdFilter())

    app_logger = logging.getLogger(_APP_LOGGER_NAME)
    app_logger.setLevel(level)
    app_logger.addHandler(handler)
    app_logger.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Returns a logger under the app's namespace with JSON+trace_id output configured."""
    configure_logging()
    return logging.getLogger(f"{_APP_LOGGER_NAME}.{name}")
