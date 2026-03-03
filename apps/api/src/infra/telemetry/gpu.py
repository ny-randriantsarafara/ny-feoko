"""GPU monitoring utilities."""

from __future__ import annotations

import torch


def get_gpu_memory_info() -> dict:
    """Get current GPU memory usage.

    Returns:
        Dict with keys: available, name, used_gb, total_gb, percent
        If no GPU, only 'available': False is returned.
    """
    if not torch.cuda.is_available():
        return {"available": False}

    device = torch.cuda.current_device()
    name = torch.cuda.get_device_name(device)
    used = torch.cuda.memory_allocated(device)
    total = torch.cuda.get_device_properties(device).total_memory

    used_gb = used / (1024**3)
    total_gb = total / (1024**3)
    percent = (used / total) * 100 if total > 0 else 0

    return {
        "available": True,
        "name": name,
        "used_gb": round(used_gb, 2),
        "total_gb": round(total_gb, 2),
        "percent": round(percent, 1),
    }


def format_gpu_memory(info: dict) -> str:
    """Format GPU memory info as a human-readable string."""
    if not info.get("available"):
        return "GPU: Not available"

    return (
        f"GPU: {info['name']}, "
        f"VRAM: {info['used_gb']:.1f}GB / {info['total_gb']:.1f}GB "
        f"({info['percent']:.0f}%)"
    )
