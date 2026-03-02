"""Job entity — background task tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class JobType(str, Enum):
    INGEST = "ingest"
    REDRAFT = "redraft"
    EXPORT = "export"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class Job:
    id: str
    job_type: JobType
    status: JobStatus
    progress: int
    progress_message: str | None
    params: dict[str, Any]
    result: dict[str, Any] | None
    created_at: datetime
