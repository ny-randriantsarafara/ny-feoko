"""Singleton cache for ML models -- loaded once, reused across jobs."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from domain.ports.classifier import ClassifierPort
from domain.ports.transcriber import TranscriberPort
from domain.ports.vad import VADPort

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_instance: ModelCache | None = None


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
    global _instance  # noqa: PLW0603
    if _instance is not None:
        return _instance

    with _lock:
        if _instance is not None:
            return _instance

        logger.info("Loading ML models (first request)...")
        _instance = _load_models(
            device,
            vad_threshold=vad_threshold,
            whisper_model=whisper_model,
            whisper_hf=whisper_hf,
        )
        logger.info("ML models loaded and cached.")
        return _instance


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
        from infra.clients.ml.hf_transcriber import HuggingFaceTranscriber

        transcriber = HuggingFaceTranscriber(model_id=whisper_hf, device=device)
    else:
        from infra.clients.ml.transcriber import WhisperTranscriber

        transcriber = WhisperTranscriber(model_name=whisper_model, device=device)

    return ModelCache(vad=vad, classifier=classifier, transcriber=transcriber)
