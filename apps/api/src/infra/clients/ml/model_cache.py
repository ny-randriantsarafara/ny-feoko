"""Process-local cache for ML models keyed by effective configuration."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from domain.ports.classifier import ClassifierPort
from domain.ports.transcriber import TranscriberPort
from domain.ports.vad import VADPort

logger = logging.getLogger(__name__)

_lock = threading.Lock()
CacheKey = tuple[str, float, str, str]
_instances: dict[CacheKey, ModelCache] = {}


@dataclass
class ModelCache:
    vad: VADPort
    classifier: ClassifierPort
    transcriber: TranscriberPort


def get_models(
    device: str,
    *,
    vad_threshold: float = 0.35,
    whisper_model: str = "small",
    whisper_hf: str = "",
) -> ModelCache:
    cache_key = _cache_key(
        device=device,
        vad_threshold=vad_threshold,
        whisper_model=whisper_model,
        whisper_hf=whisper_hf,
    )
    cached = _instances.get(cache_key)
    if cached is not None:
        return cached

    with _lock:
        cached = _instances.get(cache_key)
        if cached is not None:
            return cached

        logger.info("Loading ML models for cache key %s...", cache_key)
        models = _load_models(
            device,
            vad_threshold=vad_threshold,
            whisper_model=whisper_model,
            whisper_hf=whisper_hf,
        )
        _instances[cache_key] = models
        logger.info("ML models loaded and cached for key %s.", cache_key)
        return models


def clear_models() -> bool:
    """Clear all cached ML models in the current process.

    Returns True when at least one cached entry existed and was cleared.
    """
    with _lock:
        had_instances = bool(_instances)
        _instances.clear()

    if had_instances:
        logger.info("ML model cache cleared.")
    else:
        logger.info("ML model cache already empty.")

    return had_instances


def _cache_key(
    *,
    device: str,
    vad_threshold: float,
    whisper_model: str,
    whisper_hf: str,
) -> CacheKey:
    if whisper_hf:
        whisper_model = ""
    return (device, vad_threshold, whisper_model, whisper_hf)


def _load_models(
    device: str,
    *,
    vad_threshold: float,
    whisper_model: str,
    whisper_hf: str,
) -> ModelCache:
    from infra.clients.ml.classifier import ASTClassifier
    from infra.clients.ml.vad import SileroVAD

    vad = SileroVAD(threshold=vad_threshold)
    classifier = ASTClassifier(device=device)

    if whisper_hf:
        from infra.clients.ml.hf_auth import ensure_hf_auth
        from infra.clients.ml.hf_transcriber import HuggingFaceTranscriber

        ensure_hf_auth(required=False)
        transcriber = HuggingFaceTranscriber(model_id=whisper_hf, device=device)
    else:
        from infra.clients.ml.transcriber import WhisperTranscriber

        transcriber = WhisperTranscriber(model_name=whisper_model, device=device)

    return ModelCache(vad=vad, classifier=classifier, transcriber=transcriber)
