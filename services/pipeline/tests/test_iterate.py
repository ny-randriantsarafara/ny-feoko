"""Tests for the iterate pipeline orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.iterate import _ensure_source_dir, iterate


def _make_mock_client(
    run_source: str = "/fake/path",
    run_label: str = "test-run",
    run_id: str = "run-uuid-123",
) -> MagicMock:
    """Create a mock Supabase client for iterate tests."""
    client = MagicMock()

    runs_chain = MagicMock()
    runs_chain.select.return_value = runs_chain
    runs_chain.eq.return_value = runs_chain
    runs_chain.order.return_value = runs_chain
    runs_chain.limit.return_value = runs_chain
    runs_chain.execute.return_value = MagicMock(
        data=[{"id": run_id, "source": run_source, "label": run_label}]
    )

    client.table.return_value = runs_chain
    return client


class TestEnsureSourceDir:
    def test_uses_local_path_when_exists(self, tmp_path: Path) -> None:
        source_dir = tmp_path / "run"
        clips_dir = source_dir / "clips"
        clips_dir.mkdir(parents=True)

        client = _make_mock_client(run_source=str(source_dir))
        result = _ensure_source_dir(client, "run-uuid-123", "test-run")

        assert result == source_dir

    @patch("db_sync.sync.download_run_clips")
    def test_downloads_when_local_missing(
        self, mock_download: MagicMock, tmp_path: Path
    ) -> None:
        client = _make_mock_client(run_source="/nonexistent/path")

        result = _ensure_source_dir(client, "run-uuid-123", "test-run")

        mock_download.assert_called_once_with(
            client, "run-uuid-123", Path("data/output") / "test-run"
        )
        assert result == Path("data/output") / "test-run"


def _mock_status_counts() -> dict[str, int]:
    return {"pending": 10, "corrected": 5, "discarded": 2}


class TestIterate:
    @patch("pipeline.iterate._fetch_status_counts", return_value=_mock_status_counts())
    @patch("pipeline.iterate._redraft", return_value=3)
    @patch("pipeline.iterate._train")
    @patch("pipeline.iterate._export")
    @patch("pipeline.iterate._ensure_source_dir")
    @patch("pipeline.iterate.get_client")
    @patch("pipeline.iterate._resolve_run_id")
    def test_chains_export_train_redraft(
        self,
        mock_resolve: MagicMock,
        mock_get_client: MagicMock,
        mock_ensure: MagicMock,
        mock_export: MagicMock,
        mock_train: MagicMock,
        mock_redraft: MagicMock,
        mock_counts: MagicMock,  # noqa: ARG002
        tmp_path: Path,
    ) -> None:
        mock_resolve.return_value = "run-uuid-123"
        mock_get_client.return_value = MagicMock()
        mock_ensure.return_value = tmp_path / "source"
        mock_export.return_value = tmp_path / "training" / "dataset"
        mock_train.return_value = tmp_path / "model"

        result = iterate("test-run", "cpu")

        mock_export.assert_called_once()
        mock_train.assert_called_once()
        mock_redraft.assert_called_once()
        assert result == tmp_path / "model"

    @patch("pipeline.iterate._fetch_status_counts", return_value=_mock_status_counts())
    @patch("pipeline.iterate._redraft", return_value=3)
    @patch("pipeline.iterate._push")
    @patch("pipeline.iterate._train")
    @patch("pipeline.iterate._export")
    @patch("pipeline.iterate._ensure_source_dir")
    @patch("pipeline.iterate.get_client")
    @patch("pipeline.iterate._resolve_run_id")
    def test_pushes_to_hub_when_requested(
        self,
        mock_resolve: MagicMock,
        mock_get_client: MagicMock,
        mock_ensure: MagicMock,
        mock_export: MagicMock,
        mock_train: MagicMock,
        mock_push: MagicMock,
        mock_redraft: MagicMock,
        mock_counts: MagicMock,  # noqa: ARG002
        tmp_path: Path,
    ) -> None:
        mock_resolve.return_value = "run-uuid-123"
        mock_get_client.return_value = MagicMock()
        mock_ensure.return_value = tmp_path / "source"
        mock_export.return_value = tmp_path / "training" / "dataset"
        model_dir = tmp_path / "model"
        mock_train.return_value = model_dir

        iterate("test-run", "cpu", push_to_hub="user/whisper-mg")

        mock_push.assert_called_once_with(model_dir, "user/whisper-mg")
        mock_redraft.assert_called_once()
        redraft_kwargs = mock_redraft.call_args.kwargs
        assert redraft_kwargs["model_path"] == "user/whisper-mg"

    @patch("pipeline.iterate._fetch_status_counts", return_value=_mock_status_counts())
    @patch("pipeline.iterate._redraft", return_value=3)
    @patch("pipeline.iterate._train")
    @patch("pipeline.iterate._export")
    @patch("pipeline.iterate._ensure_source_dir")
    @patch("pipeline.iterate.get_client")
    @patch("pipeline.iterate._resolve_run_id")
    def test_passes_training_config(
        self,
        mock_resolve: MagicMock,
        mock_get_client: MagicMock,
        mock_ensure: MagicMock,
        mock_export: MagicMock,
        mock_train: MagicMock,
        mock_redraft: MagicMock,
        mock_counts: MagicMock,  # noqa: ARG002
        tmp_path: Path,
    ) -> None:
        mock_resolve.return_value = "run-uuid-123"
        mock_get_client.return_value = MagicMock()
        mock_ensure.return_value = tmp_path / "source"
        mock_export.return_value = tmp_path / "dataset"
        mock_train.return_value = tmp_path / "model"

        iterate(
            "test-run",
            "cuda",
            epochs=5,
            batch_size=8,
            lr=3e-5,
            base_model="openai/whisper-large-v3",
        )

        train_kwargs = mock_train.call_args.kwargs
        assert train_kwargs["epochs"] == 5
        assert train_kwargs["batch_size"] == 8
        assert train_kwargs["lr"] == 3e-5
        assert train_kwargs["base_model"] == "openai/whisper-large-v3"
        assert train_kwargs["device"] == "cuda"
