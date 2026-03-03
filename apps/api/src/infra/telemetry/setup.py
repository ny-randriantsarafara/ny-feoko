"""OpenTelemetry setup and configuration."""

from __future__ import annotations

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from infra.telemetry.logging import configure_logging

_initialized = False


def init_telemetry(
    service_name: str = "ambara-api",
    *,
    otlp_endpoint: str | None = None,
    console_export: bool = True,
    log_level: str = "INFO",
) -> None:
    """Initialize OpenTelemetry with tracer and meter providers.

    Args:
        service_name: Name to identify this service in traces/metrics.
        otlp_endpoint: OTLP collector endpoint. If None, uses console export.
        console_export: If True, export to console (for development).
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
    """
    global _initialized
    if _initialized:
        return

    resource = Resource(attributes={SERVICE_NAME: service_name})

    # Tracer setup
    tracer_provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    if console_export:
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(tracer_provider)

    # Meter setup
    readers = []
    if otlp_endpoint:
        readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=otlp_endpoint)))
    if console_export:
        readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))

    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(meter_provider)

    # Configure structured logging with trace correlation
    configure_logging(level=log_level)

    _initialized = True


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer for the given module name."""
    return trace.get_tracer(name)


def get_meter(name: str) -> metrics.Meter:
    """Get a meter for the given module name."""
    return metrics.get_meter(name)


def reset_telemetry() -> None:
    """Reset telemetry state (for testing)."""
    global _initialized
    _initialized = False
