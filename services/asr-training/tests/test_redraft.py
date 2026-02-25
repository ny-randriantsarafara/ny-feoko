"""Tests for re-draft logic with mocked Supabase and model."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from asr_training.redraft import _fetch_pending_clips, redraft_pending

SAMPLE_RATE = 16_000


@pytest.fixture
def clips_dir(tmp_path: Path) -> Path:
    """Create a temporary clips directory with two WAV files."""
    clips = tmp_path / "clips"
    clips.mkdir()

    for name in ("clip_001.wav", "clip_002.wav"):
        audio = np.random.default_rng(42).standard_normal(SAMPLE_RATE * 5).astype(np.float32)
        sf.write(str(clips / name), audio, SAMPLE_RATE)

    return tmp_path


@pytest.fixture
def mock_supabase() -> MagicMock:
    client = MagicMock()

    pending_data = [
        {"id": "aaa-111", "file_name": "clips/clip_001.wav"},
        {"id": "bbb-222", "file_name": "clips/clip_002.wav"},
    ]

    select_mock = MagicMock()
    select_mock.eq.return_value = select_mock
    select_mock.range.return_value = select_mock
    select_mock.execute.return_value = MagicMock(data=pending_data)

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock

    update_chain = MagicMock()
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock()
    table_mock.update.return_value = update_chain

    client.table.return_value = table_mock
    return client


class TestFetchPendingClips:
    def test_returns_pending_clips(self, mock_supabase: MagicMock) -> None:
        clips = _fetch_pending_clips(mock_supabase, "run-123")

        assert len(clips) == 2
        assert clips[0]["file_name"] == "clips/clip_001.wav"
        assert clips[1]["file_name"] == "clips/clip_002.wav"

    def test_queries_correct_run_and_status(self, mock_supabase: MagicMock) -> None:
        _fetch_pending_clips(mock_supabase, "run-123")

        table_mock = mock_supabase.table.return_value
        table_mock.select.assert_called_once_with("id,file_name")

        eq_calls = table_mock.select.return_value.eq.call_args_list
        assert eq_calls[0].args == ("run_id", "run-123")
        assert eq_calls[1].args == ("status", "pending")


class TestRedraftPending:
    @patch("asr_training.redraft.WhisperProcessor")
    @patch("asr_training.redraft.WhisperForConditionalGeneration")
    def test_updates_draft_transcription(
        self,
        mock_model_cls: MagicMock,
        mock_proc_cls: MagicMock,
        clips_dir: Path,
        mock_supabase: MagicMock,
    ) -> None:
        mock_processor = MagicMock()
        mock_proc_cls.from_pretrained.return_value = mock_processor
        mock_processor.get_decoder_prompt_ids.return_value = []
        mock_processor.return_value = MagicMock(
            input_features=MagicMock(to=MagicMock(return_value=MagicMock()))
        )
        mock_processor.batch_decode.return_value = ["Teny vaovao"]

        mock_model = MagicMock()
        mock_model_cls.from_pretrained.return_value = mock_model
        mock_model.to.return_value = mock_model
        mock_model.eval.return_value = mock_model
        mock_model.generate.return_value = MagicMock()

        updated = redraft_pending(
            client=mock_supabase,
            model_path="fake-model",
            source_dir=clips_dir,
            run_id="run-123",
            device="cpu",
        )

        assert updated == 2

        update_calls = mock_supabase.table.return_value.update.call_args_list
        assert len(update_calls) == 2
        for call in update_calls:
            assert "draft_transcription" in call.args[0]
