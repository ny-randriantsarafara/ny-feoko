"""GET /runs -- list available runs for frontend selection."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
def list_runs(request: Request) -> list[dict[str, Any]]:
    use_case = request.app.state.list_runs
    runs = use_case.execute()
    return [
        {
            "id": run.id,
            "label": run.label,
            "source": run.source,
            "type": run.run_type.value,
            "created_at": run.created_at.isoformat(),
        }
        for run in runs
    ]
