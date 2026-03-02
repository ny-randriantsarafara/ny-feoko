"""Application metrics using OpenTelemetry."""

from __future__ import annotations

from infra.telemetry.setup import get_meter


class ApiMetrics:
    """Metrics for the Ambara API.

    Usage in routes (ports layer):
        metrics = ApiMetrics()
        metrics.record_job_started("ingest")
    """

    def __init__(self) -> None:
        meter = get_meter("ambara.api")

        self._jobs_started = meter.create_counter(
            name="jobs_started_total",
            description="Total jobs started",
            unit="1",
        )

        self._jobs_completed = meter.create_counter(
            name="jobs_completed_total",
            description="Total jobs completed",
            unit="1",
        )

        self._job_duration = meter.create_histogram(
            name="job_duration_seconds",
            description="Job duration in seconds",
            unit="s",
        )

        self._active_jobs = meter.create_up_down_counter(
            name="jobs_active",
            description="Currently running jobs",
            unit="1",
        )

    def record_job_started(self, job_type: str) -> None:
        """Record a job starting."""
        attributes = {"job.type": job_type}
        self._jobs_started.add(1, attributes)
        self._active_jobs.add(1, attributes)

    def record_job_completed(
        self,
        job_type: str,
        success: bool,
        duration_seconds: float,
    ) -> None:
        """Record a job completing."""
        attributes = {
            "job.type": job_type,
            "job.success": str(success).lower(),
        }
        self._jobs_completed.add(1, attributes)
        self._active_jobs.add(-1, {"job.type": job_type})
        self._job_duration.record(duration_seconds, attributes)
