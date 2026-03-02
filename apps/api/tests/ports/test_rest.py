"""Tests for REST API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from domain.entities.job import Job, JobStatus, JobType
from domain.entities.run import Run, RunType
from ports.rest.routes.jobs import router as jobs_router
from ports.rest.routes.runs import router as runs_router


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(runs_router)
    app.include_router(jobs_router)
    return app


class TestRunsRoute:
    def test_list_runs(self) -> None:
        app = _create_test_app()
        now = datetime.now(tz=UTC)
        app.state.list_runs = MagicMock()
        app.state.list_runs.execute.return_value = [
            Run(
                id="r1",
                label="my-run",
                source="/path",
                run_type=RunType.EXTRACTION,
                created_at=now,
            )
        ]

        client = TestClient(app)
        response = client.get("/runs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "r1"
        assert data[0]["label"] == "my-run"
        assert data[0]["type"] == "extraction"

    def test_list_runs_empty(self) -> None:
        app = _create_test_app()
        app.state.list_runs = MagicMock()
        app.state.list_runs.execute.return_value = []

        client = TestClient(app)
        response = client.get("/runs")

        assert response.status_code == 200
        assert response.json() == []


class TestJobsRoute:
    def test_list_jobs(self) -> None:
        app = _create_test_app()
        app.state.job_repo = MagicMock()
        app.state.job_repo.list_recent.return_value = [
            {"id": "j1", "type": "ingest", "status": "done"}
        ]

        client = TestClient(app)
        response = client.get("/jobs")

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_get_job_found(self) -> None:
        app = _create_test_app()
        now = datetime.now(tz=UTC)
        app.state.job_repo = MagicMock()
        app.state.job_repo.find_by_id.return_value = Job(
            id="j1",
            job_type=JobType.INGEST,
            status=JobStatus.DONE,
            progress=100,
            progress_message="complete",
            params={"url": "https://example.com"},
            result={"run_id": "r1"},
            created_at=now,
        )

        client = TestClient(app)
        response = client.get("/jobs/j1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "j1"
        assert data["status"] == "done"

    def test_get_job_not_found(self) -> None:
        app = _create_test_app()
        app.state.job_repo = MagicMock()
        app.state.job_repo.find_by_id.return_value = None

        client = TestClient(app)
        response = client.get("/jobs/missing")

        assert response.status_code == 404
