"""POST /export — export training data (synchronous)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db_sync.export import export_training
from db_sync.run_resolution import resolve_run_id
from db_sync.supabase_client import get_client
from pipeline.iterate import _ensure_source_dir

router = APIRouter(prefix="/export", tags=["export"])


class ExportRequest(BaseModel):
    label: str
    eval_split: float = 0.1


class ExportResponse(BaseModel):
    run_id: str
    dataset_dir: str


@router.post("", response_model=ExportResponse)
def export(body: ExportRequest, request: Request) -> ExportResponse:
    settings = request.app.state.settings
    client = get_client()
    run_id = resolve_run_id(client, run_id=None, label=body.label)
    source_dir = _ensure_source_dir(client, run_id, body.label)
    output_dir = Path(settings.output_dir)
    dataset_path = export_training(
        client,
        run_id=run_id,
        label=None,
        source_dir=source_dir,
        output=output_dir,
        eval_split=body.eval_split,
    )
    if dataset_path is None:
        raise HTTPException(status_code=500, detail="Export produced no output")
    return ExportResponse(run_id=run_id, dataset_dir=str(dataset_path))
