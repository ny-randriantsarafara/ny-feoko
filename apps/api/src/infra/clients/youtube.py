"""YouTube audio downloader via yt-dlp."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from domain.ports.downloader import AudioDownloader


class YouTubeDownloader(AudioDownloader):
    def download(self, url: str, dest_dir: Path, label: str) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)

        resolved_label = label or self._derive_label(url)
        out_path = dest_dir / f"{resolved_label}.wav"

        try:
            subprocess.run(
                [
                    "yt-dlp",
                    "--extract-audio",
                    "--audio-format", "wav",
                    "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
                    "-o", str(out_path),
                    url,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to download audio for {url}: {exc.stderr or exc.stdout or exc}"
            ) from exc

        return out_path

    @staticmethod
    def _derive_label(url: str) -> str:
        title = YouTubeDownloader._get_title(url)
        return YouTubeDownloader._sanitize(title)

    @staticmethod
    def _get_title(url: str) -> str:
        try:
            result = subprocess.run(
                ["yt-dlp", "--get-title", url],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to fetch title for {url}: {exc.stderr or exc.stdout or exc}"
            ) from exc
        return result.stdout.strip()

    @staticmethod
    def _sanitize(name: str) -> str:
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[\s]+", "-", name.strip())
        return name.lower()[:80]
