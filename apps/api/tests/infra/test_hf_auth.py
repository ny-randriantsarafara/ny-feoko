from __future__ import annotations

import pytest

from infra.clients.ml import hf_auth


@pytest.fixture(autouse=True)
def reset_hf_auth_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hf_auth, "_is_authenticated", False)


def test_required_auth_raises_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        hf_auth.ensure_hf_auth(required=True)


def test_optional_auth_noop_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)

    hf_auth.ensure_hf_auth(required=False)


def test_login_called_once_across_multiple_ensure_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_TOKEN", "token-value")

    calls: list[str] = []

    def fake_login(token: str) -> None:
        calls.append(token)

    monkeypatch.setattr(hf_auth, "_huggingface_login", fake_login)

    hf_auth.ensure_hf_auth(required=True)
    hf_auth.ensure_hf_auth(required=True)
    hf_auth.ensure_hf_auth(required=False)

    assert calls == ["token-value"]
