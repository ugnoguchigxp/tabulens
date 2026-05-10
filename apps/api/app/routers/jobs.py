from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.paths import RESULT_DIR, UPLOAD_DIR
from app.models.schemas import (
    ComparisonResponse,
    BoundarySnapshot,
    JobRequest,
    JobResponse,
    ProposalListResponse,
    ProposalStatus,
    ReviewAction,
    ReviewAssessment,
    ReviewResult,
    ReviewSummary,
    RerunRequest,
)
from app.services.analysis_review import (
    apply_proposals_and_rerun,
    build_comparison,
    build_review_summary,
    review_job,
    save_review_artifacts,
    proposal_key,
)
from app.services.job_store import load_job_state, save_job_state, save_result_artifacts
from app.services.ml.boundary import build_boundary_snapshot
from app.services.ml.classifier import run_analysis

router = APIRouter()

jobs_db: dict[str, dict[str, Any]] = {}
COMPLETED_PROPOSAL_STATUSES = {ProposalStatus.APPLIED, ProposalStatus.DISCARDED}


def _normalize_proposals(proposals: list[ReviewAction]) -> list[ReviewAction]:
    normalized: list[ReviewAction] = []
    key_to_index: dict[str, int] = {}

    for proposal in proposals:
        item = proposal.model_copy(deep=True)
        key = proposal_key(item)
        if key not in key_to_index:
            key_to_index[key] = len(normalized)
            normalized.append(item)
            continue

        existing = normalized[key_to_index[key]]
        if existing.status == ProposalStatus.PENDING and item.status in {ProposalStatus.APPLIED, ProposalStatus.DISCARDED}:
            existing.status = item.status

    return normalized


def _parse_proposals(raw_proposals: Any) -> list[ReviewAction]:
    if not isinstance(raw_proposals, list):
        return []

    proposals: list[ReviewAction] = []
    for item in raw_proposals:
        try:
            proposals.append(ReviewAction.model_validate(item))
        except Exception:
            continue
    return proposals


def _proposal_payload(proposals: list[ReviewAction]) -> list[dict[str, Any]]:
    return [proposal.model_dump(mode="json") for proposal in proposals]


def _is_completed_proposal(proposal: ReviewAction) -> bool:
    return proposal.status in COMPLETED_PROPOSAL_STATUSES


def _completed_proposal_keys(proposals: list[ReviewAction]) -> set[str]:
    return {proposal_key(proposal) for proposal in proposals if _is_completed_proposal(proposal)}


def _merge_resolved_proposals(*proposal_groups: list[ReviewAction]) -> list[ReviewAction]:
    resolved: list[ReviewAction] = []
    for group in proposal_groups:
        resolved.extend(proposal for proposal in group if _is_completed_proposal(proposal))
    return _normalize_proposals(resolved)


def _normalize_job_state(state: dict[str, Any]) -> bool:
    changed = False

    raw_proposals = state.get("proposals", [])
    raw_resolved_proposals = state.get("resolved_proposals", [])
    proposals = _parse_proposals(raw_proposals)
    resolved_proposals = _merge_resolved_proposals(
        _parse_proposals(raw_resolved_proposals),
        proposals,
    )
    completed_keys = _completed_proposal_keys(resolved_proposals)
    active_proposals = [
        proposal.model_copy(deep=True)
        for proposal in proposals
        if proposal.status == ProposalStatus.PENDING and proposal_key(proposal) not in completed_keys
    ]
    normalized_proposals = _normalize_proposals(active_proposals)
    normalized_proposal_payload = _proposal_payload(normalized_proposals)
    if normalized_proposal_payload != raw_proposals:
        state["proposals"] = normalized_proposal_payload
        changed = True

    normalized_resolved_payload = _proposal_payload(resolved_proposals)
    if normalized_resolved_payload != raw_resolved_proposals:
        state["resolved_proposals"] = normalized_resolved_payload
        changed = True

    raw_review_result = state.get("review_result")
    if raw_review_result:
        try:
            review_result = ReviewResult.model_validate(raw_review_result)
            review_result.recommended_actions = [proposal.model_copy(deep=True) for proposal in normalized_proposals]
            normalized_review_result = review_result.model_dump(mode="json")
            if normalized_review_result != raw_review_result:
                state["review_result"] = normalized_review_result
                changed = True
        except Exception:
            pass

    return changed


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
        baseline_csv_path, baseline_xlsx_path = save_result_artifacts(job_id, result_df, name="baseline")

        summary = build_review_summary(
            job_id=job_id,
            workbook_id=request.workbook_id,
            sheet_name=request.sheet_name,
            request=request,
            source_df=source_df,
            result_df=result_df,
            metadata=metadata,
        )
        review_result = review_job(summary=summary)
        merged_proposals = _compose_proposals([], review_result.recommended_actions)
        review_result.recommended_actions = merged_proposals
        job_dir = current_csv_path.parent
        save_review_artifacts(
            artifact_dir=job_dir,
            summary=summary,
            review_result=review_result,
        )

        state = {
            "job_id": job_id,
            "status": "completed",
            "workbook_id": request.workbook_id,
            "sheet_name": request.sheet_name,
            "source_path": str(file_path),
            "base_request": request.model_dump(mode="json"),
            "current_request": request.model_dump(mode="json"),
            "metadata": metadata,
            "baseline_metadata": metadata,
            "result_path": str(current_csv_path),
            "result_xlsx_path": str(current_xlsx_path),
            "baseline_result_path": str(baseline_csv_path),
            "baseline_result_xlsx_path": str(baseline_xlsx_path),
            "review_summary": summary.model_dump(mode="json"),
            "review_result": review_result.model_dump(mode="json"),
            "proposals": [proposal.model_dump(mode="json") for proposal in merged_proposals],
            "resolved_proposals": [],
            "last_applied_proposals": [],
            "comparison": None,
        }
        _normalize_job_state(state)
        save_job_state(state)
        jobs_db[job_id] = state

        return JobResponse(job_id=job_id, status="completed", metadata=metadata)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc


