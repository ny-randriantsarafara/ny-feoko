"""Dump all Supabase table data as SQL INSERT statements for backup."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from supabase import Client

console = Console()

TABLES = ["runs", "clips", "clip_edits"]


def dump_database(client: Client, output: Path) -> None:
    """Export all rows from runs, clips, and clip_edits as SQL INSERT statements."""
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w") as f:
        f.write(f"-- Ambara database dump — {datetime.now(tz=UTC).isoformat()}\n")
        f.write("-- Restore by running this file in the Supabase SQL editor.\n\n")
        f.write("BEGIN;\n\n")

        for table in TABLES:
            rows = _fetch_all_rows(client, table)
            f.write(f"-- {table}: {len(rows)} rows\n")

            for row in rows:
                columns = ", ".join(row.keys())
                values = ", ".join(_sql_literal(v) for v in row.values())
                f.write(f"INSERT INTO {table} ({columns}) VALUES ({values})"
                        f" ON CONFLICT DO NOTHING;\n")

            f.write("\n")

        f.write("COMMIT;\n")

    total = sum(
        len(_fetch_all_rows(client, t)) for t in TABLES
    )
    console.print(f"[bold green]Dumped {total} rows across {len(TABLES)} tables to {output}[/]")


def _fetch_all_rows(client: Client, table: str) -> list[dict[str, object]]:
    """Paginate through all rows in a table."""
    all_rows: list[dict[str, object]] = []
    page_size = 1000
    offset = 0

    while True:
        result = (
            client.table(table)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        all_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    return all_rows


def _sql_literal(value: object) -> str:
    """Convert a Python value to a SQL literal string."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"
