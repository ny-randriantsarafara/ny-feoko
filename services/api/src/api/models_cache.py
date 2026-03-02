"""Singleton cache for ML models — loaded once, reused across jobs."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from clip_extraction.domain.ports import ClassifierPort, TranscriberPort, VADPort

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
    global _instance
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
    from clip_extraction.infrastructure.classifier import ASTClassifier
    from clip_extraction.infrastructure.vad import SileroVAD

    vad = SileroVAD(threshold=vad_threshold)
    classifier = ASTClassifier(device=device)

    if whisper_hf:
        from clip_extraction.infrastructure.hf_transcriber import (
            HuggingFaceTranscriber,
        )

        transcriber = HuggingFaceTranscriber(model_id=whisper_hf, device=device)
    else:
        from clip_extraction.infrastructure.transcriber import WhisperTranscriber

        transcriber = WhisperTranscriber(model_name=whisper_model, device=device)

    return ModelCache(vad=vad, classifier=classifier, transcriber=transcriber)
