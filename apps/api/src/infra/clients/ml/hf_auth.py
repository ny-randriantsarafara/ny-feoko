"""HuggingFace authentication helper."""

from __future__ import annotations

import os
import threading

HF_TOKEN_ENV_VAR = "HF_TOKEN"

_lock = threading.Lock()
_is_authenticated = False


def ensure_hf_auth(*, required: bool) -> None:
    """Authenticate with HuggingFace once per process when a token exists."""
    global _is_authenticated  # noqa: PLW0603

    if _is_authenticated:
        return

    token = os.getenv(HF_TOKEN_ENV_VAR, "").strip()
    if not token:
        if required:
            raise RuntimeError(
                "HuggingFace authentication is required but HF_TOKEN is not set. "
                "Set HF_TOKEN in the environment before continuing."
            )
        return

    with _lock:
        if _is_authenticated:
            return

        _huggingface_login(token)
        _is_authenticated = True


def _huggingface_login(token: str) -> None:
    from huggingface_hub import login

    login(token=token, add_to_git_credential=False)
