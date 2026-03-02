"""Supabase client factory, configured from environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

from domain.exceptions import MissingConfigError


def get_client() -> Client:
    """Create a Supabase client using service role key from environment."""
    _load_env()

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        raise MissingConfigError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.\n"
            "Set them in .env at the repo root or export them."
        )

    return create_client(url, key)


def _load_env() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    dotenv_path = repo_root / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
