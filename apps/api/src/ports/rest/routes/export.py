"""POST /export -- export training data."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from application.types import ExportRequest

router = APIRouter(prefix="/export", tags=["export"])


class ExportResponse(BaseModel):
    dataset_dir: str


@router.post("", response_model=ExportResponse)
def export(body: ExportRequest, request: Request) -> ExportResponse:
    settings = request.app.state.settings
    export_use_case = request.app.state.export
    output = body.output if "output" in body.model_fields_set else settings.output_dir
    output_dir = Path(output)

    dataset_path = export_use_case.execute(body.run_ids, output_dir, eval_split=body.eval_split)

    return ExportResponse(dataset_dir=str(dataset_path))
