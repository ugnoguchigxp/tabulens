from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import ValidationError

from app.models.schemas import (
    ModelReviewAction,
    ModelReviewActionType,
    ModelReviewAssessment,
    ModelReviewComparison,
    ModelReviewResult,
    ModelReviewSummary,
    ModelWorkflowRequest,
    ProposalStatus,
    UseCaseType,
)
from app.services.llm.nano_explainer import review_model_workflow_summary
from app.services.ml.model_workflows import run_model_workflow

SUPPORTED_RETRAIN_ACTIONS = {
    ModelReviewActionType.REBALANCE_CLASSES,
    ModelReviewActionType.INCREASE_TEST_SIZE,
    ModelReviewActionType.SWITCH_ALGORITHM,
    ModelReviewActionType.NORMALIZE_FEATURES,
}


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def build_model_review_summary(
    *,
    workflow_id: str,
    workbook_id: str,
    sheet_name: str,
    request: ModelWorkflowRequest,
    result_df: pd.DataFrame,
    metadata: dict[str, Any],
    source_job_id: str | None = None,
    resolved_actions: list[ModelReviewAction] | None = None,
) -> ModelReviewSummary:
    use_case = request.use_case
    feature_columns = [col for col in request.mapping.feature_columns if col in result_df.columns]
    label_column = request.mapping.label_column if request.mapping.label_column in result_df.columns else None
    metrics = _to_jsonable(metadata.get("metrics", {}))
    if not isinstance(metrics, dict):
        metrics = {}

    train_count = int(metrics.get("train_count", metadata.get("train_count", 0)) or 0)
    test_count = int(metrics.get("test_count", metadata.get("test_count", 0)) or 0)
    unused_count = int(metrics.get("unused_count", metadata.get("unused_count", 0)) or 0)

    quality_flags = _build_quality_flags(use_case, result_df, metrics, label_column)
    diagnostics = _build_diagnostics(use_case, result_df, metrics, label_column)
    feature_importance = _build_feature_importance(metadata.get("feature_importance"))
    sample_errors = _build_sample_records(result_df, label_column, kind="error")
    sample_low_confidence = _build_sample_records(result_df, label_column, kind="low_confidence")
    sample_outliers = _build_sample_records(result_df, label_column, kind="outlier")

    split_summary = {
        "train_count": train_count,
        "test_count": test_count,
        "unused_count": unused_count,
        "train_ratio": float(train_count / max(1, train_count + test_count + unused_count)),
        "test_ratio": float(test_count / max(1, train_count + test_count + unused_count)),
        "unused_ratio": float(unused_count / max(1, train_count + test_count + unused_count)),
    }

    boundary_summary = _build_boundary_summary(use_case, result_df, metrics, label_column)

    metadata_payload = {
        "source_kind": metadata.get("source_kind"),
        "source_path": metadata.get("source_path"),
        "task_type": metadata.get("task_type"),
        "previous_review_actions": [action.model_dump(mode="json") for action in resolved_actions or []],
        "raw_metrics": metrics,
    }

    return ModelReviewSummary(
        workflow_id=workflow_id,
        source_job_id=source_job_id,
        workbook_id=workbook_id,
        sheet_name=sheet_name,
        use_case=use_case,
        algorithm=str(metadata.get("algorithm", request.algorithm)),
        row_count=int(len(result_df)),
        train_count=train_count,
        test_count=test_count,
        unused_count=unused_count,
        feature_columns=feature_columns,
        label_column=label_column,
        metrics=metrics,
        quality_flags=quality_flags,
        diagnostics=diagnostics,
        feature_importance=feature_importance,
        sample_errors=sample_errors,
        sample_low_confidence=sample_low_confidence,
        sample_outliers=sample_outliers,
        boundary_summary=boundary_summary,
        split_summary=split_summary,
        metadata=metadata_payload,
    )


