from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ValidationError

from app.models.schemas import (
    AlgorithmType,
    ClusterSummary,
    ComparisonResponse,
    ConfidenceStats,
    DistributionItem,
    JobRequest,
    ProposalStatus,
    RepresentativeRow,
    ReviewAction,
    ReviewActionType,
    ReviewAssessment,
    ReviewResult,
    ReviewSummary,
    ScoreItem,
)
from app.services.llm.nano_explainer import review_job_summary
from app.services.ml.classifier import run_analysis


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_to_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def build_review_summary(
    *,
    job_id: str,
    workbook_id: str,
    sheet_name: str,
    request: JobRequest,
    source_df: pd.DataFrame,
    result_df: pd.DataFrame,
    metadata: dict[str, Any],
) -> ReviewSummary:
    feature_columns = [col for col in request.mapping.feature_columns if col in source_df.columns]
    label_column = request.mapping.label_column if request.mapping.label_column in source_df.columns else None
    algorithm_value = getattr(request.algorithm, "value", str(request.algorithm))

    missing_rate = 0.0
    if feature_columns:
        missing_rate = float(source_df[feature_columns].isna().mean().mean())

    outlier_rate = float(result_df["_is_outlier"].mean()) if "_is_outlier" in result_df else 0.0
    island_rate = float(result_df["_is_island"].mean()) if "_is_island" in result_df else 0.0

    class_distribution = _build_class_distribution(source_df, label_column)
    confidence_stats = _build_confidence_stats(result_df)
    feature_importance_top = _build_feature_importance_top(metadata)
    cluster_summary = _build_cluster_summary(result_df)
    representative_rows = _build_representative_rows(result_df, feature_columns, label_column)
    quality_flags = _build_quality_flags(
        source_df=source_df,
        result_df=result_df,
        feature_columns=feature_columns,
        label_column=label_column,
        confidence_stats=confidence_stats,
        class_distribution=class_distribution,
        metadata=metadata,
    )

    return ReviewSummary(
        job_id=job_id,
        workbook_id=workbook_id,
        sheet_name=sheet_name,
        algorithm=algorithm_value,
        row_count=int(len(result_df)),
        feature_count=int(len(feature_columns)),
        feature_columns=feature_columns,
        label_column=label_column,
        missing_rate=missing_rate,
        outlier_rate=outlier_rate,
        island_rate=island_rate,
        class_distribution=class_distribution,
        prediction_confidence=confidence_stats,
        feature_importance_top=feature_importance_top,
        cluster_summary=cluster_summary,
        representative_rows=representative_rows,
        quality_flags=quality_flags,
        metadata=_to_jsonable(metadata),
    )


def review_job(
    *,
    summary: ReviewSummary,
    fallback_only: bool = False,
) -> ReviewResult:
    summary_payload = summary.model_dump(mode="json")
    fallback_payload = review_job_summary(summary_payload, force_fallback=True)
    review_payload = fallback_payload if fallback_only else review_job_summary(summary_payload)

    try:
        review_result = ReviewResult.model_validate(review_payload)
    except ValidationError:
        review_result = ReviewResult.model_validate(fallback_payload)

    review_result.summary = summary
    if not review_result.recommended_actions:
        review_result.recommended_actions = ReviewResult.model_validate(fallback_payload).recommended_actions
    for proposal in review_result.recommended_actions:
        proposal.status = ProposalStatus.PENDING
    if review_result.assessment == ReviewAssessment.KEEP and review_result.blocking_factors:
        review_result.assessment = ReviewAssessment.NEEDS_IMPROVEMENT
    if not review_result.source:
        review_result.source = "fallback" if fallback_only else "openai"
    return review_result


