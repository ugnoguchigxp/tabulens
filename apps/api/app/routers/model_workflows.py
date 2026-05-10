from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.paths import RESULT_DIR
from app.models.schemas import (
    BoundarySnapshot,
    ModelWorkflowRequest,
    ModelWorkflowResponse,
    WorkflowMetrics,
    WorkflowRowsResponse,
)
from app.services.exploration_store import load_exploration_result
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
        exploration_result = load_exploration_result(request.workbook_id, request.sheet_name)
        export_path = _save_workflow_export(
            workflow_id,
            workflow_result.result_df,
            workflow_result.metrics,
            exploration_result=exploration_result,
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
            "exploration_available": exploration_result is not None,
            "result_path": str(current_csv_path),
            "result_xlsx_path": str(current_xlsx_path),
            "export_xlsx_path": str(export_path),
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
async def get_workflow_boundary(workflow_id: str):
    state = _get_workflow_state(workflow_id)
    request = ModelWorkflowRequest.model_validate(state["request"])
    if request.use_case.value != "classification":
        raise HTTPException(status_code=400, detail="Boundary graph is only available for classification workflows")

    source_df, _, resolved_request = _load_workflow_source(request)
    result_df = _read_dataframe(_resolve_result_path(state))
    feature_columns = [column for column in resolved_request.mapping.feature_columns if column and column != resolved_request.mapping.label_column]
    if len(feature_columns) < 2:
        raise HTTPException(status_code=400, detail="Boundary graph requires at least 2 feature columns")
    if not resolved_request.mapping.label_column:
        raise HTTPException(status_code=400, detail="Boundary graph requires a label column")
    snapshot = build_boundary_snapshot(
        source_df=source_df,
        result_df=result_df,
        label_column=resolved_request.mapping.label_column,
        feature_columns=feature_columns,
    )
    return snapshot


@router.get("/{workflow_id}/export.xlsx")
async def export_workflow(workflow_id: str):
    state = _get_workflow_state(workflow_id)
    export_path = state.get("export_xlsx_path")
    if not export_path:
        raise HTTPException(status_code=404, detail="Workflow export not found")
    path = Path(str(export_path))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Workflow export not found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{workflow_id}-workflow.xlsx",
    )


def _load_workflow_source(request: ModelWorkflowRequest) -> tuple[pd.DataFrame, dict[str, Any], ModelWorkflowRequest]:
    if request.source_job_id:
        job_state = load_job_state(request.source_job_id)
        if job_state:
            result_path = job_state.get("result_path")
            if result_path and Path(result_path).exists():
                source_df = pd.read_csv(result_path)
                source_mapping = request.mapping.model_copy(deep=True)
                source_columns = list(source_df.columns)
                source_mapping.feature_columns = [column for column in source_mapping.feature_columns if column in source_columns]
                if source_mapping.label_column and source_mapping.label_column not in source_columns:
                    source_mapping.label_column = None
                resolved_request = request.model_copy(deep=True)
                resolved_request.mapping = source_mapping
                return source_df, {
                    "source_kind": "prepare_job",
                    "source_job_id": request.source_job_id,
                    "source_path": result_path,
                }, resolved_request
    file_path = resolve_workbook_path(request.workbook_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Workbook not found")
    source_df = load_workbook_sheet(file_path, request.sheet_name)
    return source_df, {"source_kind": "workbook", "source_path": str(file_path)}, request


def _get_workflow_state(workflow_id: str) -> dict[str, Any]:
    state = workflow_db.get(workflow_id)
    if state is None:
        state = load_job_state(workflow_id)
        if state is not None:
            workflow_db[workflow_id] = state
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return state


def _resolve_result_path(state: dict[str, Any]) -> Path:
    result_path = state.get("result_path")
    if isinstance(result_path, str) and Path(result_path).exists():
        return Path(result_path)
    fallback = RESULT_DIR / str(state["workflow_id"]) / "results.csv"
    if fallback.exists():
        state["result_path"] = str(fallback)
        return fallback
    raise HTTPException(status_code=404, detail="Workflow result not found")


def _save_workflow_export(
    workflow_id: str,
    result_df: pd.DataFrame,
    metrics: dict[str, Any],
    exploration_result: dict[str, Any] | None = None,
) -> Path:
    export_path = RESULT_DIR / workflow_id / "workflow_export.xlsx"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(export_path, engine="openpyxl") as writer:
        result_df.to_excel(writer, sheet_name="results", index=False)
        metrics_rows = [{"metric": key, "value": json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else value} for key, value in metrics.items()]
        pd.DataFrame(metrics_rows).to_excel(writer, sheet_name="metrics", index=False)
        if exploration_result and isinstance(exploration_result.get("evaluation"), dict):
            evaluation = exploration_result["evaluation"]
            rows = [
                {"key": "overall_verdict", "value": evaluation.get("overall_verdict")},
                {"key": "signal_strength", "value": evaluation.get("signal_strength")},
                {"key": "model_viability", "value": evaluation.get("model_viability")},
                {"key": "confidence", "value": evaluation.get("confidence")},
                {"key": "risk_flags", "value": json.dumps(evaluation.get("risk_flags", []), ensure_ascii=False)},
                {"key": "next_actions", "value": json.dumps(evaluation.get("next_actions", []), ensure_ascii=False)},
                {"key": "decision", "value": json.dumps(evaluation.get("decision", {}), ensure_ascii=False)},
            ]
            pd.DataFrame(rows).to_excel(writer, sheet_name="evaluation", index=False)
        else:
            pd.DataFrame([{"key": "evaluation_not_available", "value": True}]).to_excel(writer, sheet_name="evaluation", index=False)
    return export_path


def _read_dataframe(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    safe_df = df.replace([float("inf"), float("-inf")], pd.NA).where(pd.notna(df), None)
    return safe_df.to_dict(orient="records")
