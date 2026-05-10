from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.paths import RESULT_DIR, UPLOAD_DIR
from app.models.schemas import BoundarySnapshot, JobRequest, JobResponse
from app.services.job_store import load_job_state, save_job_state, save_result_artifacts
from app.services.ml.boundary import build_boundary_snapshot
from app.services.ml.classifier import run_analysis

router = APIRouter()

jobs_db: dict[str, dict[str, Any]] = {}


@router.post("/run", response_model=JobResponse)
async def create_job(request: JobRequest):
    file_path = _resolve_workbook_path(request.workbook_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Workbook not found")

    try:
        source_df = _load_source_df(file_path, request.sheet_name)
        result_df, metadata = run_analysis(
            source_df,
            request.mapping.feature_columns,
            request.mapping.label_column,
            algorithm=request.algorithm,
            preprocessing=request.preprocessing.model_dump() if hasattr(request.preprocessing, "model_dump") else request.preprocessing.dict(),
            run_cleansing=request.run_cleansing,
            run_feature_selection=request.run_feature_selection,
            run_ml=request.run_ml,
        )

        job_id = str(uuid.uuid4())
        current_csv_path, current_xlsx_path = save_result_artifacts(job_id, result_df, name="current")

        state = {
            "job_id": job_id,
            "status": "completed",
            "workbook_id": request.workbook_id,
            "sheet_name": request.sheet_name,
            "source_path": str(file_path),
            "request": request.model_dump(mode="json"),
            "metadata": metadata,
            "result_path": str(current_csv_path),
            "result_xlsx_path": str(current_xlsx_path),
        }
        save_job_state(state)
        jobs_db[job_id] = state
        return JobResponse(job_id=job_id, status="completed", metadata=metadata)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


@router.get("/{job_id}")
async def get_job(job_id: str):
    state = _get_job_state(job_id)
    return {
        "job_id": job_id,
        "status": state.get("status", "completed"),
        "metadata": state.get("metadata", {}),
    }


@router.get("/{job_id}/rows")
async def get_job_rows(job_id: str):
    state = _get_job_state(job_id)
    result_path = _resolve_result_path(state)
    if result_path is None or not result_path.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    return _dataframe_to_records(_read_dataframe(result_path))


@router.get("/{job_id}/boundary", response_model=BoundarySnapshot)
async def get_job_boundary(job_id: str):
    state = _get_job_state(job_id)
    request = state.get("request", {})
    mapping = request.get("mapping") if isinstance(request, dict) else None
    label_column = mapping.get("label_column") if isinstance(mapping, dict) else None
    feature_columns = mapping.get("feature_columns") if isinstance(mapping, dict) else None
    if not label_column or not isinstance(feature_columns, list):
        raise HTTPException(status_code=400, detail="Boundary requires a label column and feature columns")
    source_df = _load_source_df(Path(state["source_path"]), str(state["sheet_name"]))
    result_df = _read_dataframe(_resolve_result_path(state))
    snapshot = build_boundary_snapshot(
        source_df=source_df,
        result_df=result_df,
        label_column=str(label_column),
        feature_columns=[str(item) for item in feature_columns],
    )
    return snapshot


@router.get("/{job_id}/export.xlsx")
async def export_job(job_id: str):
    state = _get_job_state(job_id)
    xlsx_path = state.get("result_xlsx_path")
    if not xlsx_path:
        raise HTTPException(status_code=404, detail="Export file path is missing")
    path = Path(str(xlsx_path))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"{job_id}-analysis.xlsx")


def _get_job_state(job_id: str) -> dict[str, Any]:
    state = jobs_db.get(job_id)
    if state is None:
        state = load_job_state(job_id)
        if state is not None:
            jobs_db[job_id] = state
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return state


def _resolve_result_path(state: dict[str, Any]) -> Path | None:
    result_path = state.get("result_path")
    if isinstance(result_path, str):
        path = Path(result_path)
        if path.exists():
            return path
    job_id = str(state["job_id"])
    fallback = RESULT_DIR / job_id / "current.csv"
    if fallback.exists():
        state["result_path"] = str(fallback)
        return fallback
    return None


def _read_dataframe(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _resolve_workbook_path(workbook_id: str) -> Path | None:
    for ext in [".xlsx", ".csv"]:
        file_path = UPLOAD_DIR / f"{workbook_id}{ext}"
        if file_path.exists():
            return file_path
    return None


def _load_source_df(file_path: Path, sheet_name: str) -> pd.DataFrame:
    if str(file_path).endswith(".xlsx"):
        return pd.read_excel(file_path, sheet_name=sheet_name)
    return pd.read_csv(file_path)


def _dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    safe_df = df.replace([float("inf"), float("-inf")], pd.NA).where(pd.notna(df), None)
    return safe_df.to_dict(orient="records")
