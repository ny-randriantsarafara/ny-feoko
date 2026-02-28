"""Tests for paginate_table."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from db_sync.pagination import PAGE_SIZE, paginate_table


def test_paginate_empty_table() -> None:
    """paginate_table returns empty list when table has no rows."""
    client = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.range.return_value.execute.return_value = MagicMock(data=[])
    client.table.return_value = chain

    result = paginate_table(client, "clips")

    assert result == []
    chain.range.assert_called_once_with(0, PAGE_SIZE - 1)


def test_paginate_single_batch() -> None:
    """paginate_table returns all rows when fewer than PAGE_SIZE."""
    client = MagicMock()
    rows = [{"id": "a"}, {"id": "b"}]
    chain = MagicMock()
    chain.select.return_value = chain
    chain.range.return_value.execute.return_value = MagicMock(data=rows)
    client.table.return_value = chain

    result = paginate_table(client, "clips")

    assert result == rows
    chain.range.assert_called_once_with(0, PAGE_SIZE - 1)


def test_paginate_multiple_batches() -> None:
    """paginate_table concatenates rows across multiple pages."""
    client = MagicMock()
    batch1 = [{"id": str(i)} for i in range(PAGE_SIZE)]
    batch2 = [{"id": str(i)} for i in range(500)]

    chain = MagicMock()
    chain.select.return_value = chain
    call_count = 0

    def range_side_effect(start: int, end: int) -> MagicMock:
        nonlocal call_count
        mock = MagicMock()
        call_count += 1
        if start == 0:
            mock.execute.return_value = MagicMock(data=batch1)
        else:
            mock.execute.return_value = MagicMock(data=batch2)
        return mock

    chain.range.side_effect = range_side_effect
    client.table.return_value = chain

    result = paginate_table(client, "clips")

    assert len(result) == PAGE_SIZE + 500
    assert chain.range.call_count == 2
    chain.range.assert_any_call(0, PAGE_SIZE - 1)
    chain.range.assert_any_call(PAGE_SIZE, PAGE_SIZE * 2 - 1)


def test_paginate_with_filters() -> None:
    """paginate_table applies eq filters to the query."""
    client = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.range.return_value.execute.return_value = MagicMock(data=[])
    client.table.return_value = chain

    paginate_table(
        client,
        "clips",
        columns="id,file_name",
        filters={"run_id": "run-123", "status": "corrected"},
    )

    chain.eq.assert_any_call("run_id", "run-123")
    chain.eq.assert_any_call("status", "corrected")
