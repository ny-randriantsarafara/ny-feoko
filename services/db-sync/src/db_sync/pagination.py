"""Shared pagination for Supabase table queries."""

from __future__ import annotations

from typing import Any

PAGE_SIZE = 1000


def paginate_table(
    client: Any,
    table: str,
    columns: str = "*",
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Fetch all rows from a Supabase table with pagination.

    Args:
        client: Supabase Client.
        table: Table name.
        columns: Comma-separated column names or "*".
        filters: Optional eq filters, e.g. {"run_id": "x", "status": "corrected"}.

    Returns:
        All rows concatenated from paginated queries.
    """
    all_rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        query = client.table(table).select(columns)
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        result = query.range(offset, offset + PAGE_SIZE - 1).execute()
        batch = result.data or []
        all_rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return all_rows
