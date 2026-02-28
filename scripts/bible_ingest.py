"""Download Bible chapter audio and ingest into Supabase.

Reads baiboly.json from Phase 1, downloads chapter mp3s, converts to wav,
and creates one run + one unsplit clip per chapter in Supabase.
Paragraph splitting is done manually in the editor.

Usage:
    python scripts/bible_ingest.py [--output-dir data/bible] [--book at01] [--dry-run]
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://nybaiboly.net/"
REQUEST_DELAY_SEC = 1.0
SAMPLE_RATE = 16000


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class VerseData(TypedDict):
    verse: int
    text: str


class ParagraphData(TypedDict):
    heading: str | None
    verses: list[VerseData]


class ChapterData(TypedDict):
    chapter: int
    audio_url: str | None
    paragraphs: list[ParagraphData]


class BookData(TypedDict):
    code: str
    name_mg: str
    name_fr: str
    chapters: list[ChapterData]


class TestamentData(TypedDict):
    name: str
    books: list[BookData]


class BaibolyData(TypedDict):
    testaments: list[TestamentData]


@dataclass(frozen=True)
class ChapterResult:
    book_code: str
    book_name_mg: str
    chapter_number: int
    audio_url: str | None
    wav_path: Path
    has_audio: bool
    paragraphs: list[dict[str, str | None]]
    full_transcript: str


# ---------------------------------------------------------------------------
# Audio download + conversion
# ---------------------------------------------------------------------------


def download_mp3(
    client: httpx.Client,
    url: str,
    dest: Path,
) -> bool:
    """Download an mp3 file. Returns True if downloaded, False if skipped."""
    if dest.exists() and dest.stat().st_size > 0:
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    response = client.get(url, follow_redirects=True, timeout=60.0)
    response.raise_for_status()
    dest.write_bytes(response.content)
    return True


def convert_mp3_to_wav(mp3_path: Path, wav_path: Path) -> None:
    """Convert mp3 to 16kHz mono wav using ffmpeg."""
    if wav_path.exists() and wav_path.stat().st_size > 0:
        return

    wav_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(mp3_path),
            "-ar", str(SAMPLE_RATE), "-ac", "1",
            str(wav_path),
        ],
        check=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _paragraph_to_text(paragraph: ParagraphData) -> str:
    verses = " ".join(v["text"] for v in paragraph["verses"])
    heading = paragraph.get("heading")
    if heading:
        return f"{heading} {verses}"
    return verses


def _build_paragraph_meta(
    paragraphs: list[ParagraphData],
) -> list[dict[str, str | None]]:
    return [
        {
            "heading": p.get("heading"),
            "text": _paragraph_to_text(p),
        }
        for p in paragraphs
    ]


# ---------------------------------------------------------------------------
# Chapter processing
# ---------------------------------------------------------------------------


def process_chapter(
    client: httpx.Client,
    book: BookData,
    chapter: ChapterData,
    audio_dir: Path,
    skip_download: bool,
) -> ChapterResult:
    """Download and convert a single chapter. No alignment."""
    book_code = book["code"]
    chapter_num = chapter["chapter"]
    chapter_str = str(chapter_num).zfill(2)

    book_audio_dir = audio_dir / book_code
    mp3_path = book_audio_dir / f"toko_{chapter_str}.mp3"
    wav_path = book_audio_dir / f"toko_{chapter_str}.wav"

    paragraphs = chapter["paragraphs"]
    audio_url = chapter.get("audio_url")
    has_audio = False

    if audio_url and not skip_download:
        try:
            downloaded = download_mp3(client, audio_url, mp3_path)
            if downloaded:
                time.sleep(REQUEST_DELAY_SEC)
            convert_mp3_to_wav(mp3_path, wav_path)
            has_audio = True
        except Exception:
            logger.warning(
                "Failed to download/convert %s ch.%d",
                book_code, chapter_num, exc_info=True,
            )
    elif wav_path.exists():
        has_audio = True

    full_transcript = " ".join(_paragraph_to_text(p) for p in paragraphs)

    return ChapterResult(
        book_code=book_code,
        book_name_mg=book["name_mg"],
        chapter_number=chapter_num,
        audio_url=audio_url,
        wav_path=wav_path,
        has_audio=has_audio,
        paragraphs=_build_paragraph_meta(paragraphs),
        full_transcript=full_transcript,
    )


# ---------------------------------------------------------------------------
# Supabase ingest
# ---------------------------------------------------------------------------


def create_supabase_client():  # noqa: ANN201
    """Create a Supabase client from environment variables."""
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv()
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def ingest_chapter(
    supabase_client,  # noqa: ANN001
    result: ChapterResult,
    dry_run: bool = False,
) -> None:
    """Create a run + one unsplit clip for a chapter in Supabase."""
    chapter_str = str(result.chapter_number).zfill(2)
    label = f"baiboly-{result.book_code}-toko-{chapter_str}"
    source = f"{result.book_name_mg} toko {result.chapter_number}"
    file_name = f"{result.book_code}/toko_{chapter_str}.wav"

    if dry_run:
        n_para = len(result.paragraphs)
        print(f"  [DRY RUN] Would create run '{label}' with 1 clip ({n_para} paragraphs)")
        return

    run_data = supabase_client.table("runs").insert({
        "label": label,
        "source": source,
        "type": "reading",
    }).execute()

    run_id = run_data.data[0]["id"]

    supabase_client.table("clips").insert({
        "run_id": run_id,
        "file_name": file_name,
        "draft_transcription": result.full_transcript,
        "paragraphs": result.paragraphs,
        "status": "pending",
        "priority": 1,
    }).execute()

    if result.has_audio and result.wav_path.exists():
        storage_path = f"{run_id}/{file_name}"
        with open(result.wav_path, "rb") as f:
            supabase_client.storage.from_("clips").upload(
                storage_path,
                f.read(),
                {"content-type": "audio/wav"},
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Download Bible chapter audio and ingest into Supabase",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/bible"),
        help="Directory containing baiboly.json",
    )
    parser.add_argument(
        "--book", type=str, default=None,
        help="Process only this book code (e.g. at01)",
    )
    parser.add_argument(
        "--books", type=str, default=None,
        help="Comma-separated list of book codes",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview without creating Supabase records",
    )
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip mp3 download (use existing files)",
    )
    parser.add_argument(
        "--skip-supabase", action="store_true",
        help="Skip Supabase ingest (only download + convert)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    output_dir: Path = args.output_dir
    audio_dir = output_dir / "audio"

    baiboly_path = output_dir / "baiboly.json"
    if not baiboly_path.exists():
        print(f"Error: {baiboly_path} not found. Run bible_scrape.py first.", file=sys.stderr)
        sys.exit(1)

    with open(baiboly_path, encoding="utf-8") as f:
        baiboly: BaibolyData = json.load(f)

    book_filter: set[str] | None = None
    if args.book:
        book_filter = {args.book}
    elif args.books:
        book_filter = set(args.books.split(","))

    all_books: list[BookData] = []
    for testament in baiboly["testaments"]:
        for book in testament["books"]:
            if book_filter is None or book["code"] in book_filter:
                all_books.append(book)

    if not all_books:
        print("No books matched the filter.", file=sys.stderr)
        sys.exit(1)

    total_chapters = sum(len(b["chapters"]) for b in all_books)
    print("Baiboly Audio Ingest")
    print("=" * 50)
    print(f"  Books: {len(all_books)}")
    print(f"  Chapters: {total_chapters}")
    print(f"  Dry run: {args.dry_run}")
    print(f"  Skip download: {args.skip_download}")
    print()

    supabase_client = None
    if not args.dry_run and not args.skip_supabase:
        print("Connecting to Supabase...")
        supabase_client = create_supabase_client()
        print("  Connected.")

    chapter_idx = 0

    with httpx.Client() as client:
        for book in all_books:
            book_code = book["code"]
            book_name = book["name_mg"]
            print(f"\n{book_name} ({book_code}):")

            for chapter in book["chapters"]:
                chapter_idx += 1
                ch_num = chapter["chapter"]
                progress = f"  [{chapter_idx}/{total_chapters}]"

                print(f"{progress} toko {ch_num}...", end="", flush=True)

                result = process_chapter(
                    client=client,
                    book=book,
                    chapter=chapter,
                    audio_dir=audio_dir,
                    skip_download=args.skip_download,
                )

                audio_status = "audio" if result.has_audio else "no audio"
                print(f" {len(result.paragraphs)} paragraphs, {audio_status}")

                if supabase_client is not None:
                    ingest_chapter(supabase_client, result, dry_run=args.dry_run)

                if args.dry_run and supabase_client is None:
                    ingest_chapter(None, result, dry_run=True)

    print(f"\nDone! {chapter_idx} chapters processed.")


if __name__ == "__main__":
    main()
