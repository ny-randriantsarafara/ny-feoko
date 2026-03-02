"""Tests for Supabase repository implementations."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from domain.entities.job import JobStatus, JobType
from domain.entities.run import RunType
from domain.exceptions import RunNotFoundError


class _FakeResponse:
    def __init__(self, data: list[dict[str, Any]], count: int | None = None) -> None:
        self.data = data
        self.count = count


class _FakeQuery:
    def __init__(self, data: list[dict[str, Any]], count: int | None = None) -> None:
        self._data = data
        self._count = count

    def eq(self, *_: object, **__: object) -> _FakeQuery:
        return self

    def neq(self, *_: object, **__: object) -> _FakeQuery:
        return self

    def order(self, *_: object, **__: object) -> _FakeQuery:
        return self

    def limit(self, *_: object) -> _FakeQuery:
        return self

    def range(self, *_: object) -> _FakeQuery:
        return self

    def select(self, *_: object, **__: object) -> _FakeQuery:
        return self

    def insert(self, *_: object) -> _FakeQuery:
        return self

    def update(self, *_: object) -> _FakeQuery:
        return self

    def upsert(self, *_: object, **__: object) -> _FakeQuery:
        return self

    def delete(self) -> _FakeQuery:
        return self

    def maybe_single(self) -> _FakeQuery:
        return self

    def execute(self) -> _FakeResponse:
        return _FakeResponse(self._data, self._count)


def _make_client(table_data: dict[str, list[dict[str, Any]]] | None = None) -> MagicMock:
    client = MagicMock()

    def table_fn(name: str) -> _FakeQuery:
        data = (table_data or {}).get(name, [])
        return _FakeQuery(data)

    client.table.side_effect = table_fn
    return client


class TestSupabaseRunRepository:
    def test_create(self) -> None:
        from infra.repositories.supabase_run_repo import SupabaseRunRepository

        client = _make_client({"runs": [{"id": "new-uuid"}]})
        repo = SupabaseRunRepository(client)
        result = repo.create("my-label", "/path", RunType.EXTRACTION)
        assert result == "new-uuid"

    def test_find_by_id_found(self) -> None:
        from infra.repositories.supabase_run_repo import SupabaseRunRepository

        client = _make_client({
            "runs": [{
                "id": "abc",
                "label": "test",
                "source": "/p",
                "type": "extraction",
                "created_at": "2026-01-01T00:00:00+00:00",
            }]
        })
        repo = SupabaseRunRepository(client)
        run = repo.find_by_id("abc")
        assert run is not None
        assert run.id == "abc"
        assert run.label == "test"

    def test_find_by_id_not_found(self) -> None:
        from infra.repositories.supabase_run_repo import SupabaseRunRepository

        client = _make_client({"runs": []})
        repo = SupabaseRunRepository(client)
        assert repo.find_by_id("missing") is None

    def test_resolve_run_id_with_id(self) -> None:
        from infra.repositories.supabase_run_repo import SupabaseRunRepository

        client = _make_client()
        repo = SupabaseRunRepository(client)
        assert repo.resolve_run_id("given-id", None) == "given-id"

    def test_resolve_run_id_with_label(self) -> None:
        from infra.repositories.supabase_run_repo import SupabaseRunRepository

        client = _make_client({"runs": [{"id": "found-id"}]})
        repo = SupabaseRunRepository(client)
        assert repo.resolve_run_id(None, "some-label") == "found-id"

    def test_resolve_run_id_not_found(self) -> None:
        from infra.repositories.supabase_run_repo import SupabaseRunRepository

        client = _make_client({"runs": []})
        repo = SupabaseRunRepository(client)
        with pytest.raises(RunNotFoundError):
            repo.resolve_run_id(None, "no-such-label")

    def test_resolve_run_id_no_args(self) -> None:
        from infra.repositories.supabase_run_repo import SupabaseRunRepository

        client = _make_client()
        repo = SupabaseRunRepository(client)
        with pytest.raises(RunNotFoundError):
            repo.resolve_run_id(None, None)


class TestSupabaseClipRepository:
    def test_upsert_batch(self) -> None:
        from infra.repositories.supabase_clip_repo import SupabaseClipRepository

        client = _make_client()
        repo = SupabaseClipRepository(client)
        rows = [{"file_name": "clip_00001.wav", "duration_sec": 5.0}]
        repo.upsert_batch("run-1", rows)
        assert rows[0]["run_id"] == "run-1"

    def test_count_by_status(self) -> None:
        from infra.repositories.supabase_clip_repo import SupabaseClipRepository

        client = MagicMock()
        query = MagicMock()
        query.select.return_value = query
        query.eq.return_value = query
        query.execute.return_value = _FakeResponse([], count=5)
        client.table.return_value = query

        repo = SupabaseClipRepository(client)
        counts = repo.count_by_status("run-1")
        assert all(c == 5 for c in counts.values())


class TestSupabaseJobRepository:
    def test_create(self) -> None:
        from infra.repositories.supabase_job_repo import SupabaseJobRepository

        client = _make_client({"jobs": [{"id": "job-uuid"}]})
        repo = SupabaseJobRepository(client)
        result = repo.create("ingest", {"url": "https://example.com"})
        assert result == "job-uuid"

    def test_find_by_id_found(self) -> None:
        from infra.repositories.supabase_job_repo import SupabaseJobRepository

        client = _make_client({
            "jobs": [{
                "id": "j1",
                "type": "ingest",
                "status": "queued",
                "progress": 0,
                "progress_message": None,
                "params": {},
                "result": None,
                "created_at": "2026-01-01T00:00:00+00:00",
            }]
        })
        repo = SupabaseJobRepository(client)
        job = repo.find_by_id("j1")
        assert job is not None
        assert job.job_type == JobType.INGEST
        assert job.status == JobStatus.QUEUED

    def test_find_by_id_not_found(self) -> None:
        from infra.repositories.supabase_job_repo import SupabaseJobRepository

        client = _make_client({"jobs": []})
        repo = SupabaseJobRepository(client)
        assert repo.find_by_id("missing") is None

    def test_fail(self) -> None:
        from infra.repositories.supabase_job_repo import SupabaseJobRepository

        client = _make_client()
        repo = SupabaseJobRepository(client)
        repo.fail("j1", "something broke")
