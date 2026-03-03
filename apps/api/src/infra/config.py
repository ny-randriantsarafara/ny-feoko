"""Settings loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    dotenv_path = repo_root / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    device: str = "cpu"
    input_dir: Path = Path("data/input")
    output_dir: Path = Path("data/output")
    whisper_model: str = "small"
    # Telemetry settings
    otel_endpoint: str | None = None
    otel_service_name: str = "ambara-api"
    otel_console_export: bool = True

    @classmethod
    def from_env(cls) -> Settings:
        _load_env()
        return cls(
            supabase_url=os.environ.get("SUPABASE_URL", ""),
            supabase_service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
            device=os.environ.get("API_DEVICE", "cpu"),
            input_dir=Path(os.environ.get("API_INPUT_DIR", "data/input")),
            output_dir=Path(os.environ.get("API_OUTPUT_DIR", "data/output")),
            whisper_model=os.environ.get("API_WHISPER_MODEL", "small"),
            otel_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
            otel_service_name=os.environ.get("OTEL_SERVICE_NAME", "ambara-api"),
            otel_console_export=os.environ.get("OTEL_CONSOLE_EXPORT", "true").lower() == "true",
        )
