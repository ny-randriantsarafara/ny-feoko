"""Tests for resolve_run_id and resolve_label."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from db_sync.exceptions import RunNotFoundError
from db_sync.run_resolution import resolve_label, resolve_run_id


def test_resolve_run_id_returns_id_when_provided() -> None:
    """resolve_run_id returns run_id directly when provided."""
    client = MagicMock()
    result = resolve_run_id(client, run_id="run-123", label=None)
    assert result == "run-123"
    client.table.assert_not_called()


def test_resolve_run_id_raises_when_neither_provided() -> None:
    """resolve_run_id raises RunNotFoundError when neither run_id nor label given."""
    client = MagicMock()
    with pytest.raises(RunNotFoundError, match="Provide --run or --label"):
        resolve_run_id(client, run_id=None, label=None)


def test_resolve_run_id_by_label() -> None:
    """resolve_run_id looks up run by label and returns id."""
    client = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=[{"id": "resolved-uuid"}])
    client.table.return_value = chain

    result = resolve_run_id(client, run_id=None, label="my-run")

    assert result == "resolved-uuid"
    client.table.assert_called_once_with("runs")
    chain.eq.assert_called_with("label", "my-run")
    chain.order.assert_called_with("created_at", desc=True)
    chain.limit.assert_called_with(1)


def test_resolve_run_id_raises_when_label_not_found() -> None:
    """resolve_run_id raises RunNotFoundError when no run matches label."""
    client = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=[])
    client.table.return_value = chain

    with pytest.raises(RunNotFoundError, match="No run found with label 'unknown'"):
        resolve_run_id(client, run_id=None, label="unknown")


def test_resolve_label() -> None:
    """resolve_label returns label for given run_id."""
    client = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=[{"label": "my-run-label"}])
    client.table.return_value = chain

    result = resolve_label(client, "run-uuid-123")

    assert result == "my-run-label"
    client.table.assert_called_once_with("runs")
    chain.eq.assert_called_with("id", "run-uuid-123")


def test_resolve_label_raises_when_not_found() -> None:
    """resolve_label raises RunNotFoundError when run not found."""
    client = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=[])
    client.table.return_value = chain

    with pytest.raises(RunNotFoundError, match="No run found with id"):
        resolve_label(client, "unknown-id")