def review_model_workflow(
    *,
    summary: ModelReviewSummary,
    fallback_only: bool = False,
) -> ModelReviewResult:
    summary_payload = summary.model_dump(mode="json")
    fallback_payload = review_model_workflow_summary(summary_payload, force_fallback=True)
    review_payload = fallback_payload if fallback_only else review_model_workflow_summary(summary_payload)

    try:
        review_result = ModelReviewResult.model_validate(review_payload)
    except ValidationError:
        review_result = ModelReviewResult.model_validate(fallback_payload)

    review_result.summary = summary
    if not review_result.recommended_actions:
        review_result.recommended_actions = ModelReviewResult.model_validate(fallback_payload).recommended_actions

    for proposal in review_result.recommended_actions:
        proposal.status = ProposalStatus.PENDING
        proposal.safe_to_apply = proposal.safe_to_apply and proposal.action in SUPPORTED_RETRAIN_ACTIONS

    if review_result.assessment == ModelReviewAssessment.PASS and review_result.blocking_factors:
        review_result.assessment = ModelReviewAssessment.NEEDS_IMPROVEMENT
    if not review_result.source:
        review_result.source = "fallback" if fallback_only else "openai"
    if review_result.assessment == ModelReviewAssessment.PASS:
        review_result.safe_to_promote = True
    return review_result


