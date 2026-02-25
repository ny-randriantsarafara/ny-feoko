"""Tests for TrainingConfig defaults and device-specific behavior."""

from __future__ import annotations

from asr_training.config import TrainingConfig


class TestTrainingConfigDefaults:
    def test_default_base_model(self) -> None:
        config = TrainingConfig()
        assert config.base_model == "openai/whisper-small"

    def test_default_language(self) -> None:
        config = TrainingConfig()
        assert config.language == "mg"

    def test_default_hyperparameters(self) -> None:
        config = TrainingConfig()
        assert config.epochs == 10
        assert config.batch_size == 4
        assert config.gradient_accumulation_steps == 2
        assert config.learning_rate == 1e-5
        assert config.warmup_ratio == 0.1

    def test_frozen(self) -> None:
        config = TrainingConfig()
        try:
            config.epochs = 20  # type: ignore[misc]
            raise AssertionError("Should have raised FrozenInstanceError")
        except AttributeError:
            pass

    def test_custom_overrides(self) -> None:
        config = TrainingConfig(epochs=5, batch_size=8, learning_rate=3e-5)
        assert config.epochs == 5
        assert config.batch_size == 8
        assert config.learning_rate == 3e-5


class TestFp16Detection:
    def test_cuda_uses_fp16(self) -> None:
        assert TrainingConfig.use_fp16("cuda") is True
        assert TrainingConfig.use_fp16("cuda:0") is True

    def test_mps_no_fp16(self) -> None:
        assert TrainingConfig.use_fp16("mps") is False

    def test_cpu_no_fp16(self) -> None:
        assert TrainingConfig.use_fp16("cpu") is False
