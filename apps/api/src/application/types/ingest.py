"""Canonical ingest request schema used by application layer."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class IngestRequest(BaseModel):
    url: str
    label: str = ""
    whisper_model: str = "small"
    whisper_hf: str | None = None
    vad_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    speech_threshold: float = Field(default=0.35, ge=0.0, le=1.0)

    @field_validator("url", mode="before")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value

        normalized = value.strip()
        if not normalized:
            raise ValueError("url must be a non-empty string")

        has_scheme = "://" in normalized
        if has_scheme and not normalized.startswith(("http://", "https://")):
            raise ValueError(
                "url must be a local file path or start with http:// or https://"
            )
        return normalized

    @field_validator("label", mode="before")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        if not isinstance(value, str):
            return value

        return value.strip()

    @field_validator("whisper_hf", mode="before")
    @classmethod
    def _normalize_empty_whisper_hf(cls, value: str | None) -> str | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value