def save_model_review_artifacts(
    *,
    artifact_dir: Path,
    summary: ModelReviewSummary,
    review_result: ModelReviewResult,
    comparison: ModelReviewComparison | None = None,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    save_json(artifact_dir / "model_review_summary.json", summary)
    save_json(artifact_dir / "model_review_result.json", review_result)
    save_json(artifact_dir / "model_review_actions.json", review_result.recommended_actions)
    if comparison is not None:
        save_json(artifact_dir / "model_review_comparison.json", comparison)


def proposal_key(proposal: ModelReviewAction) -> str:
    payload = {
        "action": proposal.action.value if hasattr(proposal.action, "value") else str(proposal.action),
        "target": _normalize_for_key(proposal.target),
        "params": _normalize_for_key(proposal.params or {}),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def merge_proposal_statuses(
    proposals: list[ModelReviewAction],
    status_map: dict[str, ProposalStatus | str] | None,
) -> list[ModelReviewAction]:
    if not status_map:
        return [proposal.model_copy(deep=True) for proposal in proposals]

    normalized_status_map: dict[str, ProposalStatus] = {}
    for key, status in status_map.items():
        try:
            normalized_status_map[str(key)] = status if isinstance(status, ProposalStatus) else ProposalStatus(str(status))
        except ValueError:
            continue

    merged: list[ModelReviewAction] = []
    for proposal in proposals:
        item = proposal.model_copy(deep=True)
        key = proposal_key(item)
        if key in normalized_status_map:
            item.status = normalized_status_map[key]
        merged.append(item)
    return merged


def build_comparison(
    *,
    workflow_id: str,
    before_workflow_id: str,
    after_workflow_id: str,
    before: ModelReviewSummary,
    after: ModelReviewSummary,
    applied_actions: list[ModelReviewAction],
) -> ModelReviewComparison:
    deltas = _build_deltas(before, after)
    accepted = _compare_acceptance(before, after)
    return ModelReviewComparison(
        workflow_id=workflow_id,
        before_workflow_id=before_workflow_id,
        after_workflow_id=after_workflow_id,
        before=before,
        after=after,
        deltas=deltas,
        applied_actions=applied_actions,
        accepted=accepted,
    )


def apply_proposals_and_rerun(
    *,
    workflow_state: dict[str, Any],
    proposal_ids: list[str],
    source_df: pd.DataFrame,
    rerun_workflow_id: str,
) -> tuple[ModelWorkflowRequest, pd.DataFrame, dict[str, Any], ModelReviewResult, ModelReviewSummary, ModelReviewSummary, list[ModelReviewAction], str]:
    if not proposal_ids:
        raise ValueError("At least one proposal_id must be provided")

    current_request = ModelWorkflowRequest.model_validate(workflow_state["request"])
    current_result_df = _load_dataframe_for_review(workflow_state)
    active_proposals = _parse_proposals(workflow_state.get("model_review_proposals", []))

    applied_proposals: list[ModelReviewAction] = []
    next_request = current_request.model_copy(deep=True)
    filtered_source_df = source_df.copy()
    rows_to_drop: set[int] = set()

    for proposal_id in proposal_ids:
        proposal = next((item for item in active_proposals if item.proposal_id == proposal_id), None)
        if proposal is None:
            raise ValueError(f"Proposal not found: {proposal_id}")
        if proposal.status == ProposalStatus.DISCARDED:
            raise ValueError(f"Proposal has been discarded: {proposal_id}")
        if proposal.action == ModelReviewActionType.REVIEW_LABEL_QUALITY:
            raise ValueError(f"Proposal is not actionable: {proposal_id}")

        next_request, filtered_source_df = _apply_single_proposal(
            current_request=next_request,
            source_df=filtered_source_df,
            current_result_df=current_result_df,
            proposal=proposal,
        )
        applied = proposal.model_copy(deep=True)
        applied.status = ProposalStatus.APPLIED
        applied_proposals.append(applied)
        if proposal.action == ModelReviewActionType.REBALANCE_CLASSES:
            next_request.params["class_weight"] = "balanced"

    rerun_df, rerun_metadata = run_model_workflow(filtered_source_df, next_request, rerun_workflow_id)

    before_summary = build_model_review_summary(
        workflow_id=str(workflow_state["workflow_id"]),
        workbook_id=workflow_state["workbook_id"],
        sheet_name=workflow_state["sheet_name"],
        request=current_request,
        result_df=current_result_df,
        metadata=workflow_state.get("metadata", {}),
        source_job_id=workflow_state.get("source_job_id"),
        resolved_actions=_parse_proposals(workflow_state.get("resolved_model_review_proposals", [])),
    )
    after_summary = build_model_review_summary(
        workflow_id=rerun_workflow_id,
        workbook_id=workflow_state["workbook_id"],
        sheet_name=workflow_state["sheet_name"],
        request=next_request,
        result_df=rerun_df.result_df,
        metadata={**workflow_state.get("metadata", {}), **rerun_metadata},
        source_job_id=workflow_state.get("source_job_id"),
        resolved_actions=applied_proposals,
    )
    review_result = review_model_workflow(summary=after_summary)
    comparison = build_comparison(
        workflow_id=str(workflow_state["workflow_id"]),
        before_workflow_id=str(workflow_state["workflow_id"]),
        after_workflow_id=rerun_workflow_id,
        before=before_summary,
        after=after_summary,
        applied_actions=applied_proposals,
    )
    return next_request, rerun_df.result_df, rerun_metadata, review_result, before_summary, after_summary, applied_proposals, rerun_workflow_id


def build_resolved_status_map(proposals: list[ModelReviewAction]) -> dict[str, ProposalStatus]:
    status_map: dict[str, ProposalStatus] = {}
    for proposal in proposals:
        if proposal.status in {ProposalStatus.APPLIED, ProposalStatus.DISCARDED}:
            status_map[proposal_key(proposal)] = proposal.status
    return status_map


def merge_active_proposals(
    proposals: list[ModelReviewAction],
    resolved_proposals: list[ModelReviewAction] | None = None,
) -> list[ModelReviewAction]:
    resolved = resolved_proposals or []
    resolved_keys = {proposal_key(proposal) for proposal in resolved if proposal.status in {ProposalStatus.APPLIED, ProposalStatus.DISCARDED}}
    active: list[ModelReviewAction] = []
    seen: set[str] = set()
    for proposal in proposals:
        item = proposal.model_copy(deep=True)
        key = proposal_key(item)
        if key in resolved_keys or key in seen:
            continue
        seen.add(key)
        if item.status == ProposalStatus.PENDING:
            active.append(item)
    return active


def _parse_proposals(raw_proposals: Any) -> list[ModelReviewAction]:
    if not isinstance(raw_proposals, list):
        return []

    proposals: list[ModelReviewAction] = []
    for item in raw_proposals:
        try:
            proposals.append(ModelReviewAction.model_validate(item))
        except Exception:
            continue
    return proposals


def _load_dataframe_for_review(workflow_state: dict[str, Any]) -> pd.DataFrame:
    result_path = workflow_state.get("result_path")
    if not result_path:
        raise ValueError("Workflow result not found")
    path = Path(result_path)
    if not path.exists():
        raise ValueError("Workflow result file not found")
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path)
    return pd.read_csv(path)


def _apply_single_proposal(
    *,
    current_request: ModelWorkflowRequest,
    source_df: pd.DataFrame,
    current_result_df: pd.DataFrame,
    proposal: ModelReviewAction,
) -> tuple[ModelWorkflowRequest, pd.DataFrame]:
    next_request = current_request.model_copy(deep=True)
    filtered_source_df = source_df.copy()

    if proposal.action == ModelReviewActionType.REBALANCE_CLASSES:
        next_request.params["class_weight"] = "balanced"
        return next_request, filtered_source_df

    if proposal.action == ModelReviewActionType.INCREASE_TEST_SIZE:
        split_mode = str(next_request.params.get("split_mode", "ratio")).lower()
        if split_mode == "count":
            total_rows = len(current_result_df)
            current_test = int(next_request.params.get("test_size", max(1, total_rows // 5)) or max(1, total_rows // 5))
            next_request.params["test_size"] = min(total_rows - 1, max(current_test + max(1, total_rows // 10), current_test + 1))
        else:
            current_test = float(next_request.params.get("test_size", 0.2) or 0.2)
            next_test = min(0.4, max(current_test + 0.1, 0.2))
            next_request.params["test_size"] = round(next_test, 3)
            next_request.params["train_size"] = round(max(0.1, 1 - next_test), 3)
        return next_request, filtered_source_df

    if proposal.action == ModelReviewActionType.SWITCH_ALGORITHM:
        next_request.algorithm = str(proposal.params.get("algorithm") or _suggest_algorithm(next_request))
        return next_request, filtered_source_df

    if proposal.action == ModelReviewActionType.NORMALIZE_FEATURES:
        next_request.preprocessing.normalization = str(proposal.params.get("normalization") or _suggest_normalization(next_request))
        return next_request, filtered_source_df

    if proposal.action == ModelReviewActionType.TUNE_HYPERPARAMETERS:
        params = proposal.params or {}
        for key, value in params.items():
            next_request.params[key] = value
        return next_request, filtered_source_df

    raise ValueError(f"Unsupported proposal action: {proposal.action}")


def _suggest_algorithm(request: ModelWorkflowRequest) -> str:
    if request.use_case == UseCaseType.CLASSIFICATION:
        return "gradient_boosting" if request.algorithm != "gradient_boosting" else "random_forest"
    if request.use_case == UseCaseType.PREDICTION:
        return "random_forest" if request.algorithm != "random_forest" else "linear_regression"
    return str(request.algorithm or "random_forest")


def _suggest_normalization(request: ModelWorkflowRequest) -> str:
    current = str(getattr(request.preprocessing, "normalization", "minmax"))
    if current == "standard":
        return "minmax"
    return "standard"


def _build_quality_flags(
    use_case: UseCaseType,
    result_df: pd.DataFrame,
    metrics: dict[str, Any],
    label_column: str | None,
) -> list[str]:
    flags: list[str] = []
    if len(result_df) < 30:
        flags.append("small_sample")

    if use_case == UseCaseType.CLASSIFICATION:
        accuracy = float(metrics.get("accuracy", 0.0) or 0.0)
        balanced_accuracy = float(metrics.get("balanced_accuracy", 0.0) or 0.0)
        train_accuracy = float(metrics.get("train_accuracy", 0.0) or 0.0)
        test_accuracy = float(metrics.get("test_accuracy", accuracy) or accuracy)
        confidence_mean = float(metrics.get("confidence_mean", _series_mean(result_df.get("_prediction_confidence"))) or 0.0)
        class_imbalance = _class_imbalance_ratio(result_df, label_column)
        if accuracy and accuracy < 0.65:
            flags.append("low_accuracy")
        if balanced_accuracy and balanced_accuracy < 0.6:
            flags.append("low_balanced_accuracy")
        if confidence_mean and confidence_mean < 0.65:
            flags.append("low_confidence")
        if train_accuracy and test_accuracy and train_accuracy - test_accuracy > 0.15:
            flags.append("train_test_gap")
        if class_imbalance >= 5:
            flags.append("class_imbalance")
        confusion_matrix = metrics.get("confusion_matrix") or {}
        if isinstance(confusion_matrix, dict) and confusion_matrix.get("matrix"):
            flags.append("confusion_matrix_available")
        return flags

    if use_case == UseCaseType.PREDICTION:
        r2 = float(metrics.get("r2", 0.0) or 0.0)
        mae = float(metrics.get("mae", 0.0) or 0.0)
        train_r2 = float(metrics.get("train_r2", 0.0) or 0.0)
        test_r2 = float(metrics.get("test_r2", r2) or r2)
        residual_mean = float(metrics.get("residual_mean", 0.0) or 0.0)
        residual_std = float(metrics.get("residual_std", 0.0) or 0.0)
        if r2 < 0.3:
            flags.append("low_r2")
        if mae and residual_std and mae > residual_std:
            flags.append("high_error")
        if abs(residual_mean) > max(1e-6, residual_std * 0.25):
            flags.append("residual_bias")
        if train_r2 and test_r2 and train_r2 - test_r2 > 0.15:
            flags.append("train_test_gap")
        if _target_is_constant(result_df, label_column):
            flags.append("constant_target")
        return flags

    return flags


def _build_diagnostics(
    use_case: UseCaseType,
    result_df: pd.DataFrame,
    metrics: dict[str, Any],
    label_column: str | None,
) -> dict[str, Any]:
    if use_case == UseCaseType.CLASSIFICATION:
        confidence = result_df.get("_prediction_confidence")
        test_rows = result_df[result_df.get("_split_role", "unused") == "test"] if "_split_role" in result_df.columns else result_df
        error_rows = result_df[result_df.get("_error_flag", False)] if "_error_flag" in result_df.columns else pd.DataFrame()
        return {
            "accuracy": metrics.get("accuracy"),
            "balanced_accuracy": metrics.get("balanced_accuracy"),
            "train_accuracy": metrics.get("train_accuracy"),
            "test_accuracy": metrics.get("test_accuracy"),
            "confidence_mean": _series_mean(confidence),
            "confidence_p10": _series_quantile(confidence, 0.1),
            "confidence_p90": _series_quantile(confidence, 0.9),
            "misclassified_count": int(len(error_rows)) if len(error_rows) else int(result_df.get("_error_flag", pd.Series(dtype=bool)).sum()),
            "test_count": int(len(test_rows)),
            "class_imbalance_ratio": _class_imbalance_ratio(result_df, label_column),
        }

    if use_case == UseCaseType.PREDICTION:
        residual = result_df.get("_residual")
        abs_error = result_df.get("_absolute_error")
        return {
            "mae": metrics.get("mae"),
            "rmse": metrics.get("rmse"),
            "r2": metrics.get("r2"),
            "train_r2": metrics.get("train_r2"),
            "test_r2": metrics.get("test_r2"),
            "residual_mean": metrics.get("residual_mean"),
            "residual_std": metrics.get("residual_std"),
            "residual_p10": _series_quantile(residual, 0.1),
            "residual_p90": _series_quantile(residual, 0.9),
            "absolute_error_p90": _series_quantile(abs_error, 0.9),
        }

    return {
        "metrics": metrics,
        "row_count": int(len(result_df)),
    }


def _build_feature_importance(raw_importance: Any) -> list[dict[str, Any]]:
    if isinstance(raw_importance, dict):
        items = sorted(raw_importance.items(), key=lambda item: float(item[1]), reverse=True)
        return [{"feature": str(feature), "score": float(score)} for feature, score in items[:10]]
    if isinstance(raw_importance, list):
        normalized: list[dict[str, Any]] = []
        for item in raw_importance[:10]:
            if isinstance(item, dict) and "feature" in item:
                normalized.append({"feature": str(item["feature"]), "score": float(item.get("score", 0.0) or 0.0)})
        return normalized
    return []


def _build_sample_records(result_df: pd.DataFrame, label_column: str | None, *, kind: str) -> list[dict[str, Any]]:
    if kind == "error":
        if "_error_flag" in result_df.columns:
            subset = result_df.loc[result_df["_error_flag"] == True]  # noqa: E712
        elif "_absolute_error" in result_df.columns:
            subset = result_df.sort_values("_absolute_error", ascending=False)
        else:
            subset = pd.DataFrame()
    elif kind == "low_confidence":
        if "_prediction_confidence" in result_df.columns:
            subset = result_df.sort_values("_prediction_confidence", ascending=True)
        elif "_absolute_error" in result_df.columns:
            subset = result_df.sort_values("_absolute_error", ascending=False)
        else:
            subset = pd.DataFrame()
    else:
        if "_is_outlier" in result_df.columns:
            subset = result_df.loc[result_df["_is_outlier"] == True]  # noqa: E712
        elif "_is_island" in result_df.columns:
            subset = result_df.loc[result_df["_is_island"] == True]  # noqa: E712
        else:
            subset = pd.DataFrame()

    if subset.empty:
        return []

    records: list[dict[str, Any]] = []
    for _, row in subset.head(5).iterrows():
        record: dict[str, Any] = {}
        if "_row_id" in row:
            record["row_id"] = int(row["_row_id"])
        if label_column and label_column in row.index:
            record["label"] = _to_jsonable(row[label_column])
        if "_predicted_class" in row.index:
            record["predicted"] = _to_jsonable(row["_predicted_class"])
        if "_prediction_confidence" in row.index:
            record["confidence"] = _safe_float(row["_prediction_confidence"])
        if "_predicted_value" in row.index:
            record["predicted_value"] = _safe_float(row["_predicted_value"])
        if "_actual_value" in row.index:
            record["actual_value"] = _safe_float(row["_actual_value"])
        if "_residual" in row.index:
            record["residual"] = _safe_float(row["_residual"])
        if "_absolute_error" in row.index:
            record["absolute_error"] = _safe_float(row["_absolute_error"])
        if "_split_role" in row.index:
            record["split_role"] = _to_jsonable(row["_split_role"])
        if "_cluster_id" in row.index:
            record["cluster_id"] = _to_jsonable(row["_cluster_id"])
        if "_is_outlier" in row.index:
            record["is_outlier"] = bool(row["_is_outlier"])
        if "_is_island" in row.index:
            record["is_island"] = bool(row["_is_island"])
        records.append(record)
    return records


def _build_boundary_summary(
    use_case: UseCaseType,
    result_df: pd.DataFrame,
    metrics: dict[str, Any],
    label_column: str | None,
) -> dict[str, Any]:
    if use_case == UseCaseType.CLASSIFICATION:
        class_labels = []
        if label_column and label_column in result_df.columns:
            class_labels = [str(value) for value in pd.Series(result_df[label_column]).dropna().astype(str).unique().tolist()]
        return {
            "class_labels": class_labels,
            "confusion_matrix": metrics.get("confusion_matrix", {}),
            "misclassified_count": int(result_df.get("_error_flag", pd.Series(dtype=bool)).sum()) if "_error_flag" in result_df.columns else 0,
            "low_confidence_count": int((result_df.get("_prediction_confidence", pd.Series(dtype=float)) < 0.65).sum()) if "_prediction_confidence" in result_df.columns else 0,
        }
    if use_case == UseCaseType.PREDICTION:
        return {
            "residual_mean": metrics.get("residual_mean"),
            "residual_std": metrics.get("residual_std"),
            "absolute_error_p90": _series_quantile(result_df.get("_absolute_error"), 0.9),
        }
    return {"metrics": metrics}


def _compare_acceptance(before: ModelReviewSummary, after: ModelReviewSummary) -> bool:
    if before.use_case == UseCaseType.CLASSIFICATION:
        before_key = _classification_score(before.metrics)
        after_key = _classification_score(after.metrics)
        return after_key >= before_key and after.metrics.get("test_accuracy", 0.0) >= before.metrics.get("test_accuracy", 0.0) - 0.05
    if before.use_case == UseCaseType.PREDICTION:
        before_key = _prediction_score(before.metrics)
        after_key = _prediction_score(after.metrics)
        return after_key >= before_key
    return after.row_count >= before.row_count


def _classification_score(metrics: dict[str, Any]) -> float:
    balanced = float(metrics.get("balanced_accuracy", 0.0) or 0.0)
    f1 = float(metrics.get("f1", 0.0) or 0.0)
    accuracy = float(metrics.get("accuracy", 0.0) or 0.0)
    confidence = float(metrics.get("confidence_mean", 0.0) or 0.0)
    return balanced * 0.4 + f1 * 0.3 + accuracy * 0.2 + confidence * 0.1


def _prediction_score(metrics: dict[str, Any]) -> float:
    r2 = float(metrics.get("r2", 0.0) or 0.0)
    mae = float(metrics.get("mae", 0.0) or 0.0)
    rmse = float(metrics.get("rmse", 0.0) or 0.0)
    residual_bias = abs(float(metrics.get("residual_mean", 0.0) or 0.0))
    return r2 * 0.5 - mae * 0.2 - rmse * 0.2 - residual_bias * 0.1


def _build_deltas(before: ModelReviewSummary, after: ModelReviewSummary) -> dict[str, Any]:
    deltas: dict[str, Any] = {
        "row_count": after.row_count - before.row_count,
        "train_count": after.train_count - before.train_count,
        "test_count": after.test_count - before.test_count,
        "unused_count": after.unused_count - before.unused_count,
    }
    if before.use_case == UseCaseType.CLASSIFICATION:
        for key in ["accuracy", "balanced_accuracy", "precision", "recall", "f1", "confidence_mean", "train_accuracy", "test_accuracy"]:
            deltas[key] = float(after.metrics.get(key, 0.0) or 0.0) - float(before.metrics.get(key, 0.0) or 0.0)
        deltas["train_test_gap"] = float(after.metrics.get("train_accuracy", 0.0) or 0.0) - float(after.metrics.get("test_accuracy", 0.0) or 0.0)
        return deltas
    if before.use_case == UseCaseType.PREDICTION:
        for key in ["mae", "rmse", "r2", "residual_mean", "residual_std", "train_mae", "test_mae", "train_r2", "test_r2"]:
            deltas[key] = float(after.metrics.get(key, 0.0) or 0.0) - float(before.metrics.get(key, 0.0) or 0.0)
        return deltas
    return deltas


def _class_imbalance_ratio(result_df: pd.DataFrame, label_column: str | None) -> float:
    if not label_column or label_column not in result_df.columns:
        return 0.0
    counts = result_df[label_column].astype(str).value_counts()
    if counts.empty or counts.min() == 0:
        return 0.0
    return float(counts.max() / counts.min())


def _target_is_constant(result_df: pd.DataFrame, label_column: str | None) -> bool:
    if not label_column or label_column not in result_df.columns:
        return False
    series = pd.to_numeric(result_df[label_column], errors="coerce")
    if series.notna().sum() == 0:
        return False
    return bool(series.nunique(dropna=True) <= 1)


def _series_mean(series: pd.Series | None) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(pd.to_numeric(series, errors="coerce").mean())


def _series_quantile(series: pd.Series | None, quantile: float) -> float:
    if series is None or len(series) == 0:
        return 0.0
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        return 0.0
    return float(numeric.quantile(quantile))


def _safe_float(value: Any) -> float:
    try:
        numeric = float(value)
    except Exception:
        return 0.0
    if not np.isfinite(numeric):
        return 0.0
    return numeric


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, np.floating) and not np.isfinite(value):
        return None
    if hasattr(value, "model_dump"):
        try:
            return _to_jsonable(value.model_dump(mode="json"))
        except TypeError:
            return _to_jsonable(value.model_dump())
    if hasattr(value, "value") and type(value).__name__ != "str":
        try:
            return value.value
        except Exception:
            return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _normalize_for_key(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_for_key(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        normalized = [_normalize_for_key(item) for item in value]
        if all(not isinstance(item, (dict, list)) for item in normalized):
            return sorted(normalized, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, default=str))
        return normalized
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "value") and type(value).__name__ != "str":
        try:
            return value.value
        except Exception:
            return str(value)
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value
