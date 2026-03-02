"""Audio Spectrogram Transformer classifier for speech vs music/singing."""

from __future__ import annotations

import numpy as np
import torch
from transformers import ASTForAudioClassification, AutoFeatureExtractor

from domain.ports.classifier import ClassifierPort

SPEECH_LABELS = {
    "Speech",
    "Male speech, man speaking",
    "Female speech, woman speaking",
    "Narration, monologue",
    "Conversation",
    "Whispering",
}
MUSIC_LABELS = {
    "Singing",
    "Choir",
    "Chant",
    "Music",
    "Gospel music",
    "Christian music",
    "Organ",
    "Hymn",
}


class ASTClassifier(ClassifierPort):
    MODEL_ID = "MIT/ast-finetuned-audioset-10-10-0.4593"

    def __init__(self, device: str = "mps") -> None:
        self.extractor = AutoFeatureExtractor.from_pretrained(self.MODEL_ID)
        self.model = ASTForAudioClassification.from_pretrained(self.MODEL_ID)
        self.model.to(device).eval()
        self.id2label: dict[int, str] = self.model.config.id2label
        self.device = device

        self._speech_ids = {i for i, label in self.id2label.items() if label in SPEECH_LABELS}
        self._music_ids = {i for i, label in self.id2label.items() if label in MUSIC_LABELS}

    def classify(self, audio: np.ndarray, sample_rate: int) -> tuple[float, float]:
        window = sample_rate * 10
        if len(audio) > window:
            scores = [
                self._classify_window(audio[i : i + window], sample_rate)
                for i in range(0, len(audio) - window + 1, window // 2)
            ]
            return max(s[0] for s in scores), max(s[1] for s in scores)
        return self._classify_window(audio, sample_rate)

    def _classify_window(self, audio: np.ndarray, sr: int) -> tuple[float, float]:
        inputs = self.extractor(audio, sampling_rate=sr, return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probs = torch.sigmoid(logits[0]).cpu()

        speech = max((float(probs[i]) for i in self._speech_ids), default=0.0)
        music = max((float(probs[i]) for i in self._music_ids), default=0.0)
        return speech, music
