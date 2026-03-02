"""POST /export -- export training data."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/export", tags=["export"])


class ExportRequest(BaseModel):
    run_ids: list[str]
    eval_split: float = 0.1


class ExportResponse(BaseModel):
    dataset_dir: str


@router.post("", response_model=ExportResponse)
def export(body: ExportRequest, request: Request) -> ExportResponse:
    settings = request.app.state.settings
    export_use_case = request.app.state.export
    output_dir = Path(settings.output_dir)

    dataset_path = export_use_case.execute(
        body.run_ids, output_dir, eval_split=body.eval_split
    )

    return ExportResponse(dataset_dir=str(dataset_path))
