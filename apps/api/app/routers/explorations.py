from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import ExplorationRequest, ExplorationResponse
from app.services.exploration import run_exploration
from app.services.workbook_loader import load_workbook_sheet, resolve_workbook_path

router = APIRouter()


@router.post("/run", response_model=ExplorationResponse)
async def run_exploration_api(request: ExplorationRequest):
    file_path = resolve_workbook_path(request.workbook_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Workbook not found")
    try:
        df = load_workbook_sheet(file_path, request.sheet_name)
        data_profile, target_feasibility, model_sweep, evaluation = run_exploration(df, request)
        return ExplorationResponse(
            workbook_id=request.workbook_id,
            sheet_name=request.sheet_name,
            data_profile=data_profile,
            target_feasibility=target_feasibility,
            model_sweep=model_sweep,
            evaluation=evaluation,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Exploration failed: {exc}") from exc
