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


@app.command("delete-run")
def delete_run_cmd(
    run: Optional[str] = typer.Option(None, "--run", help="Run UUID"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Run label (uses most recent match)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a run and all its clips, edits, and storage files."""
    from db_sync.supabase_client import get_client
    from db_sync.export import _resolve_run_id
    from db_sync.manage import delete_run

    client = get_client()
    run_id = _resolve_run_id(client, run_id=run, label=label)

    if not yes:
        from db_sync.manage import _fetch_run, _count_clips

        run_data = _fetch_run(client, run_id)
        total, corrected = _count_clips(client, run_id)
        typer.echo(f"Run:       {run_data['label']}  ({run_id})")
        typer.echo(f"Clips:     {total}  ({corrected} corrected)")
        typer.confirm("Delete this run and all associated data?", abort=True)

    delete_run(client, run_id)


@app.command("reset")
def reset_cmd(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Wipe all runs, clips, edits, and storage. Irreversible."""
    from db_sync.supabase_client import get_client
    from db_sync.manage import reset_all, _count_table

    client = get_client()

    if not yes:
        run_count = _count_table(client, "runs")
        clip_count = _count_table(client, "clips")
        edit_count = _count_table(client, "clip_edits")
        typer.echo(f"This will permanently delete:")
        typer.echo(f"  {run_count} runs, {clip_count} clips, {edit_count} edits")
        typer.echo(f"  All storage objects in the clips bucket")
        typer.confirm("Proceed?", abort=True)

    reset_all(client)


@app.command("cleanup")
def cleanup_cmd(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Remove orphaned data: empty runs and unlinked storage files."""
    from db_sync.supabase_client import get_client
    from db_sync.manage import cleanup, _find_empty_runs, _find_orphan_storage_prefixes

    client = get_client()
    empty_runs = _find_empty_runs(client)
    orphan_prefixes = _find_orphan_storage_prefixes(client)

    if not empty_runs and not orphan_prefixes:
        typer.echo("No orphans found.")
        return

    if empty_runs:
        typer.echo(f"Empty runs ({len(empty_runs)}):")
        for r in empty_runs:
            typer.echo(f"  - {r['label']}  ({r['id']})")

    if orphan_prefixes:
        typer.echo(f"Orphan storage prefixes ({len(orphan_prefixes)}):")
        for p in orphan_prefixes:
            typer.echo(f"  - {p}")

    if not yes:
        typer.confirm("Remove all orphans?", abort=True)

    cleanup(client, empty_runs, orphan_prefixes)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
