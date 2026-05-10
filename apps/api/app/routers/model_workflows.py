from __future__ import annotations

import json
import uuid
import zipfile
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.paths import RESULT_DIR
from app.models.schemas import BoundarySnapshot, JobRequest, ModelWorkflowRequest, ModelWorkflowResponse, UseCaseType, WorkflowMetrics, WorkflowRowsResponse
from app.services.job_store import load_job_state, save_job_state, save_result_artifacts
from app.services.ml.boundary import build_boundary_snapshot
from app.services.ml.model_workflows import run_model_workflow
from app.services.workbook_loader import load_workbook_sheet, resolve_workbook_path

router = APIRouter()

workflow_db: dict[str, dict[str, Any]] = {}


@router.post("/run", response_model=ModelWorkflowResponse)
async def run_workflow(request: ModelWorkflowRequest):
    try:
        if not request.source_job_id:
            raise HTTPException(status_code=400, detail="Workflow requires a completed Prepare job")
        source_df, source_metadata, request = _load_workflow_source(request)
        workflow_id = str(uuid.uuid4())
        workflow_result = run_model_workflow(source_df, request, workflow_id)
        workflow_result.metadata.update(source_metadata)

        current_csv_path, current_xlsx_path = save_result_artifacts(workflow_id, workflow_result.result_df, name="results")
        _save_workflow_export(workflow_id, workflow_result.result_df, workflow_result.metrics)
        model_artifact_zip_path = None
        if workflow_result.model_artifacts:
            model_artifact_zip_path = _save_model_artifact_bundle(
                workflow_id=workflow_id,
                result_df=workflow_result.result_df,
                metrics=workflow_result.metrics,
                artifacts=workflow_result.model_artifacts,
            )

        state = {
            "job_id": workflow_id,
            "workflow_id": workflow_id,
            "status": "completed",
            "workbook_id": request.workbook_id,
            "sheet_name": request.sheet_name,
            "source_job_id": request.source_job_id,
            "source_kind": source_metadata.get("source_kind", "workbook"),
            "use_case": request.use_case.value,
            "source_path": source_metadata.get("source_path"),
            "request": request.model_dump(mode="json"),
            "metadata": workflow_result.metadata,
            "metrics": workflow_result.metrics,
            "result_path": str(current_csv_path),
            "result_xlsx_path": str(current_xlsx_path),
            "export_xlsx_path": str(_workflow_export_path(workflow_id)),
            "model_artifact_zip_path": str(model_artifact_zip_path) if model_artifact_zip_path else None,
        }
        save_job_state(state)
        workflow_db[workflow_id] = state

        return ModelWorkflowResponse(
            workflow_id=workflow_id,
            status="completed",
            use_case=request.use_case,
            rows=_dataframe_to_records(workflow_result.result_df),
            metrics=WorkflowMetrics(values=workflow_result.metrics),
            metadata=workflow_result.metadata,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workflow failed: {exc}") from exc


@router.get("/{workflow_id}", response_model=ModelWorkflowResponse)
async def get_workflow(workflow_id: str):
    state = _get_workflow_state(workflow_id)
    result_df = _read_dataframe(_resolve_result_path(state))
    return ModelWorkflowResponse(
        workflow_id=workflow_id,
        status=state.get("status", "completed"),
        use_case=state.get("use_case", "classification"),
        rows=_dataframe_to_records(result_df),
        metrics=WorkflowMetrics(values=state.get("metrics", {})),
        metadata=state.get("metadata", {}),
    )


@router.get("/{workflow_id}/rows", response_model=WorkflowRowsResponse)
async def get_workflow_rows(workflow_id: str):
    state = _get_workflow_state(workflow_id)
    result_df = _read_dataframe(_resolve_result_path(state))
    return WorkflowRowsResponse(workflow_id=workflow_id, rows=_dataframe_to_records(result_df))


@router.get("/{workflow_id}/metrics", response_model=WorkflowMetrics)
async def get_workflow_metrics(workflow_id: str):
    state = _get_workflow_state(workflow_id)
    return WorkflowMetrics(values=state.get("metrics", {}))


@router.get("/{workflow_id}/boundary", response_model=BoundarySnapshot)
async def get_workflow_boundary(workflow_id: str, grid_resolution: int = 40):
    state = _get_workflow_state(workflow_id)
    request = ModelWorkflowRequest.model_validate(state["request"])
    if request.use_case != UseCaseType.CLASSIFICATION:
        raise HTTPException(status_code=400, detail="Boundary graph is only available for classification workflows")

    result_df = _read_dataframe(_resolve_result_path(state))
    source_df, _, request = _load_workflow_source(request)
    boundary_request = JobRequest(
        workbook_id=request.workbook_id,
        sheet_name=request.sheet_name,
        mapping=request.mapping,
        algorithm=request.algorithm,
        params=request.params,
        preprocessing=request.preprocessing,
        run_cleansing=True,
        run_feature_selection=False,
        run_ml=True,
    )
    try:
        return build_boundary_snapshot(
            job_id=workflow_id,
            source_df=source_df,
            result_df=result_df,
            request=boundary_request,
            grid_resolution=grid_resolution,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{workflow_id}/artifact.zip")
async def export_model_artifact(workflow_id: str):
    state = _get_workflow_state(workflow_id)
    artifact_path = state.get("model_artifact_zip_path")
    if not artifact_path:
        raise HTTPException(status_code=404, detail="Model artifact is not available for this workflow")
    path = Path(artifact_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Model artifact not found")

    return FileResponse(
        path=str(path),
        filename=f"{workflow_id}-model-artifact.zip",
        media_type="application/zip",
    )


@router.get("/{workflow_id}/export.xlsx")
async def export_workflow(workflow_id: str):
    export_path = _workflow_export_path(workflow_id)
    if not export_path.exists():
        state = _get_workflow_state(workflow_id)
        result_df = _read_dataframe(_resolve_result_path(state))
        _save_workflow_export(workflow_id, result_df, state.get("metrics", {}))

    return FileResponse(
        path=str(export_path),
        filename=f"{workflow_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _workflow_export_path(workflow_id: str) -> Path:
    path = RESULT_DIR / workflow_id
    path.mkdir(parents=True, exist_ok=True)
    return path / "export.xlsx"


def _workflow_model_artifact_path(workflow_id: str) -> Path:
    path = RESULT_DIR / workflow_id
    path.mkdir(parents=True, exist_ok=True)
    return path / "model_artifact.zip"


def _load_workflow_source(request: ModelWorkflowRequest) -> tuple[pd.DataFrame, dict[str, Any], ModelWorkflowRequest]:
    if request.source_job_id:
        source_state = load_job_state(request.source_job_id)
        if source_state is None:
            raise HTTPException(status_code=404, detail="Source prepare job not found")
        result_path = source_state.get("result_path")
        if not result_path:
            raise HTTPException(status_code=404, detail="Source prepare result not found")
        path = Path(result_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Source prepare result file not found")

        prepare_request = None
        raw_prepare_request = source_state.get("current_request") or source_state.get("base_request")
        if raw_prepare_request:
            try:
                prepare_request = JobRequest.model_validate(raw_prepare_request)
            except Exception:
                prepare_request = None
        if prepare_request is not None:
            request = request.model_copy(update={"preprocessing": prepare_request.preprocessing})

        return _read_dataframe(path), {
            "source_kind": "prepare_job",
            "source_job_id": request.source_job_id,
            "source_path": str(path),
            "prepare_preprocessing_applied": prepare_request.preprocessing.model_dump(mode="json") if prepare_request is not None else None,
        }, request

    file_path = resolve_workbook_path(request.workbook_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Workbook not found")
    return load_workbook_sheet(file_path, request.sheet_name), {
        "source_kind": "workbook",
        "source_path": str(file_path),
    }, request


def _save_workflow_export(workflow_id: str, result_df: pd.DataFrame, metrics: dict[str, Any]) -> None:
    export_path = _workflow_export_path(workflow_id)
    with pd.ExcelWriter(export_path, engine="openpyxl") as writer:
        result_df.to_excel(writer, sheet_name="results", index=False)
        pd.DataFrame([metrics]).to_excel(writer, sheet_name="metrics", index=False)


def _save_model_artifact_bundle(
    *,
    workflow_id: str,
    result_df: pd.DataFrame,
    metrics: dict[str, Any],
    artifacts: dict[str, Any],
) -> Path:
    artifact_dir = RESULT_DIR / workflow_id / "model_artifact"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    zip_path = _workflow_model_artifact_path(workflow_id)

    joblib.dump(artifacts["model"], artifact_dir / "model.joblib")
    joblib.dump(artifacts["preprocessor"], artifact_dir / "preprocessing.joblib")
    _write_json(artifact_dir / "feature_columns.json", {"feature_columns": artifacts.get("feature_columns", [])})
    _write_json(
        artifact_dir / "target_schema.json",
        {
            "label_column": artifacts.get("label_column"),
            "task_type": artifacts.get("task_type"),
        },
    )
    _write_json(
        artifact_dir / "training_config.json",
        {
            "algorithm": artifacts.get("algorithm"),
            "params": artifacts.get("params", {}),
            "preprocessing": artifacts.get("preprocessing", {}),
        },
    )
    _write_json(artifact_dir / "metrics.json", metrics)
    result_df.to_excel(artifact_dir / "predictions.xlsx", index=False)
    result_df.to_excel(artifact_dir / "results.xlsx", index=False)

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(artifact_dir.iterdir()):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.name)

    return zip_path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _resolve_result_path(state: dict[str, Any]) -> Path:
    result_path = state.get("result_path")
    if result_path:
        path = Path(result_path)
        if path.exists():
            return path
    legacy_csv = RESULT_DIR / f"{state['workflow_id']}.csv"
    if legacy_csv.exists():
        return legacy_csv
    legacy_xlsx = RESULT_DIR / f"{state['workflow_id']}.xlsx"
    if legacy_xlsx.exists():
        return legacy_xlsx
    raise HTTPException(status_code=404, detail="Workflow result not found")


def _read_dataframe(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    return pd.read_csv(path)


def _dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


def _get_workflow_state(workflow_id: str) -> dict[str, Any]:
    state = workflow_db.get(workflow_id)
    if state is None:
        state = load_job_state(workflow_id)
        if state is not None:
            workflow_db[workflow_id] = state
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return state
