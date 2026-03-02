"""Tests for telemetry setup."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from infra.telemetry.setup import get_tracer, init_telemetry
from infra.telemetry.metrics import ApiMetrics


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
