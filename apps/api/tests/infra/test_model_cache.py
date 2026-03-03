from __future__ import annotations

from typing import Any

import pytest

from infra.clients.ml import model_cache


@pytest.fixture(autouse=True)
def reset_model_cache() -> None:
    model_cache.clear_models()


def test_get_models_reuses_cached_entry_for_same_effective_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, float, str, str]] = []

    def fake_load_models(
        device: str,
        *,
        vad_threshold: float,
        whisper_model: str,
        whisper_hf: str,
    ) -> model_cache.ModelCache:
        calls.append((device, vad_threshold, whisper_model, whisper_hf))
        token = len(calls)
        return model_cache.ModelCache(
            vad=cast_any(("vad", token)),
            classifier=cast_any(("classifier", token)),
            transcriber=cast_any(("transcriber", token)),
        )

    monkeypatch.setattr(model_cache, "_load_models", fake_load_models)

    first = model_cache.get_models(
        "cpu",
        vad_threshold=0.2,
        whisper_model="small",
        whisper_hf="",
    )
    second = model_cache.get_models(
        "cpu",
        vad_threshold=0.2,
        whisper_model="small",
        whisper_hf="",
    )

    assert first is second
    assert calls == [("cpu", 0.2, "small", "")]


def test_get_models_loads_fresh_entry_when_effective_config_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, float, str, str]] = []

    def fake_load_models(
        device: str,
        *,
        vad_threshold: float,
        whisper_model: str,
        whisper_hf: str,
    ) -> model_cache.ModelCache:
        calls.append((device, vad_threshold, whisper_model, whisper_hf))
        token = len(calls)
        return model_cache.ModelCache(
            vad=cast_any(("vad", token)),
            classifier=cast_any(("classifier", token)),
            transcriber=cast_any(("transcriber", token)),
        )

    monkeypatch.setattr(model_cache, "_load_models", fake_load_models)

    base = model_cache.get_models("cpu", vad_threshold=0.35, whisper_model="small", whisper_hf="")
    by_device = model_cache.get_models(
        "cuda",
        vad_threshold=0.35,
        whisper_model="small",
        whisper_hf="",
    )
    by_threshold = model_cache.get_models(
        "cpu",
        vad_threshold=0.6,
        whisper_model="small",
        whisper_hf="",
    )
    by_model = model_cache.get_models(
        "cpu",
        vad_threshold=0.35,
        whisper_model="medium",
        whisper_hf="",
    )
    by_hf = model_cache.get_models(
        "cpu",
        vad_threshold=0.35,
        whisper_model="small",
        whisper_hf="org/whisper-custom",
    )

    assert len(calls) == 5
    assert base is not by_device
    assert base is not by_threshold
    assert base is not by_model
    assert base is not by_hf


def test_clear_models_returns_whether_any_cached_entry_existed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, float, str, str]] = []

    def fake_load_models(
        device: str,
        *,
        vad_threshold: float,
        whisper_model: str,
        whisper_hf: str,
    ) -> model_cache.ModelCache:
        calls.append((device, vad_threshold, whisper_model, whisper_hf))
        token = len(calls)
        return model_cache.ModelCache(
            vad=cast_any(("vad", token)),
            classifier=cast_any(("classifier", token)),
            transcriber=cast_any(("transcriber", token)),
        )

    monkeypatch.setattr(model_cache, "_load_models", fake_load_models)

    assert model_cache.clear_models() is False

    model_cache.get_models("cpu")
    model_cache.get_models("cuda")

    assert model_cache.clear_models() is True
    assert model_cache.clear_models() is False


def test_get_models_hf_mode_ignores_whisper_model_in_cache_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, float, str, str]] = []

    def fake_load_models(
        device: str,
        *,
        vad_threshold: float,
        whisper_model: str,
        whisper_hf: str,
    ) -> model_cache.ModelCache:
        calls.append((device, vad_threshold, whisper_model, whisper_hf))
        token = len(calls)
        return model_cache.ModelCache(
            vad=cast_any(("vad", token)),
            classifier=cast_any(("classifier", token)),
            transcriber=cast_any(("transcriber", token)),
        )

    monkeypatch.setattr(model_cache, "_load_models", fake_load_models)

    first = model_cache.get_models(
        "cpu",
        vad_threshold=0.35,
        whisper_model="small",
        whisper_hf="org/whisper-custom",
    )
    second = model_cache.get_models(
        "cpu",
        vad_threshold=0.35,
        whisper_model="large-v3",
        whisper_hf="org/whisper-custom",
    )

    assert first is second
    assert len(calls) == 1


def cast_any(value: object) -> Any:
    return value


def test_load_models_whisper_hf_uses_optional_hf_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from infra.clients.ml import hf_auth, hf_transcriber

    auth_calls: list[bool] = []

    class FakeSileroVAD:
        def __init__(self, *, threshold: float) -> None:
            self.threshold = threshold

    class FakeASTClassifier:
        def __init__(self, *, device: str) -> None:
            self.device = device

    class FakeHuggingFaceTranscriber:
        def __init__(self, *, model_id: str, device: str) -> None:
            self.model_id = model_id
            self.device = device

    def fake_ensure_hf_auth(*, required: bool) -> None:
        auth_calls.append(required)

    monkeypatch.setattr("infra.clients.ml.vad.SileroVAD", FakeSileroVAD)
    monkeypatch.setattr("infra.clients.ml.classifier.ASTClassifier", FakeASTClassifier)
    monkeypatch.setattr(hf_transcriber, "HuggingFaceTranscriber", FakeHuggingFaceTranscriber)
    monkeypatch.setattr(hf_auth, "ensure_hf_auth", fake_ensure_hf_auth)

    models = model_cache._load_models(
        "cpu",
        vad_threshold=0.35,
        whisper_model="small",
        whisper_hf="org/whisper-public",
    )

    assert isinstance(models.transcriber, FakeHuggingFaceTranscriber)
    assert auth_calls == [False]