@router.get("/{job_id}/rows")
async def get_job_rows(job_id: str):
    state = _get_job_state(job_id)
    result_path = _resolve_result_path(state)
    if result_path is None or not result_path.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    return _dataframe_to_records(_read_dataframe(result_path))


@router.get("/{job_id}")
async def get_job(job_id: str):
    state = _get_job_state(job_id)
    return {
        "job_id": job_id,
        "status": state.get("status", "completed"),
        "metadata": state.get("metadata", {}),
        "review_status": state.get("review_result", {}).get("assessment") if state.get("review_result") else None,
        "proposal_count": len(state.get("proposals", [])),
    }


@router.get("/{job_id}/review-summary", response_model=ReviewSummary)
async def get_review_summary(job_id: str):
    state = _get_job_state(job_id)
    summary = _load_review_summary(state)
    if summary is None:
        raise HTTPException(status_code=404, detail="Review summary not found")
    return summary


@router.get("/{job_id}/review", response_model=ReviewResult)
async def get_review_result(job_id: str):
    state = _get_job_state(job_id)
    review_result = _load_review_result(state)
    if review_result is None:
        raise HTTPException(status_code=404, detail="Review result not found")
    return review_result


@router.post("/{job_id}/review", response_model=ReviewResult)
async def run_job_review(job_id: str):
    state = _get_job_state(job_id)
    summary = _load_review_summary(state)
    if summary is None:
        summary = _rebuild_review_summary(state)

    review_result = review_job(summary=summary)
    merged_proposals = _compose_proposals(
        _parse_proposals(state.get("proposals", [])),
        review_result.recommended_actions,
        _parse_proposals(state.get("resolved_proposals", [])),
    )
    review_result.recommended_actions = merged_proposals
    state["review_summary"] = summary.model_dump(mode="json")
    state["review_result"] = review_result.model_dump(mode="json")
    state["proposals"] = [proposal.model_dump(mode="json") for proposal in merged_proposals]
    save_review_artifacts(
        artifact_dir=_job_dir(job_id),
        summary=summary,
        review_result=review_result,
    )
    _normalize_job_state(state)
    save_job_state(state)
    jobs_db[job_id] = state
    return review_result


@router.get("/{job_id}/proposals", response_model=ProposalListResponse)
async def get_job_proposals(job_id: str):
    state = _get_job_state(job_id)
    proposals = _parse_proposals(state.get("proposals", []))
    return ProposalListResponse(job_id=job_id, proposals=proposals)


@router.post("/{job_id}/proposals/{proposal_id}/apply", response_model=ComparisonResponse)
async def apply_proposal(job_id: str, proposal_id: str):
    return await _apply_and_compare(job_id, [proposal_id])


