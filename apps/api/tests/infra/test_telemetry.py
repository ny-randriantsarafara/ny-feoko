"""Tests for telemetry setup."""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from infra.telemetry.logging import TraceContextFilter, configure_logging
from infra.telemetry.metrics import ApiMetrics
from infra.telemetry.setup import get_tracer, init_telemetry


class TestTelemetrySetup:
    def test_init_telemetry_configures_tracer_provider(self) -> None:
        init_telemetry(service_name="test-service")

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

    def test_get_tracer_returns_tracer(self) -> None:
        init_telemetry(service_name="test-service")

        tracer = get_tracer("test-module")
        assert tracer is not None


class TestApiMetrics:
    def test_record_job_started(self) -> None:
        init_telemetry(service_name="test-service", console_export=False)
        metrics = ApiMetrics()
        # Should not raise
        metrics.record_job_started(job_type="ingest")

    def test_record_job_completed(self) -> None:
        init_telemetry(service_name="test-service", console_export=False)
        metrics = ApiMetrics()
        # Should not raise
        metrics.record_job_completed(job_type="ingest", success=True, duration_seconds=10.5)
        metrics.record_job_completed(job_type="ingest", success=False, duration_seconds=5.0)


class TestLogging:
    def test_trace_context_filter_adds_trace_fields(self) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        filter = TraceContextFilter()
        result = filter.filter(record)

        assert result is True
        assert hasattr(record, "trace_id")
        assert hasattr(record, "span_id")

    def test_configure_logging_sets_root_level(self) -> None:
        configure_logging(level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

        # Reset to INFO
        configure_logging(level="INFO")
        assert root.level == logging.INFO

    def test_configure_logging_adds_handler_with_filter(self) -> None:
        configure_logging(level="INFO")
        root = logging.getLogger()

        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert any(isinstance(f, TraceContextFilter) for f in handler.filters)


class TestCliLogging:
    def test_configure_cli_logging_sets_level(self) -> None:
        from infra.telemetry.logging import configure_cli_logging

        configure_cli_logging(verbose=False)
        root = logging.getLogger()
        assert root.level == logging.INFO

        configure_cli_logging(verbose=True)
        assert root.level == logging.DEBUG

    def test_configure_cli_logging_uses_rich_handler(self) -> None:
        from rich.logging import RichHandler

        from infra.telemetry.logging import configure_cli_logging

        configure_cli_logging(verbose=True)
        root = logging.getLogger()

        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], RichHandler)
