"""Canonical training/export/redraft request schemas used by application layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator


def _normalize_required_string(value: Any, field_name: str) -> Any:
    if not isinstance(value, str):
        return value

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    return normalized


def _normalize_run_ids(value: Any) -> Any:
    if not isinstance(value, list):
        return value

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("run_ids must only include non-empty strings")
        trimmed = item.strip()
        if trimmed == "":
            raise ValueError("run_ids must only include non-empty strings")
        normalized.append(trimmed)

    if not normalized:
        raise ValueError("run_ids must contain at least one run id")
    return normalized


class TrainRequest(BaseModel):
    data_dir: str
    output_dir: str = "models/whisper-mg-v1"
    device: str = "auto"
    base_model: str = "openai/whisper-small"
    epochs: int = Field(default=10, ge=1)
    batch_size: int = Field(default=4, ge=1)
    lr: float = Field(default=1e-5, gt=0.0)
    push_to_hub: str | None = None

    @field_validator("data_dir", "output_dir", "device", "base_model", mode="before")
    @classmethod
    def _validate_required_strings(cls, value: Any, info: ValidationInfo) -> Any:
        return _normalize_required_string(value, info.field_name)

    @field_validator("push_to_hub", mode="before")
    @classmethod
    def _normalize_push_to_hub(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value

        normalized = value.strip()
        if normalized == "":
            return None
        return normalized


class ExportRequest(BaseModel):
    run_ids: list[str]
    output: str = "data/output"
    eval_split: float = Field(default=0.1, ge=0.0, le=0.5)

    @field_validator("run_ids", mode="before")
    @classmethod
    def _validate_run_ids(cls, value: Any) -> Any:
        return _normalize_run_ids(value)

    @field_validator("output", mode="before")
    @classmethod
    def _validate_output(cls, value: Any) -> Any:
        return _normalize_required_string(value, "output")


class RedraftRequest(BaseModel):
    run_ids: list[str]
    model_path: str
    device: str = "auto"
    language: str = "mg"

    @field_validator("run_ids", mode="before")
    @classmethod
    def _validate_run_ids(cls, value: Any) -> Any:
        return _normalize_run_ids(value)

    @field_validator("model_path", mode="before")
    @classmethod
    def _validate_model_path(cls, value: Any) -> Any:
        return _normalize_required_string(value, "model_path")

    @field_validator("device", "language", mode="before")
    @classmethod
    def _normalize_optional_defaults(cls, value: Any, info: ValidationInfo) -> Any:
        if not isinstance(value, str):
            return value

        normalized = value.strip()
        if normalized:
            return normalized
        return "auto" if info.field_name == "device" else "mg"
