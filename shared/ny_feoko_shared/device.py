"""Device detection for PyTorch (cuda, mps, cpu)."""

from __future__ import annotations

import torch


def detect_device(requested: str) -> str:
    """Resolve device string; when 'auto', pick cuda > mps > cpu."""
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
