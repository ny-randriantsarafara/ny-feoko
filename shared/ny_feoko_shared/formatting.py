"""Shared formatting utilities."""

from __future__ import annotations


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as human-readable (e.g. '1h 2m 5s')."""
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    parts: list[str] = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0:
        parts.append(f"{secs}s")
    return " ".join(parts)
