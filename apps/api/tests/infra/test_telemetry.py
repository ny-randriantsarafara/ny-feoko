"""Tests for telemetry setup."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from infra.telemetry.setup import init_telemetry, get_tracer


class TestTelemetrySetup:
    def test_init_telemetry_configures_tracer_provider(self) -> None:
        init_telemetry(service_name="test-service")

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

    def test_get_tracer_returns_tracer(self) -> None:
        init_telemetry(service_name="test-service")

        tracer = get_tracer("test-module")
        assert tracer is not None
