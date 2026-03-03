"""Structured logging with trace correlation."""

from __future__ import annotations

import logging
import sys

from opentelemetry import trace


class TraceContextFilter(logging.Filter):
    """Add trace context to log records for correlation."""

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context()

        record.trace_id = format(ctx.trace_id, "032x") if ctx.trace_id else ""
        record.span_id = format(ctx.span_id, "016x") if ctx.span_id else ""

        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging with trace context.

    Log format includes trace_id and span_id for correlation with traces.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(TraceContextFilter())

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s "
        "[trace_id=%(trace_id)s span_id=%(span_id)s] "
        "%(message)s"
    )
    handler.setFormatter(formatter)

    root.addHandler(handler)
