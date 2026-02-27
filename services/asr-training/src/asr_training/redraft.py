"""Re-transcribe pending clips using a fine-tuned Whisper model."""

from __future__ import annotations

from pathlib import Path

import soundfile as sf
import torch
from rich.console import Console
from rich.progress import Progress
from supabase import Client
from transformers import WhisperForConditionalGeneration, WhisperProcessor

console = Console()

SAMPLE_RATE = 16_000


def redraft_pending(
    client: Client,
    model_path: str,
    source_dir: Path,
    run_id: str,
    device: str,
    language: str = "mg",
) -> int:
    """Re-transcribe pending clips and update draft_transcription in Supabase.

    Returns the number of clips updated.
    """
    console.print(f"Loading model from [bold]{model_path}[/]...")
    processor = WhisperProcessor.from_pretrained(model_path)
    model = WhisperForConditionalGeneration.from_pretrained(model_path)
    model.to(device).eval()

    forced_decoder_ids = processor.get_decoder_prompt_ids(
        language=language, task="transcribe"
    )

    pending_clips = _fetch_pending_clips(client, run_id)
    if not pending_clips:
        console.print("[yellow]No pending clips found.[/]")
        return 0

    total_pending = len(pending_clips)
    console.print(f"Re-drafting [bold]{total_pending}[/] pending clips...")
    updated = 0
    skipped = 0

    with Progress(console=console) as progress:
        task = progress.add_task("Transcribing", total=total_pending)

        for clip in pending_clips:
            file_name = clip["file_name"]
            wav_path = source_dir / file_name

            if not wav_path.exists():
                console.print(f"[yellow]Skipping {file_name} (file not found)[/]")
                skipped += 1
                progress.advance(task)
                continue

            new_text = _transcribe_clip(
                wav_path, processor, model, device, forced_decoder_ids
            )

            client.table("clips").update(
                {"draft_transcription": new_text}
            ).eq("id", clip["id"]).execute()

            updated += 1
            progress.advance(task)

    console.print(f"[bold green]Updated {updated} clips[/]")

    if skipped > 0:
        console.print(f"[yellow]Skipped {skipped} clips (file not found)[/]")

    remaining = total_pending - updated - skipped
    if remaining > 0:
        console.print(f"  Remaining pending: {remaining}")

    est_minutes = updated * 0.5
    console.print(
        f"  Estimated correction time: ~{est_minutes:.0f} min "
        f"(at ~30s per clip)"
    )

    return updated


def _transcribe_clip(
    wav_path: Path,
    processor: WhisperProcessor,
    model: WhisperForConditionalGeneration,
    device: str,
    forced_decoder_ids: list[tuple[int, int]],
) -> str:
    audio, sr = sf.read(str(wav_path), dtype="float32")
    if sr != SAMPLE_RATE:
        raise SystemExit(
            f"Expected {SAMPLE_RATE}Hz audio, got {sr}Hz in {wav_path}"
        )

    inputs = processor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
    input_features = inputs.input_features.to(device)

    with torch.no_grad():
        predicted_ids = model.generate(
            input_features,
            forced_decoder_ids=forced_decoder_ids,
            max_new_tokens=444,  # 448 - 4 to leave room for decoder start tokens
        )

    return processor.batch_decode(
        predicted_ids, skip_special_tokens=True
    )[0].strip()


def _fetch_pending_clips(
    client: Client, run_id: str
) -> list[dict[str, str]]:
    """Fetch all pending clips for a run, paginated."""
    all_rows: list[dict[str, str]] = []
    page_size = 1000
    offset = 0

    while True:
        result = (
            client.table("clips")
            .select("id,file_name")
            .eq("run_id", run_id)
            .eq("status", "pending")
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
