"""Supabase implementation of AudioStorage."""

from __future__ import annotations

from pathlib import Path

from supabase import Client

from domain.ports.storage import AudioStorage


class SupabaseAudioStorage(AudioStorage):
    BUCKET = "clips"

    def __init__(self, client: Client) -> None:
        self._client = client

    def upload(self, run_id: str, file_name: str, file_path: Path) -> None:
        storage_path = f"{run_id}/{file_name}"
        with open(file_path, "rb") as f:
            self._client.storage.from_(self.BUCKET).upload(
                storage_path,
                f,
                file_options={"content-type": "audio/wav", "upsert": "true"},
            )

    def download(self, run_id: str, file_name: str, dest_path: Path) -> None:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path = f"{run_id}/{file_name}"
        data = self._client.storage.from_(self.BUCKET).download(storage_path)
        dest_path.write_bytes(data)

    def list_files(self, run_id: str) -> list[str]:
        objects = self._client.storage.from_(self.BUCKET).list(run_id)
        if not objects:
            return []
        return [obj["name"] for obj in objects if obj.get("id") is not None]

    def remove_prefix(self, prefix: str) -> None:
        objects = self._client.storage.from_(self.BUCKET).list(prefix)
        if not objects:
            return

        paths = [f"{prefix}/{obj['name']}" for obj in objects]

        sub_folders = [obj for obj in objects if obj.get("id") is None]
        for folder in sub_folders:
            sub_path = f"{prefix}/{folder['name']}"
            sub_objects = self._client.storage.from_(self.BUCKET).list(sub_path)
            if sub_objects:
                paths.extend(f"{sub_path}/{obj['name']}" for obj in sub_objects)

        file_paths = [p for p in paths if not p.endswith("/")]
        if file_paths:
            self._client.storage.from_(self.BUCKET).remove(file_paths)