@router.post("/{job_id}/proposals/{proposal_id}/discard", response_model=ReviewAction)
async def discard_proposal(job_id: str, proposal_id: str):
    state = _get_job_state(job_id)
    proposals = _parse_proposals(state.get("proposals", []))
    active_proposals: list[ReviewAction] = []
    discarded_proposals: list[ReviewAction] = []
    found: ReviewAction | None = None
    for proposal in proposals:
        if proposal.proposal_id == proposal_id:
            found = proposal.model_copy(deep=True)
        active_proposals.append(proposal)

    if found is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    target_key = proposal_key(found)
    remaining_proposals: list[ReviewAction] = []
    for proposal in active_proposals:
        if proposal.proposal_id == proposal_id or proposal_key(proposal) == target_key:
            discarded = proposal.model_copy(deep=True)
            discarded.status = ProposalStatus.DISCARDED
            discarded_proposals.append(discarded)
        else:
            remaining_proposals.append(proposal)

    found.status = ProposalStatus.DISCARDED
    resolved_proposals = _merge_resolved_proposals(
        _parse_proposals(state.get("resolved_proposals", [])),
        discarded_proposals,
    )
    merged_proposals = _compose_proposals(remaining_proposals, [], resolved_proposals)

    state["proposals"] = _proposal_payload(merged_proposals)
    state["resolved_proposals"] = _proposal_payload(resolved_proposals)
    if state.get("review_result"):
        review_result = ReviewResult.model_validate(state["review_result"])
        review_result.recommended_actions = [proposal.model_copy(deep=True) for proposal in merged_proposals]
        state["review_result"] = review_result.model_dump(mode="json")
    _normalize_job_state(state)
    save_job_state(state)
    jobs_db[job_id] = state
    return found


@router.post("/{job_id}/rerun", response_model=ComparisonResponse)
async def rerun_job(job_id: str, request: RerunRequest):
    if not request.proposal_ids:
        raise HTTPException(status_code=400, detail="proposal_ids is required")
    return await _apply_and_compare(job_id, request.proposal_ids)


@router.get("/{job_id}/compare", response_model=ComparisonResponse)
async def compare_job(job_id: str):
    state = _get_job_state(job_id)
    stored = state.get("comparison")
    if stored:
        return ComparisonResponse.model_validate(stored)

    before = _load_baseline_summary(state)
    after = _load_review_summary(state)
    if before is None or after is None:
        raise HTTPException(status_code=404, detail="Comparison data not found")
    applied_proposals = [ReviewAction.model_validate(item) for item in state.get("last_applied_proposals", [])]
    comparison = build_comparison(
        job_id=job_id,
        before=before,
        after=after,
        applied_proposals=applied_proposals,
    )
    state["comparison"] = comparison.model_dump(mode="json")
    save_job_state(state)
    jobs_db[job_id] = state
    return comparison


