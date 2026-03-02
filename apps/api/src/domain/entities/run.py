"""Run entity — represents an extraction or reading session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RunType(str, Enum):
    EXTRACTION = "extraction"
    READING = "reading"


@dataclass(frozen=True)
class Run:
    id: str
    label: str
    source: str | None
    run_type: RunType
    created_at: datetime
