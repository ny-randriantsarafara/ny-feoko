"""Tests for configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

from infra.config import Settings


class TestSettings:
    def test_telemetry_settings_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "http://test",
                "SUPABASE_SERVICE_ROLE_KEY": "key",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4317",
                "OTEL_SERVICE_NAME": "test-api",
            },
        ):
            settings = Settings.from_env()

            assert settings.otel_endpoint == "http://collector:4317"
            assert settings.otel_service_name == "test-api"

    def test_telemetry_settings_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SUPABASE_URL": "http://test",
                "SUPABASE_SERVICE_ROLE_KEY": "key",
            },
            clear=True,
        ):
            settings = Settings.from_env()

            assert settings.otel_endpoint is None
            assert settings.otel_service_name == "ambara-api"
