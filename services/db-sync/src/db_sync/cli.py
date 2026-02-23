"""CLI for syncing extraction runs to Supabase and exporting corrected data."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Ambara DB sync — push extraction runs to Supabase and export corrections.")


@app.command()
def sync(
    dir: Path = typer.Option(..., "--dir", "-d", help="Path to extraction run directory"),
    label: str = typer.Option("", "--label", "-l", help="Run label (defaults to directory name)"),
) -> None:
    """Upload clips and metadata from a local extraction run to Supabase."""
    from db_sync.supabase_client import get_client
    from db_sync.sync import sync_run

    resolved_dir = dir.resolve()
    if not resolved_dir.is_dir():
        raise typer.BadParameter(f"Directory not found: {resolved_dir}")

    resolved_label = label or resolved_dir.name
    client = get_client()
    sync_run(client, resolved_dir, resolved_label)


@app.command("export")
def export_cmd(
    run: Optional[str] = typer.Option(None, "--run", help="Run UUID"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Run label (uses most recent match)"),
    output: Path = typer.Option(
        "metadata.corrected.csv", "--output", "-o", help="Output CSV path"
    ),
) -> None:
    """Export corrected clips to CSV for training."""
    from db_sync.supabase_client import get_client
    from db_sync.export import export_corrected

    client = get_client()
    export_corrected(client, run_id=run, label=label, output=output)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