@router.get("/{job_id}/boundary", response_model=BoundarySnapshot)
async def get_job_boundary(job_id: str, grid_resolution: int = 40):
    state = _get_job_state(job_id)
    result_path = _resolve_result_path(state)
    if result_path is None or not result_path.exists():
        raise HTTPException(status_code=404, detail="Job result not found")

    request = JobRequest.model_validate(state["current_request"])
    source_df = _load_source_df(Path(state["source_path"]), state["sheet_name"])
    result_df = _read_dataframe(result_path)
    try:
        return build_boundary_snapshot(
            job_id=job_id,
            source_df=source_df,
            result_df=result_df,
            request=request,
            grid_resolution=grid_resolution,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{job_id}/export.xlsx")
async def export_job(job_id: str):
    state = _get_job_state(job_id)
    xlsx_path = _resolve_result_xlsx_path(state)
    if xlsx_path is None or not xlsx_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(
        path=str(xlsx_path),
        filename=f"{job_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


async def _apply_and_compare(job_id: str, proposal_ids: list[str]) -> ComparisonResponse:
    state = _get_job_state(job_id)
    try:
        previous_proposals = _parse_proposals(state.get("proposals", []))
        previous_resolved_proposals = _parse_proposals(state.get("resolved_proposals", []))
        (
            new_request,
            rerun_df,
            rerun_metadata,
            review_result,
            baseline_summary,
            current_summary,
            applied_proposals,
        ) = apply_proposals_and_rerun(job_state=state, proposal_ids=proposal_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    current_csv_path, current_xlsx_path = save_result_artifacts(job_id, rerun_df, name="current")
    comparison = build_comparison(
        job_id=job_id,
        before=baseline_summary,
        after=current_summary,
        applied_proposals=applied_proposals,
    )
    resolved_proposals = _merge_resolved_proposals(previous_resolved_proposals, applied_proposals)
    merged_proposals = _compose_proposals(
        previous_proposals,
        review_result.recommended_actions,
        resolved_proposals,
    )
    review_result.recommended_actions = merged_proposals
    save_review_artifacts(
        artifact_dir=_job_dir(job_id),
        summary=current_summary,
        review_result=review_result,
    )

    state.update(
        {
            "status": "completed",
            "current_request": new_request.model_dump(mode="json"),
            "metadata": rerun_metadata,
            "result_path": str(current_csv_path),
            "result_xlsx_path": str(current_xlsx_path),
            "review_summary": current_summary.model_dump(mode="json"),
            "review_result": review_result.model_dump(mode="json"),
            "proposals": [proposal.model_dump(mode="json") for proposal in merged_proposals],
            "resolved_proposals": [proposal.model_dump(mode="json") for proposal in resolved_proposals],
            "last_applied_proposals": [proposal.model_dump(mode="json") for proposal in applied_proposals],
            "comparison": comparison.model_dump(mode="json"),
        }
    )
    _normalize_job_state(state)
    save_job_state(state)
    jobs_db[job_id] = state
    return comparison


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


def _read_dataframe(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    return pd.read_csv(path)


def _dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


def _get_job_state(job_id: str) -> dict[str, Any]:
    state = jobs_db.get(job_id)
    if state is None:
        state = load_job_state(job_id)
        if state is not None:
            jobs_db[job_id] = state
    if state is not None and _normalize_job_state(state):
        save_job_state(state)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return state


def _job_dir(job_id: str) -> Path:
    return RESULT_DIR / job_id


def _resolve_result_path(state: dict[str, Any]) -> Path | None:
    result_path = state.get("result_path")
    if result_path:
        return Path(result_path)
    legacy_csv = RESULT_DIR / f"{state['job_id']}.csv"
    legacy_xlsx = RESULT_DIR / f"{state['job_id']}.xlsx"
    if legacy_csv.exists():
        return legacy_csv
    if legacy_xlsx.exists():
        return legacy_xlsx
    return None


def _resolve_result_xlsx_path(state: dict[str, Any]) -> Path | None:
    result_xlsx_path = state.get("result_xlsx_path")
    if result_xlsx_path:
        return Path(result_xlsx_path)
    legacy_xlsx = RESULT_DIR / f"{state['job_id']}.xlsx"
    if legacy_xlsx.exists():
        return legacy_xlsx
    return None


def _load_review_summary(state: dict[str, Any]) -> ReviewSummary | None:
    if state.get("review_summary"):
        return ReviewSummary.model_validate(state["review_summary"])
    review_summary_path = _job_dir(state["job_id"]) / "review-summary.json"
    if review_summary_path.exists():
        return ReviewSummary.model_validate_json(review_summary_path.read_text(encoding="utf-8"))
    return None


def _load_review_result(state: dict[str, Any]) -> ReviewResult | None:
    if state.get("review_result"):
        return ReviewResult.model_validate(state["review_result"])
    review_result_path = _job_dir(state["job_id"]) / "review-result.json"
    if review_result_path.exists():
        return ReviewResult.model_validate_json(review_result_path.read_text(encoding="utf-8"))
    return None


def _load_baseline_summary(state: dict[str, Any]) -> ReviewSummary | None:
    if state.get("baseline_summary"):
        return ReviewSummary.model_validate(state["baseline_summary"])

    baseline_result_path = state.get("baseline_result_path")
    if not baseline_result_path:
        return None

    baseline_request = JobRequest.model_validate(state["base_request"])
    source_df = _load_source_df(Path(state["source_path"]), state["sheet_name"])
    baseline_df = _read_dataframe(Path(baseline_result_path))
    return build_review_summary(
        job_id=state["job_id"],
        workbook_id=state["workbook_id"],
        sheet_name=state["sheet_name"],
        request=baseline_request,
        source_df=source_df,
        result_df=baseline_df,
        metadata=state.get("baseline_metadata", state.get("metadata", {})),
    )


def _rebuild_review_summary(state: dict[str, Any]) -> ReviewSummary:
    request = JobRequest.model_validate(state["current_request"])
    source_df = _load_source_df(Path(state["source_path"]), state["sheet_name"])
    result_df = _read_dataframe(Path(state["result_path"]))
    return build_review_summary(
        job_id=state["job_id"],
        workbook_id=state["workbook_id"],
        sheet_name=state["sheet_name"],
        request=request,
        source_df=source_df,
        result_df=result_df,
        metadata=state.get("metadata", {}),
    )


def _compose_proposals(
    existing_proposals: list[ReviewAction],
    new_proposals: list[ReviewAction],
    resolved_proposals: list[ReviewAction] | None = None,
) -> list[ReviewAction]:
    existing_models = [ReviewAction.model_validate(item) for item in existing_proposals]
    resolved_models = _merge_resolved_proposals(resolved_proposals or [], existing_models)
    completed_keys = _completed_proposal_keys(resolved_models)

    active_new: list[ReviewAction] = []
    for proposal in new_proposals:
        if proposal_key(proposal) in completed_keys:
            continue
        item = proposal.model_copy(deep=True)
        item.status = ProposalStatus.PENDING
        active_new.append(item)

    active_existing: list[ReviewAction] = []
    for proposal in existing_models:
        if proposal.status != ProposalStatus.PENDING or proposal_key(proposal) in completed_keys:
            continue
        item = proposal.model_copy(deep=True)
        item.status = ProposalStatus.PENDING
        active_existing.append(item)

    return _normalize_proposals(active_new + active_existing)
