"""Tests for REST API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.use_cases.ingest_run import IngestRun
from domain.entities.job import Job, JobStatus, JobType
from domain.entities.run import Run, RunType
from ports.rest.routes.export import router as export_router
from ports.rest.routes.ingest import router as ingest_router
from ports.rest.routes.jobs import router as jobs_router
from ports.rest.routes.metrics import router as metrics_router
from ports.rest.routes.redraft import router as redraft_router
from ports.rest.routes.runs import router as runs_router


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(runs_router)
    app.include_router(ingest_router)
    app.include_router(export_router)
    app.include_router(redraft_router)
    app.include_router(jobs_router)
    app.include_router(metrics_router)
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


class TestMonitoringRoutes:
    def test_health_returns_healthy(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_metrics_returns_prometheus_format(self) -> None:
        app = _create_test_app()
        client = TestClient(app)
        response = client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


class TestIngestRoute:
    def test_ingest_allows_missing_label_via_canonical_schema(self) -> None:
        app = _create_test_app()
        app.state.settings = SimpleNamespace(device="cpu", input_dir="in", output_dir="out")
        app.state.job_repo = MagicMock()
        app.state.job_repo.create.return_value = "job-124"
        app.state.ingest_downloader = MagicMock()
        app.state.sync = MagicMock()
        app.state.executor = MagicMock()

        models = SimpleNamespace(vad=object(), classifier=object(), transcriber=object())
        with patch("ports.rest.routes.ingest.get_models", return_value=models):
            client = TestClient(app)
            response = client.post("/ingest", json={"url": "https://example.com/audio"})

        assert response.status_code == 200
        assert response.json() == {"job_id": "job-124"}
        app.state.job_repo.create.assert_called_once_with(
            "ingest",
            {
                "url": "https://example.com/audio",
                "label": "",
                "whisper_model": "small",
                "whisper_hf": None,
                "vad_threshold": 0.35,
                "speech_threshold": 0.35,
            },
        )

    def test_ingest_creates_job_and_dispatches_with_normalized_request(self) -> None:
        app = _create_test_app()
        app.state.settings = SimpleNamespace(device="cpu", input_dir="in", output_dir="out")
        app.state.job_repo = MagicMock()
        app.state.job_repo.create.return_value = "job-123"
        app.state.ingest_downloader = MagicMock()
        app.state.sync = MagicMock()
        app.state.ingest = MagicMock()
        app.state.executor = MagicMock()

        models = SimpleNamespace(vad=object(), classifier=object(), transcriber=object())
        with patch("ports.rest.routes.ingest.get_models", return_value=models) as get_models_mock:
            client = TestClient(app)
            response = client.post(
                "/ingest",
                json={
                    "url": "  https://example.com/audio  ",
                    "label": "  my run  ",
                    "whisper_model": "small",
                    "whisper_hf": "   ",
                    "vad_threshold": 0.4,
                    "speech_threshold": 0.45,
                },
            )

        assert response.status_code == 200
        assert response.json() == {"job_id": "job-123"}
        get_models_mock.assert_called_once_with(
            "cpu",
            vad_threshold=0.4,
            whisper_model="small",
            whisper_hf="",
        )
        app.state.job_repo.create.assert_called_once_with(
            "ingest",
            {
                "url": "https://example.com/audio",
                "label": "my run",
                "whisper_model": "small",
                "whisper_hf": None,
                "vad_threshold": 0.4,
                "speech_threshold": 0.45,
            },
        )
        app.state.executor.submit.assert_called_once()
        submitted_use_case = app.state.executor.submit.call_args.args[1]
        assert isinstance(submitted_use_case, IngestRun)
        assert submitted_use_case is not app.state.ingest

    def test_ingest_validation_error_for_invalid_threshold(self) -> None:
        app = _create_test_app()
        app.state.settings = SimpleNamespace(device="cpu", input_dir="in", output_dir="out")
        app.state.job_repo = MagicMock()
        app.state.ingest = MagicMock()
        app.state.executor = MagicMock()

        client = TestClient(app)
        response = client.post(
            "/ingest",
            json={
                "url": "https://example.com/audio",
                "label": "run",
                "vad_threshold": 1.2,
            },
        )

        assert response.status_code == 422


class TestExportRoute:
    def test_export_uses_request_output_when_provided(self) -> None:
        app = _create_test_app()
        app.state.settings = SimpleNamespace(output_dir="data/from-settings")
        app.state.export = MagicMock()
        app.state.export.execute.return_value = "tmp/custom/dataset"

        client = TestClient(app)
        response = client.post(
            "/export",
            json={
                "run_ids": ["run-1"],
                "output": "tmp/custom",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"dataset_dir": "tmp/custom/dataset"}
        app.state.export.execute.assert_called_once_with(
            ["run-1"],
            Path("tmp/custom"),
            eval_split=0.1,
        )

    def test_export_uses_settings_output_when_omitted(self) -> None:
        app = _create_test_app()
        app.state.settings = SimpleNamespace(output_dir="data/from-settings")
        app.state.export = MagicMock()
        app.state.export.execute.return_value = "data/from-settings/dataset"

        client = TestClient(app)
        response = client.post(
            "/export",
            json={
                "run_ids": ["  run-1  ", "run-2"],
                "eval_split": 0.2,
            },
        )

        assert response.status_code == 200
        assert response.json() == {"dataset_dir": "data/from-settings/dataset"}
        app.state.export.execute.assert_called_once_with(
            ["run-1", "run-2"],
            Path("data/from-settings"),
            eval_split=0.2,
        )

    def test_export_validation_error_for_empty_run_ids(self) -> None:
        app = _create_test_app()
        app.state.settings = SimpleNamespace(output_dir="data/from-settings")
        app.state.export = MagicMock()

        client = TestClient(app)
        response = client.post("/export", json={"run_ids": []})

        assert response.status_code == 422


class TestRedraftRoute:
    def test_redraft_creates_job_and_dispatches_with_settings_device(self) -> None:
        app = _create_test_app()
        app.state.settings = SimpleNamespace(device="mps")
        app.state.job_repo = MagicMock()
        app.state.job_repo.create.return_value = "job-redraft"
        app.state.redraft = MagicMock()
        app.state.executor = MagicMock()

        client = TestClient(app)
        response = client.post(
            "/redraft",
            json={
                "run_ids": [" run-1 "],
                "model_path": "  hf/model  ",
                "language": " fr ",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"job_id": "job-redraft"}
        app.state.job_repo.create.assert_called_once_with(
            "redraft",
            {
                "run_ids": ["run-1"],
                "model_path": "hf/model",
                "device": "mps",
                "language": "fr",
            },
        )
        app.state.executor.submit.assert_called_once()

    def test_redraft_validation_error_for_invalid_run_ids(self) -> None:
        app = _create_test_app()
        app.state.settings = SimpleNamespace(device="mps")
        app.state.job_repo = MagicMock()
        app.state.redraft = MagicMock()
        app.state.executor = MagicMock()

        client = TestClient(app)
        response = client.post(
            "/redraft",
            json={"run_ids": [""], "model_path": "model.bin"},
        )

        assert response.status_code == 422
