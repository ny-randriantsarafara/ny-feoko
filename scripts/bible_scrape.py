"""Phase 1: Scrape nybaiboly.net to produce manifest.json and baiboly.json.

Fetches the book index, audio index, and each book page to extract
structured Bible text with paragraph-level granularity.

Usage:
    python scripts/bible_scrape.py [--output-dir data/bible]
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://nybaiboly.net/"
BOOK_INDEX_URL = urljoin(BASE_URL, "Bible.htm")
AUDIO_INDEX_URL = urljoin(BASE_URL, "Bible_Oral.htm")
REQUEST_DELAY_SEC = 1.0

BOOK_HREF_PATTERN = re.compile(
    r"Bible/BibleMalagasyHtm-(at|nt)(\d{2})-(.+)\.htm"
)
AUDIO_HREF_PATTERN = re.compile(r"Bible_Oral/(.+\.mp3)")
VERSE_PATTERN = re.compile(r"^(\d+)\s+(.+)")
CHAPTER_ANCHOR_PATTERN = re.compile(r"^(at|nt)\d{2}_(?:\d_)?(\d{2,3})$")


class VerseDict(TypedDict):
    verse: int
    text: str


class ParagraphDict(TypedDict):
    heading: str | None
    verses: list[VerseDict]


class ChapterDict(TypedDict):
    chapter: int
    audio_url: str | None
    paragraphs: list[ParagraphDict]


class BookDict(TypedDict):
    code: str
    name_mg: str
    name_fr: str
    chapters: list[ChapterDict]


class TestamentDict(TypedDict):
    name: str
    books: list[BookDict]


class BaibolyDict(TypedDict):
    testaments: list[TestamentDict]


class ManifestChapterDict(TypedDict):
    chapter: int
    audio_url: str | None


class ManifestBookDict(TypedDict):
    book_code: str
    malagasy_name: str
    french_name: str
    testament: str
    text_page_url: str
    chapter_count: int
    chapters: list[ManifestChapterDict]


class ManifestSummaryDict(TypedDict):
    total_books: int
    total_chapters: int
    total_verses: int
    audio_found: int
    audio_missing: int


class MismatchDict(TypedDict):
    book_code: str
    type: str
    detail: str


class ManifestDict(TypedDict):
    scraped_at: str
    books: list[ManifestBookDict]
    summary: ManifestSummaryDict
    mismatches: list[MismatchDict]


@dataclass(frozen=True)
class BookEntry:
    book_code: str
    malagasy_name: str
    french_name: str
    testament: str
    text_page_url: str


@dataclass(frozen=True)
class Verse:
    number: int
    text: str


@dataclass
class Paragraph:
    heading: str | None
    verses: list[Verse] = field(default_factory=list)


@dataclass
class Chapter:
    number: int
    audio_url: str | None
    paragraphs: list[Paragraph] = field(default_factory=list)


@dataclass
class Book:
    entry: BookEntry
    chapters: list[Chapter] = field(default_factory=list)


def _fetch(client: httpx.Client, url: str) -> str:
    response = client.get(url, follow_redirects=True, timeout=30.0)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def scrape_book_index(client: httpx.Client) -> list[BookEntry]:
    """Parse Bible.htm to extract all book entries."""
    html = _fetch(client, BOOK_INDEX_URL)
    soup = BeautifulSoup(html, "html.parser")

    current_testament = ""
    books: list[BookEntry] = []

    for tag in soup.find_all(["h3", "a"]):
        if tag.name == "h3":
            text = tag.get_text(strip=True)
            if "Testamenta Taloha" in text:
                current_testament = "Testamenta Taloha"
            elif "Testamenta Vaovao" in text:
                current_testament = "Testamenta Vaovao"
            continue

        href = tag.get("href", "")
        match = BOOK_HREF_PATTERN.search(href)
        if not match:
            continue

        prefix = match.group(1)
        number = match.group(2)
        french_name = match.group(3)
        book_code = f"{prefix}{number}"
        malagasy_name = tag.get_text(strip=True)

        testament = current_testament
        if not testament:
            testament = (
                "Testamenta Taloha" if prefix == "at" else "Testamenta Vaovao"
            )

        full_url = urljoin(BASE_URL, href)
        books.append(
            BookEntry(
                book_code=book_code,
                malagasy_name=malagasy_name,
                french_name=french_name,
                testament=testament,
                text_page_url=full_url,
            )
        )

    return books


def scrape_audio_index(
    client: httpx.Client,
) -> dict[tuple[str, int], str]:
    """Parse Bible_Oral.htm to build a map of (book_code, chapter) -> audio_url."""
    html = _fetch(client, AUDIO_INDEX_URL)
    soup = BeautifulSoup(html, "html.parser")

    audio_map: dict[tuple[str, int], str] = {}

    for a_tag in soup.find_all("a", href=True):
        href: str = a_tag["href"]
        if not href.endswith(".mp3"):
            continue

        full_url = urljoin(AUDIO_INDEX_URL, href)
        filename = href.rsplit("/", 1)[-1].removesuffix(".mp3")

        book_code, chapter_num = _parse_audio_filename(filename)
        if book_code is not None:
            audio_map[(book_code, chapter_num)] = full_url

    return audio_map


def _parse_audio_filename(filename: str) -> tuple[str | None, int]:
    """Extract book_code and chapter number from an audio filename.

    Handles several naming conventions:
    - Standard: at01-Genesisy_toko_01
    - Psalms:   at19-SALAMO_salamo_001
    - Single-chapter books: at31-Obadia (no toko suffix)
    """
    parts = filename.split("-", 1)
    if len(parts) != 2:
        return None, 0

    book_code = parts[0]
    rest = parts[1]

    toko_match = re.search(r"_toko_(\d{2,3})$", rest)
    if toko_match:
        return book_code, int(toko_match.group(1))

    salamo_match = re.search(r"_salamo_(\d{3})$", rest)
    if salamo_match:
        return book_code, int(salamo_match.group(1))

    # Single-chapter book (no _toko_ suffix)
    if re.match(r"^(at|nt)\d{2}$", book_code):
        return book_code, 1

    return None, 0


def scrape_book_page(
    client: httpx.Client,
    entry: BookEntry,
    audio_map: dict[tuple[str, int], str],
) -> Book:
    """Fetch and parse a single book page into chapters/paragraphs/verses."""
    html = _fetch(client, entry.text_page_url)
    soup = BeautifulSoup(html, "html.parser")

    book = Book(entry=entry)
    current_chapter: Chapter | None = None
    current_paragraph: Paragraph | None = None
    past_preamble = False

    for p_tag in soup.find_all("p"):
        css_class = p_tag.get("class", [])
        css_class_str = css_class[0] if css_class else ""

        if css_class_str == "Chapitre":
            chapter_num = _extract_chapter_number(p_tag)
            if chapter_num is None:
                continue
            audio_url = audio_map.get((entry.book_code, chapter_num))
            current_chapter = Chapter(
                number=chapter_num, audio_url=audio_url
            )
            book.chapters.append(current_chapter)
            current_paragraph = None
            past_preamble = True
            continue

        if css_class_str in ("Clustermoyen", "Clustersecondaire", "Clustersuprieur"):
            if current_chapter is not None:
                current_paragraph = None
            continue

        if css_class_str == "Sous-Titre":
            continue

        if css_class_str in ("AccesDirect", "Livre"):
            past_preamble = True
            continue

        if current_chapter is None and css_class_str == "Usuel" and past_preamble:
            raw_text = p_tag.get_text(strip=True)
            if raw_text and raw_text != "\xa0" and VERSE_PATTERN.match(
                _strip_heading_from_text(raw_text) if _extract_heading(p_tag) else raw_text
            ):
                audio_url = audio_map.get((entry.book_code, 1))
                current_chapter = Chapter(number=1, audio_url=audio_url)
                book.chapters.append(current_chapter)

        if css_class_str == "Usuel":
            inline_ch = _detect_inline_chapter(p_tag, entry.book_code)
            if inline_ch is not None:
                audio_url = audio_map.get((entry.book_code, inline_ch))
                current_chapter = Chapter(
                    number=inline_ch, audio_url=audio_url
                )
                book.chapters.append(current_chapter)
                current_paragraph = None
                past_preamble = True

        if current_chapter is None:
            continue

        raw_text = p_tag.get_text(strip=True)
        if not raw_text or raw_text == "\xa0":
            continue

        raw_text = _strip_inline_chapter_prefix(raw_text)

        heading = _extract_heading(p_tag)
        cleaned_text = _strip_heading_from_text(raw_text) if heading else raw_text
        verse_match = VERSE_PATTERN.match(cleaned_text)

        if heading is not None:
            current_paragraph = Paragraph(heading=heading)
            current_chapter.paragraphs.append(current_paragraph)

        if verse_match:
            verse_num = int(verse_match.group(1))
            verse_text = _strip_footnotes(verse_match.group(2).strip())

            if current_paragraph is None:
                current_paragraph = Paragraph(heading=None)
                current_chapter.paragraphs.append(current_paragraph)

            current_paragraph.verses.append(
                Verse(number=verse_num, text=verse_text)
            )

    return book


def _extract_chapter_number(p_tag: Tag) -> int | None:
    """Extract chapter number from a <p class=Chapitre> tag.

    Handles both 'Chapitre N' and 'PSAUME N' (Psalms) formats,
    and anchor names like 'at01_01' or 'at19_1_01' (Psalms sub-book).
    """
    anchor = p_tag.find("a", attrs={"name": True})
    if anchor:
        name = anchor["name"]
        match = CHAPTER_ANCHOR_PATTERN.match(name)
        if match:
            return int(match.group(2))

    text = p_tag.get_text(strip=True)
    ch_match = re.search(r"(?:Chapitre|PSAUME)\s+(\d+)", text, re.IGNORECASE)
    if ch_match:
        return int(ch_match.group(1))
    return None


def _detect_inline_chapter(p_tag: Tag, book_code: str) -> int | None:
    """Detect inline chapter headings embedded in Usuel paragraphs.

    Some books have chapters formatted as:
    <p class=Usuel><a name="at09_10"></a><b>Chapitre 10.</b> 1 verse text...</p>
    """
    anchor = p_tag.find("a", attrs={"name": True})
    if not anchor:
        return None

    name: str = anchor["name"]
    if not name.startswith(book_code + "_"):
        return None

    match = CHAPTER_ANCHOR_PATTERN.match(name)
    if not match:
        return None

    chapter_num = int(match.group(2))

    bold = p_tag.find("b")
    if bold:
        bold_text = bold.get_text(strip=True)
        if re.search(r"(?:Chapitre|PSAUME)\s+\d+", bold_text, re.IGNORECASE):
            return chapter_num

    return None


def _extract_heading(p_tag: Tag) -> str | None:
    """Extract bracketed heading from a green span or text.

    Filters out footnote markers (single '*') and footnote definitions
    like '[* Na: ...]' or '[Samoela = ...]'.
    """
    green_spans = p_tag.find_all("span", style=lambda s: s and "green" in s)
    for span in green_spans:
        heading_text = span.get_text(strip=True)
        if not heading_text.startswith("["):
            continue
        heading_text = heading_text.strip("[]")
        if _is_footnote(heading_text):
            continue
        if heading_text:
            return heading_text

    text = p_tag.get_text(strip=True)
    for match in re.finditer(r"\[([^\]]+)\]", text):
        candidate = match.group(1)
        if not _is_footnote(candidate):
            return candidate

    return None


def _is_footnote(text: str) -> bool:
    """Check if bracketed text is a footnote rather than a section heading."""
    if text == "*":
        return True
    if text.startswith("*") or text.startswith("**"):
        return True
    if re.match(r"^\*\s", text):
        return True
    if "=" in text and len(text) < 80:
        return True
    if text.startswith("Na:") or text.startswith("Na "):
        return True
    return text.startswith("Gr.") or text.startswith("Heb.")


def _strip_footnotes(text: str) -> str:
    """Remove footnote markers and definitions from verse text."""
    text = re.sub(r"\[(\*+\s*[^\]]*|Na:[^\]]*|Na\s[^\]]*|Gr\.[^\]]*|Heb\.[^\]]*)\]", "", text)
    text = re.sub(r"(?<!\[)\*{1,2}(?!\])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _strip_inline_chapter_prefix(text: str) -> str:
    """Remove inline chapter heading like 'Chapitre 10. ' from beginning of text."""
    return re.sub(
        r"^(?:Chapitre|PSAUME)\s+\d+\.?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )


def _strip_heading_from_text(text: str) -> str:
    """Remove the bracketed heading portion from a verse line.

    Raw text may be structured as '1[heading]verse text' or '[heading] 1 verse text'.
    Replaces the heading with a space to preserve word boundaries.
    """
    cleaned = re.sub(r"\[([^\]]+)\]\s*", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def validate_book(book: Book) -> list[str]:
    """Check for sequential verses, empty text, etc. Return list of anomalies."""
    anomalies: list[str] = []
    code = book.entry.book_code

    for chapter in book.chapters:
        all_verses = [
            v for p in chapter.paragraphs for v in p.verses
        ]
        if not all_verses:
            anomalies.append(
                f"{code} ch.{chapter.number}: no verses found"
            )
            continue

        for i, verse in enumerate(all_verses):
            if not verse.text:
                anomalies.append(
                    f"{code} ch.{chapter.number} v.{verse.number}: empty text"
                )

            expected = i + 1
            if verse.number != expected:
                anomalies.append(
                    f"{code} ch.{chapter.number}: verse {verse.number} at position {expected}"
                )

    return anomalies


def build_manifest(
    books: list[Book],
    all_anomalies: list[str],
) -> ManifestDict:
    """Build the manifest.json structure."""
    total_chapters = 0
    total_verses = 0
    audio_found = 0
    audio_missing = 0
    mismatches: list[MismatchDict] = []
    manifest_books: list[ManifestBookDict] = []

    for book in books:
        chapter_count = len(book.chapters)
        total_chapters += chapter_count

        manifest_chapters: list[ManifestChapterDict] = []
        for ch in book.chapters:
            verse_count = sum(len(p.verses) for p in ch.paragraphs)
            total_verses += verse_count

            if ch.audio_url:
                audio_found += 1
            else:
                audio_missing += 1
                mismatches.append(
                    MismatchDict(
                        book_code=book.entry.book_code,
                        type="missing_audio",
                        detail=f"Chapter {ch.number} has no audio URL",
                    )
                )

            manifest_chapters.append(
                ManifestChapterDict(
                    chapter=ch.number,
                    audio_url=ch.audio_url,
                )
            )

        manifest_books.append(
            ManifestBookDict(
                book_code=book.entry.book_code,
                malagasy_name=book.entry.malagasy_name,
                french_name=book.entry.french_name,
                testament=book.entry.testament,
                text_page_url=book.entry.text_page_url,
                chapter_count=chapter_count,
                chapters=manifest_chapters,
            )
        )

    for anomaly in all_anomalies:
        code = anomaly.split(" ", 1)[0]
        mismatches.append(
            MismatchDict(
                book_code=code,
                type="validation",
                detail=anomaly,
            )
        )

    return ManifestDict(
        scraped_at=datetime.now(tz=UTC).isoformat(),
        books=manifest_books,
        summary=ManifestSummaryDict(
            total_books=len(books),
            total_chapters=total_chapters,
            total_verses=total_verses,
            audio_found=audio_found,
            audio_missing=audio_missing,
        ),
        mismatches=mismatches,
    )


def build_baiboly(books: list[Book]) -> BaibolyDict:
    """Build the baiboly.json structure grouped by testament."""
    testaments: dict[str, list[BookDict]] = {}

    for book in books:
        testament_name = book.entry.testament
        if testament_name not in testaments:
            testaments[testament_name] = []

        book_dict = BookDict(
            code=book.entry.book_code,
            name_mg=book.entry.malagasy_name,
            name_fr=book.entry.french_name,
            chapters=[
                ChapterDict(
                    chapter=ch.number,
                    audio_url=ch.audio_url,
                    paragraphs=[
                        ParagraphDict(
                            heading=p.heading,
                            verses=[
                                VerseDict(verse=v.number, text=v.text)
                                for v in p.verses
                            ],
                        )
                        for p in ch.paragraphs
                    ],
                )
                for ch in book.chapters
            ],
        )
        testaments[testament_name].append(book_dict)

    testament_order = ["Testamenta Taloha", "Testamenta Vaovao"]
    return BaibolyDict(
        testaments=[
            TestamentDict(name=name, books=testaments.get(name, []))
            for name in testament_order
            if name in testaments
        ]
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape nybaiboly.net and produce manifest.json + baiboly.json"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/bible"),
        help="Output directory (default: data/bible)",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Phase 1: Baiboly Malagasy Extraction")
    print("=" * 50)

    with httpx.Client() as client:
        print("\n[1/4] Scraping book index...")
        book_entries = scrape_book_index(client)
        print(f"  Found {len(book_entries)} books")

        time.sleep(REQUEST_DELAY_SEC)

        print("\n[2/4] Scraping audio index...")
        audio_map = scrape_audio_index(client)
        print(f"  Found {len(audio_map)} audio files")

        time.sleep(REQUEST_DELAY_SEC)

        print(f"\n[3/4] Scraping {len(book_entries)} book pages...")
        all_books: list[Book] = []
        all_anomalies: list[str] = []

        for i, entry in enumerate(book_entries):
            progress = f"  [{i + 1}/{len(book_entries)}]"
            print(f"{progress} {entry.malagasy_name} ({entry.book_code})...", end="", flush=True)

            book = scrape_book_page(client, entry, audio_map)
            anomalies = validate_book(book)
            all_anomalies.extend(anomalies)

            ch_count = len(book.chapters)
            v_count = sum(
                len(p.verses)
                for ch in book.chapters
                for p in ch.paragraphs
            )
            status = " OK" if not anomalies else f" {len(anomalies)} warnings"
            print(f" {ch_count} chapters, {v_count} verses{status}")

            all_books.append(book)

            if i < len(book_entries) - 1:
                time.sleep(REQUEST_DELAY_SEC)

    print("\n[4/4] Building output files...")

    manifest = build_manifest(all_books, all_anomalies)
    baiboly = build_baiboly(all_books)

    manifest_path = output_dir / "manifest.json"
    baiboly_path = output_dir / "baiboly.json"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    with open(baiboly_path, "w", encoding="utf-8") as f:
        json.dump(baiboly, f, ensure_ascii=False, indent=2)

    summary = manifest["summary"]
    print("\nDone!")
    print(f"  Books:    {summary['total_books']}")
    print(f"  Chapters: {summary['total_chapters']}")
    print(f"  Verses:   {summary['total_verses']}")
    print(f"  Audio:    {summary['audio_found']} found, {summary['audio_missing']} missing")
    print(f"\n  Manifest: {manifest_path}")
    print(f"  Baiboly:  {baiboly_path}")

    if all_anomalies:
        print(f"\n  Anomalies ({len(all_anomalies)}):")
        for a in all_anomalies[:20]:
            print(f"    - {a}", file=sys.stderr)
        if len(all_anomalies) > 20:
            print(
                f"    ... and {len(all_anomalies) - 20} more",
                file=sys.stderr,
            )

    if manifest["mismatches"]:
        print(
            f"\n  Mismatches: {len(manifest['mismatches'])} (see manifest.json)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