def save_review_artifacts(
    *,
    artifact_dir: Path,
    summary: ReviewSummary,
    review_result: ReviewResult,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    save_json(artifact_dir / "review-summary.json", summary)
    save_json(artifact_dir / "review-result.json", review_result)
    save_json(artifact_dir / "review-actions.json", review_result.recommended_actions)


def proposal_key(proposal: ReviewAction) -> str:
    payload = {
        "action": _to_jsonable(proposal.action),
        "target": _normalize_for_key(proposal.target),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_proposal_status_map(proposals: list[ReviewAction]) -> dict[str, ProposalStatus]:
    status_map: dict[str, ProposalStatus] = {}
    for proposal in proposals:
        if proposal.status in {ProposalStatus.APPLIED, ProposalStatus.DISCARDED}:
            status_map[proposal_key(proposal)] = proposal.status
    return status_map


def merge_proposal_statuses(
    proposals: list[ReviewAction],
    status_map: dict[str, ProposalStatus | str] | None,
) -> list[ReviewAction]:
    if not status_map:
        return [proposal.model_copy(deep=True) for proposal in proposals]

    normalized_status_map: dict[str, ProposalStatus] = {}
    for key, status in status_map.items():
        try:
            normalized_status_map[str(key)] = status if isinstance(status, ProposalStatus) else ProposalStatus(str(status))
        except ValueError:
            continue

    merged: list[ReviewAction] = []
    for proposal in proposals:
        item = proposal.model_copy(deep=True)
        key = proposal_key(item)
        if key in normalized_status_map:
            item.status = normalized_status_map[key]
        merged.append(item)
    return merged


def apply_proposals_and_rerun(
    *,
    job_state: dict[str, Any],
    proposal_ids: list[str],
) -> tuple[JobRequest, pd.DataFrame, dict[str, Any], ReviewResult, ReviewSummary, ReviewSummary, list[ReviewAction]]:
    if not proposal_ids:
        raise ValueError("At least one proposal_id must be provided")

    current_request = JobRequest.model_validate(job_state["current_request"])
    source_df = _load_source_df(job_state["source_path"], job_state["sheet_name"])
    current_result_df = _load_result_df(job_state["result_path"])

    applied_proposals: list[ReviewAction] = []
    next_request = current_request.model_copy(deep=True)
    filtered_source_df = source_df.copy()
    rows_to_drop: set[int] = set()

    for proposal_id in proposal_ids:
        proposal = _find_proposal(job_state, proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal not found: {proposal_id}")
        if proposal.status == ProposalStatus.DISCARDED:
            raise ValueError(f"Proposal has been discarded: {proposal_id}")
        if proposal.action == ReviewActionType.REVIEW_MANUALLY:
            raise ValueError(f"Proposal is not actionable: {proposal_id}")

        next_request, filtered_source_df = _apply_single_proposal(
            current_request=next_request,
            source_df=filtered_source_df,
            current_result_df=current_result_df,
            proposal=proposal,
        )
        if proposal.action in {ReviewActionType.REMOVE_OUTLIERS, ReviewActionType.EXCLUDE_ISLANDS}:
            rows_to_drop.update(_rows_for_scope(current_result_df, proposal))
        applied = proposal.model_copy(deep=True)
        applied.status = ProposalStatus.APPLIED
        applied_proposals.append(applied)

    if not next_request.mapping.feature_columns:
        raise ValueError("No feature columns remain after applying proposals")

    if rows_to_drop:
        filtered_source_df = _drop_rows_by_source_row_id(source_df, rows_to_drop)

    rerun_df, rerun_metadata = run_analysis(
        filtered_source_df,
        next_request.mapping.feature_columns,
        next_request.mapping.label_column,
        algorithm=next_request.algorithm,
        preprocessing=next_request.preprocessing.model_dump() if hasattr(next_request.preprocessing, "model_dump") else next_request.preprocessing.dict(),
        run_cleansing=next_request.run_cleansing,
        run_feature_selection=next_request.run_feature_selection,
        run_ml=next_request.run_ml,
    )

    baseline_result_df = _load_result_df(job_state["baseline_result_path"])
    baseline_summary = build_review_summary(
        job_id=job_state["job_id"],
        workbook_id=job_state["workbook_id"],
        sheet_name=job_state["sheet_name"],
        request=JobRequest.model_validate(job_state["base_request"]),
        source_df=source_df,
        result_df=baseline_result_df,
        metadata=job_state.get("baseline_metadata", job_state.get("metadata", {})),
    )
    current_summary = build_review_summary(
        job_id=job_state["job_id"],
        workbook_id=job_state["workbook_id"],
        sheet_name=job_state["sheet_name"],
        request=next_request,
        source_df=filtered_source_df,
        result_df=rerun_df,
        metadata=rerun_metadata,
    )
    review_result = review_job(summary=current_summary)

    return next_request, rerun_df, rerun_metadata, review_result, baseline_summary, current_summary, applied_proposals


def build_comparison(
    *,
    job_id: str,
    before: ReviewSummary,
    after: ReviewSummary,
    applied_proposals: list[ReviewAction],
) -> ComparisonResponse:
    before_conf = before.prediction_confidence.mean
    after_conf = after.prediction_confidence.mean
    before_islands = sum(1 for item in before.cluster_summary if item.is_island)
    after_islands = sum(1 for item in after.cluster_summary if item.is_island)

    deltas = {
        "row_count": after.row_count - before.row_count,
        "missing_rate": after.missing_rate - before.missing_rate,
        "outlier_rate": after.outlier_rate - before.outlier_rate,
        "island_rate": after.island_rate - before.island_rate,
        "confidence_mean": after_conf - before_conf,
        "feature_count": after.feature_count - before.feature_count,
        "cluster_count": len(after.cluster_summary) - len(before.cluster_summary),
        "island_clusters": after_islands - before_islands,
    }
    accepted = (
        deltas["confidence_mean"] >= 0
        and deltas["outlier_rate"] <= 0
        and deltas["island_rate"] <= 0
    )
    return ComparisonResponse(
        job_id=job_id,
        before=before,
        after=after,
        deltas=deltas,
        applied_proposals=applied_proposals,
        accepted=accepted,
    )


def _load_source_df(source_path: str, sheet_name: str) -> pd.DataFrame:
    path = Path(source_path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path, sheet_name=sheet_name)


def _load_result_df(result_path: str) -> pd.DataFrame:
    return pd.read_csv(result_path)


def _build_class_distribution(source_df: pd.DataFrame, label_column: str | None) -> list[DistributionItem]:
    if not label_column or label_column not in source_df.columns:
        return []
    counts = source_df[label_column].fillna("unknown").astype(str).value_counts(dropna=False)
    total = float(counts.sum() or 1)
    return [
        DistributionItem(value=str(label), count=int(count), ratio=float(count / total))
        for label, count in counts.head(10).items()
    ]


def _build_confidence_stats(result_df: pd.DataFrame) -> ConfidenceStats:
    if "_prediction_confidence" not in result_df:
        return ConfidenceStats()
    values = pd.to_numeric(result_df["_prediction_confidence"], errors="coerce").dropna()
    if values.empty:
        return ConfidenceStats()
    return ConfidenceStats(
        mean=float(values.mean()),
        minimum=float(values.min()),
        p10=float(values.quantile(0.1)),
        p50=float(values.quantile(0.5)),
        p90=float(values.quantile(0.9)),
        maximum=float(values.max()),
    )


def _build_feature_importance_top(metadata: dict[str, Any]) -> list[ScoreItem]:
    feature_importance = metadata.get("feature_importance") or {}
    if not isinstance(feature_importance, dict):
        return []
    items = sorted(feature_importance.items(), key=lambda item: item[1], reverse=True)
    return [ScoreItem(feature=str(feature), score=float(score)) for feature, score in items[:10]]


def _build_cluster_summary(result_df: pd.DataFrame) -> list[ClusterSummary]:
    if "_cluster_id" not in result_df:
        return []
    summaries: list[ClusterSummary] = []
    grouped = result_df.groupby("_cluster_id", dropna=False)
    for cluster_id, group in grouped:
        if pd.isna(cluster_id):
            continue
        cluster_id_str = str(cluster_id)
        if cluster_id_str == "noise":
            continue
        summaries.append(
            ClusterSummary(
                cluster_id=cluster_id_str,
                size=int(len(group)),
                is_island=bool(group["_is_island"].any()) if "_is_island" in group else False,
                review_priority=int(group["_review_priority"].max()) if "_review_priority" in group else 0,
                nearest_major_class=str(group["_nearest_major_class"].mode(dropna=True).iloc[0])
                if "_nearest_major_class" in group and not group["_nearest_major_class"].dropna().empty
                else None,
            )
        )
    summaries.sort(key=lambda item: (not item.is_island, item.size, -item.review_priority))
    return summaries[:10]


def _build_representative_rows(
    result_df: pd.DataFrame,
    feature_columns: list[str],
    label_column: str | None,
) -> list[RepresentativeRow]:
    if result_df.empty:
        return []
    sort_columns = [col for col in ["_review_priority", "_prediction_confidence"] if col in result_df.columns]
    if sort_columns:
        ascending = [False if column == "_review_priority" else True for column in sort_columns]
        ordered = result_df.sort_values(by=sort_columns, ascending=ascending)
    else:
        ordered = result_df
    rows: list[RepresentativeRow] = []
    for _, row in ordered.head(5).iterrows():
        values: dict[str, Any] = {}
        for column in ["_row_id", label_column, "_predicted_class", "_prediction_confidence", "_cluster_id", "_review_priority"]:
            if column and column in row and not pd.isna(row[column]):
                values[str(column)] = _to_jsonable(row[column])
        for column in feature_columns[:4]:
            if column in row and not pd.isna(row[column]):
                values[str(column)] = _to_jsonable(row[column])
        row_id = int(row["_row_id"]) if "_row_id" in row and not pd.isna(row["_row_id"]) else int(len(rows) + 1)
        rows.append(RepresentativeRow(row_id=row_id, values=values))
    return rows


def _build_quality_flags(
    *,
    source_df: pd.DataFrame,
    result_df: pd.DataFrame,
    feature_columns: list[str],
    label_column: str | None,
    confidence_stats: ConfidenceStats,
    class_distribution: list[DistributionItem],
    metadata: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    if not feature_columns:
        flags.append("no_features_selected")
    if not label_column:
        flags.append("unsupervised")
    if feature_columns and source_df[feature_columns].isna().mean().mean() >= 0.15:
        flags.append("high_missing_rate")
    if "_is_outlier" in result_df and float(result_df["_is_outlier"].mean()) >= 0.05:
        flags.append("many_outliers")
    if "_is_island" in result_df and float(result_df["_is_island"].mean()) >= 0.03:
        flags.append("many_islands")
    if confidence_stats.mean and confidence_stats.mean < 0.65:
        flags.append("low_prediction_confidence")
    if class_distribution:
        counts = [item.count for item in class_distribution if item.count > 0]
        if counts and max(counts) / max(1, min(counts)) >= 5:
            flags.append("class_imbalance")
    if metadata.get("dropped_features"):
        flags.append("features_dropped")
    return flags


def _find_proposal(job_state: dict[str, Any], proposal_id: str) -> ReviewAction | None:
    for candidate in job_state.get("proposals", []):
        proposal = ReviewAction.model_validate(candidate)
        if proposal.proposal_id == proposal_id:
            return proposal
    review_result = job_state.get("review_result")
    if review_result:
        result = ReviewResult.model_validate(review_result)
        for proposal in result.recommended_actions:
            if proposal.proposal_id == proposal_id:
                return proposal
    return None


def _apply_single_proposal(
    *,
    current_request: JobRequest,
    source_df: pd.DataFrame,
    current_result_df: pd.DataFrame,
    proposal: ReviewAction,
) -> tuple[JobRequest, pd.DataFrame]:
    next_request = current_request.model_copy(deep=True)
    filtered_source_df = source_df.copy()

    if proposal.action == ReviewActionType.DROP_FEATURES:
        drop_features = _normalize_target_list(proposal.target)
        next_request.mapping.feature_columns = [
            column for column in next_request.mapping.feature_columns if column not in drop_features
        ]
    elif proposal.action == ReviewActionType.CHANGE_MISSING:
        method = str((proposal.params or {}).get("handle_missing") or proposal.target or "median")
        next_request.preprocessing.handle_missing = method
    elif proposal.action == ReviewActionType.CHANGE_NORMALIZATION:
        method = str((proposal.params or {}).get("normalization") or proposal.target or "minmax")
        next_request.preprocessing.normalization = method
    elif proposal.action == ReviewActionType.ADJUST_THRESHOLD:
        threshold = (proposal.params or {}).get("feature_selection_threshold", proposal.target)
        try:
            next_request.preprocessing.feature_selection_threshold = float(threshold)
        except (TypeError, ValueError):
            pass
    elif proposal.action == ReviewActionType.SWITCH_ALGORITHM:
        algorithm = str((proposal.params or {}).get("algorithm") or proposal.target or next_request.algorithm)
        try:
            next_request.algorithm = AlgorithmType(algorithm)
        except ValueError:
            next_request.algorithm = next_request.algorithm
    elif proposal.action == ReviewActionType.REVIEW_MANUALLY:
        pass

    return next_request, filtered_source_df


def _rows_for_scope(current_result_df: pd.DataFrame, proposal: ReviewAction) -> set[int]:
    target = proposal.target
    row_ids: set[int] = set()
    if proposal.action == ReviewActionType.REMOVE_OUTLIERS and "_is_outlier" in current_result_df:
        row_ids.update(
            int(row_id)
            for row_id in current_result_df.loc[current_result_df["_is_outlier"], "_row_id"].dropna().tolist()
        )
    elif proposal.action == ReviewActionType.EXCLUDE_ISLANDS and "_is_island" in current_result_df:
        if isinstance(target, list) and target:
            cluster_ids = {str(item) for item in target}
            mask = current_result_df["_cluster_id"].astype(str).isin(cluster_ids)
        else:
            mask = current_result_df["_is_island"].astype(bool)
        row_ids.update(
            int(row_id)
            for row_id in current_result_df.loc[mask, "_row_id"].dropna().tolist()
        )
    elif proposal.action == ReviewActionType.EXCLUDE_ISLANDS and isinstance(target, str) and target:
        mask = current_result_df["_cluster_id"].astype(str) == target
        row_ids.update(
            int(row_id)
            for row_id in current_result_df.loc[mask, "_row_id"].dropna().tolist()
        )
    return row_ids


def _drop_rows_by_source_row_id(source_df: pd.DataFrame, row_ids: set[int]) -> pd.DataFrame:
    if not row_ids:
        return source_df.copy()
    source = source_df.copy().reset_index(drop=True)
    source["_row_id"] = np.arange(1, len(source) + 1)
    filtered = source.loc[~source["_row_id"].isin(row_ids)].copy()
    filtered = filtered.drop(columns=["_row_id"], errors="ignore")
    return filtered.reset_index(drop=True)


def _normalize_target_list(target: Any) -> list[str]:
    if target is None:
        return []
    if isinstance(target, list):
        return [str(item) for item in target]
    return [str(target)]


def _normalize_for_key(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize_for_key(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return _normalize_for_key(value.tolist())
    if isinstance(value, dict):
        return {
            str(key): _normalize_for_key(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple, set)):
        normalized_items = [_normalize_for_key(item) for item in value]
        if all(not isinstance(item, (dict, list)) for item in normalized_items):
            try:
                return sorted(
                    normalized_items,
                    key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, default=str),
                )
            except TypeError:
                return sorted((str(item) for item in normalized_items))
        return normalized_items
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _to_jsonable(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, np.floating) and not np.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [_to_jsonable(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return str(value)
