from __future__ import annotations

from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from app.models.schemas import (
    ColumnMapping,
    DataProfile,
    DataProfileColumn,
    ExplorationDecision,
    ExplorationEvaluation,
    ExplorationNextAction,
    ExplorationRequest,
    ModelSweepItem,
    ModelSweepResult,
    ModelWorkflowRequest,
    TargetFeasibility,
    UseCaseType,
)
from app.services.ml.model_workflows import run_model_workflow


def run_exploration(df: pd.DataFrame, request: ExplorationRequest) -> tuple[DataProfile, TargetFeasibility, ModelSweepResult, ExplorationEvaluation]:
    profile = build_data_profile(df)
    mapping = _normalize_mapping(df, request.mapping)
    target = build_target_feasibility(df, mapping.label_column, request.task_type)
    model_sweep = build_model_sweep(df, mapping, request, target)
    evaluation = build_exploration_evaluation(profile, target, model_sweep, mapping)
    return profile, target, model_sweep, evaluation


def build_data_profile(df: pd.DataFrame) -> DataProfile:
    row_count = int(len(df))
    column_count = int(len(df.columns))
    missing_rate_overall = float(df.isna().mean().mean()) if row_count and column_count else 0.0
    columns: list[DataProfileColumn] = []

    for name in df.columns:
        series = df[name]
        missing_rate = float(series.isna().mean()) if row_count else 0.0
        unique_non_null = int(series.nunique(dropna=True))
        unique_ratio = float(unique_non_null / max(1, row_count))
        likely_identifier = unique_ratio > 0.9 and unique_non_null >= 20
        low_variance = unique_non_null <= 1
        warning_flags: list[str] = []
        if missing_rate >= 0.4:
            warning_flags.append("high_missing_rate")
        if low_variance:
            warning_flags.append("low_variance")
        if likely_identifier:
            warning_flags.append("likely_identifier")
        columns.append(
            DataProfileColumn(
                name=str(name),
                inferred_type=str(series.dtype),
                missing_rate=missing_rate,
                unique_ratio=unique_ratio,
                low_variance=low_variance,
                likely_identifier=likely_identifier,
                warning_flags=warning_flags,
            )
        )
    return DataProfile(
        row_count=row_count,
        column_count=column_count,
        missing_rate_overall=missing_rate_overall,
        columns=columns,
    )


def build_target_feasibility(df: pd.DataFrame, label_column: str | None, task_type: str) -> TargetFeasibility:
    if not label_column or label_column not in df.columns:
        return TargetFeasibility(
            target_column=label_column,
            target_kind="unknown",
            feasibility="no_target",
            warnings=["label_column_missing"],
        )

    series = df[label_column]
    if task_type in {"classification", "regression"}:
        target_kind = task_type
    else:
        numeric_ratio = float(pd.to_numeric(series, errors="coerce").notna().mean()) if len(series) else 0.0
        target_kind = "regression" if numeric_ratio >= 0.95 else "classification"

    if target_kind == "classification":
        return _classification_feasibility(series, label_column)
    return _regression_feasibility(series, label_column)


def build_model_sweep(
    df: pd.DataFrame,
    mapping: ColumnMapping,
    request: ExplorationRequest,
    target: TargetFeasibility,
) -> ModelSweepResult:
    if target.target_kind not in {"classification", "regression"}:
        return ModelSweepResult(task_type=target.target_kind, items=[])

    if not mapping.label_column or mapping.label_column not in df.columns:
        return ModelSweepResult(
            task_type=target.target_kind,
            items=[ModelSweepItem(algorithm="none", status="failed", failure_reason="label_column_missing")],
        )

    algorithms = (
        ["logistic_regression", "random_forest", "gradient_boosting", "svm"]
        if target.target_kind == "classification"
        else ["linear_regression", "random_forest", "gradient_boosting", "svm"]
    )
    use_case = UseCaseType.CLASSIFICATION if target.target_kind == "classification" else UseCaseType.PREDICTION
    items: list[ModelSweepItem] = []

    for algorithm in algorithms:
        workflow_request = ModelWorkflowRequest(
            workbook_id=request.workbook_id,
            sheet_name=request.sheet_name,
            source_job_id="exploration",
            use_case=use_case,
            mapping=mapping,
            algorithm=algorithm,
            params={
                "task_type": target.target_kind,
                "split_mode": request.split_mode,
                "test_size": request.test_size,
                "train_size": request.train_size,
                "random_state": request.random_state,
                "shuffle": request.shuffle,
            },
            preprocessing=request.preprocessing,
        )
        try:
            result = run_model_workflow(df, workflow_request, str(uuid4()))
            item = _build_sweep_item(target.target_kind, algorithm, result.metrics)
            items.append(item)
        except Exception as exc:
            items.append(
                ModelSweepItem(
                    algorithm=algorithm,
                    status="failed",
                    failure_reason=str(exc),
                )
            )

    successful = [item for item in items if item.status == "success" and item.primary_metric is not None]
    best_algorithm: str | None = None
    if successful:
        reverse = target.target_kind == "classification"
        successful_sorted = sorted(successful, key=lambda x: float(x.primary_metric or 0.0), reverse=reverse)
        best_algorithm = successful_sorted[0].algorithm
    return ModelSweepResult(task_type=target.target_kind, items=items, best_algorithm=best_algorithm)


def build_exploration_evaluation(
    profile: DataProfile,
    target: TargetFeasibility,
    model_sweep: ModelSweepResult,
    mapping: ColumnMapping,
) -> ExplorationEvaluation:
    risk_flags: list[str] = list(target.warnings)
    reasons: list[str] = []
    feature_columns = set(mapping.feature_columns)
    risky_feature_flags: set[str] = set()
    warning_columns: dict[str, list[str]] = {}
    for column in profile.columns:
        if column.name in feature_columns:
            risky_feature_flags.update(column.warning_flags)
            for warning in column.warning_flags:
                warning_columns.setdefault(warning, []).append(column.name)
    if "likely_identifier" in risky_feature_flags:
        risk_flags.append("likely_identifier_features")
    if "high_missing_rate" in risky_feature_flags:
        risk_flags.append("high_missing_rate_features")
    if "low_variance" in risky_feature_flags:
        risk_flags.append("low_variance_features")
    if profile.row_count < 20:
        risk_flags.append("not_enough_rows")

    successful = [item for item in model_sweep.items if item.status == "success" and item.primary_metric is not None]
    if target.target_kind not in {"classification", "regression"}:
        reasons.append("Label column is missing or target kind is not inferable.")
        next_actions = _build_next_actions(target.target_kind, risk_flags, "unknown", "unknown", warning_columns)
        return ExplorationEvaluation(
            signal_strength="unknown",
            model_viability="unknown",
            overall_verdict="needs_better_target" if "label_column_missing" in risk_flags else "not_enough_data",
            confidence=0.2,
            reasons=reasons,
            risk_flags=_dedupe(risk_flags),
            decision=_build_decision("needs_better_target" if "label_column_missing" in risk_flags else "not_enough_data", risk_flags),
            next_actions=next_actions,
        )

    if not successful:
        risk_flags.append("all_models_failed")
        reasons.append("All candidate models failed to train or evaluate for this target.")
        next_actions = _build_next_actions(target.target_kind, risk_flags, "none", "not_useful", warning_columns)
        verdict = "needs_better_target" if _has_target_failure(risk_flags) else "needs_better_features"
        return ExplorationEvaluation(
            signal_strength="none",
            model_viability="not_useful",
            overall_verdict=verdict,
            confidence=0.25,
            reasons=reasons,
            risk_flags=_dedupe(risk_flags),
            decision=_build_decision(verdict, risk_flags),
            next_actions=next_actions,
        )

    if target.target_kind == "classification":
        signal_strength, model_viability, confidence, additional_reasons = _evaluate_classification_signal(target, successful, risk_flags)
    else:
        signal_strength, model_viability, confidence, additional_reasons = _evaluate_regression_signal(target, successful, risk_flags)
    reasons.extend(additional_reasons)

    verdict = _determine_overall_verdict(signal_strength, model_viability, risk_flags)
    next_actions = _build_next_actions(target.target_kind, risk_flags, signal_strength, model_viability, warning_columns)
    return ExplorationEvaluation(
        signal_strength=signal_strength,
        model_viability=model_viability,
        overall_verdict=verdict,
        confidence=_clamp(confidence, 0.0, 1.0),
        reasons=_dedupe(reasons),
        risk_flags=_dedupe(risk_flags),
        decision=_build_decision(verdict, risk_flags),
        next_actions=next_actions,
    )


def _classification_feasibility(series: pd.Series, label_column: str) -> TargetFeasibility:
    non_null = series.dropna().astype(str)
    warnings: list[str] = []
    if non_null.empty:
        warnings.append("empty_target")
        return TargetFeasibility(target_column=label_column, target_kind="classification", feasibility="low", warnings=warnings)

    counts = non_null.value_counts()
    top_ratio = float(counts.iloc[0] / len(non_null))
    minority_count = int(counts.min()) if len(counts) else 0
    unique_count = int(counts.shape[0])
    baseline_accuracy = top_ratio
    feasibility = "high"
    if unique_count <= 1:
        warnings.append("single_class_target")
        feasibility = "low"
    if minority_count < 5:
        warnings.append("minority_class_too_small")
        feasibility = "low" if feasibility != "low" else feasibility
    if top_ratio > 0.9:
        warnings.append("class_imbalance")
        if feasibility == "high":
            feasibility = "medium"
    return TargetFeasibility(
        target_column=label_column,
        target_kind="classification",
        feasibility=feasibility,
        baseline_metrics={"baseline_accuracy": baseline_accuracy},
        warnings=warnings,
    )


def _regression_feasibility(series: pd.Series, label_column: str) -> TargetFeasibility:
    warnings: list[str] = []
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        warnings.append("non_numeric_target")
        return TargetFeasibility(target_column=label_column, target_kind="regression", feasibility="low", warnings=warnings)

    mean_pred = float(valid.mean())
    residual = valid - mean_pred
    baseline_mae = float(np.mean(np.abs(residual)))
    baseline_rmse = float(np.sqrt(np.mean(np.square(residual))))
    feasibility = "high"
    if float(valid.std(ddof=0)) <= 1e-8:
        warnings.append("near_constant_target")
        feasibility = "low"
    if float(valid.isna().mean()) > 0.2:
        warnings.append("high_target_missing_rate")
        if feasibility == "high":
            feasibility = "medium"
    return TargetFeasibility(
        target_column=label_column,
        target_kind="regression",
        feasibility=feasibility,
        baseline_metrics={"baseline_mae": baseline_mae, "baseline_rmse": baseline_rmse},
        warnings=warnings,
    )


def _normalize_mapping(df: pd.DataFrame, mapping: ColumnMapping) -> ColumnMapping:
    available = [str(col) for col in df.columns]
    label = mapping.label_column if mapping.label_column in available else None
    excluded = {col for col in mapping.exclude_columns if col in available}
    if label:
        excluded.add(label)
    if mapping.id_column and mapping.id_column in available:
        excluded.add(mapping.id_column)

    feature_columns = [col for col in mapping.feature_columns if col in available and col not in excluded]
    if not feature_columns:
        feature_columns = [col for col in available if col not in excluded]
    normalized = mapping.model_copy(deep=True)
    normalized.label_column = label
    normalized.feature_columns = feature_columns
    normalized.exclude_columns = sorted(excluded)
    return normalized


def _build_sweep_item(task_type: str, algorithm: str, metrics: dict[str, Any]) -> ModelSweepItem:
    if task_type == "classification":
        test_metric = _to_float(metrics.get("test_f1", metrics.get("f1")))
        train_metric = _to_float(metrics.get("train_f1", metrics.get("f1")))
    else:
        test_metric = _to_float(metrics.get("test_rmse", metrics.get("rmse")))
        train_metric = _to_float(metrics.get("train_rmse", metrics.get("rmse")))
    primary_metric = test_metric
    gap = None
    if train_metric is not None and test_metric is not None:
        gap = abs(train_metric - test_metric)

    warnings: list[str] = []
    if gap is not None and gap >= 0.15 and task_type == "classification":
        warnings.append("overfit_risk")
    if gap is not None and gap >= 0.25 and task_type == "regression":
        warnings.append("overfit_risk")

    return ModelSweepItem(
        algorithm=algorithm,
        status="success",
        primary_metric=primary_metric,
        train_metric=train_metric,
        test_metric=test_metric,
        gap=gap,
        metrics=metrics,
        warnings=warnings,
    )


def _evaluate_classification_signal(
    target: TargetFeasibility,
    successful: list[ModelSweepItem],
    risk_flags: list[str],
) -> tuple[str, str, float, list[str]]:
    best = max(successful, key=lambda item: float(item.primary_metric or -1.0))
    baseline = _to_float(target.baseline_metrics.get("baseline_accuracy"))
    improvement = _baseline_improvement(target.target_kind, baseline, best.primary_metric)
    reasons: list[str] = [f"Best classification model: {best.algorithm}."]
    signal_strength = "unknown"
    model_viability = "unknown"
    confidence = 0.35

    if improvement is not None:
        reasons.append(f"Best model improves baseline by {improvement:.4f}.")
        confidence += min(0.35, max(0.0, improvement * 1.5))
        if improvement >= 0.15 and (best.gap is None or best.gap <= 0.10):
            signal_strength = "strong"
        elif improvement >= 0.05:
            signal_strength = "medium"
        elif improvement > 0:
            signal_strength = "weak"
        else:
            signal_strength = "none"
    else:
        reasons.append("Baseline improvement could not be computed.")

    improving_models = 0
    if baseline is not None:
        improving_models = sum(1 for item in successful if item.primary_metric is not None and float(item.primary_metric) > baseline)
    if signal_strength == "strong" and improving_models >= 2:
        model_viability = "strong"
    elif signal_strength in {"strong", "medium", "weak"}:
        model_viability = "promising"
    elif signal_strength == "none":
        model_viability = "not_useful"
        risk_flags.append("no_model_beats_baseline")
    else:
        model_viability = "unclear"

    if best.gap is not None and best.gap >= 0.15:
        risk_flags.append("overfit_risk")
        reasons.append(f"Train/test gap is large ({best.gap:.4f}).")
        if model_viability == "strong":
            model_viability = "promising"
        elif model_viability == "promising":
            model_viability = "unclear"
        confidence -= 0.15

    if "class_imbalance" in risk_flags:
        reasons.append("Class imbalance may limit stability on minority classes.")
        confidence -= 0.08

    return signal_strength, model_viability, confidence, reasons


def _evaluate_regression_signal(
    target: TargetFeasibility,
    successful: list[ModelSweepItem],
    risk_flags: list[str],
) -> tuple[str, str, float, list[str]]:
    best = min(successful, key=lambda item: float(item.primary_metric or float("inf")))
    baseline_rmse = _to_float(target.baseline_metrics.get("baseline_rmse"))
    improvement = _baseline_improvement(target.target_kind, baseline_rmse, best.primary_metric)
    reasons: list[str] = [f"Best regression model: {best.algorithm}."]
    signal_strength = "unknown"
    model_viability = "unknown"
    confidence = 0.35
    gain_ratio = 0.0

    if baseline_rmse is not None and baseline_rmse > 0 and improvement is not None:
        gain_ratio = improvement / baseline_rmse
        reasons.append(f"Best model reduces baseline RMSE by {gain_ratio * 100:.1f}%.")
        confidence += min(0.35, max(0.0, gain_ratio))
        if gain_ratio >= 0.20 and _extract_test_r2(best) is not None and _extract_test_r2(best) > 0.40:
            signal_strength = "strong"
        elif gain_ratio >= 0.08:
            signal_strength = "medium"
        elif gain_ratio > 0:
            signal_strength = "weak"
        else:
            signal_strength = "none"
    else:
        reasons.append("Baseline RMSE improvement could not be computed.")

    improving_models = 0
    if baseline_rmse is not None:
        improving_models = sum(
            1 for item in successful if item.primary_metric is not None and float(item.primary_metric) < baseline_rmse
        )
    if signal_strength == "strong" and improving_models >= 2:
        model_viability = "strong"
    elif signal_strength in {"strong", "medium", "weak"}:
        model_viability = "promising"
    elif signal_strength == "none":
        model_viability = "not_useful"
        risk_flags.append("no_model_beats_baseline")
    else:
        model_viability = "unclear"

    if best.gap is not None and best.gap >= 0.25:
        risk_flags.append("overfit_risk")
        reasons.append(f"Train/test gap is large ({best.gap:.4f}).")
        if model_viability == "strong":
            model_viability = "promising"
        elif model_viability == "promising":
            model_viability = "unclear"
        confidence -= 0.12

    return signal_strength, model_viability, confidence, reasons


def _baseline_improvement(task_type: str, baseline: float | None, model_value: float | None) -> float | None:
    if baseline is None or model_value is None:
        return None
    if task_type == "classification":
        return float(model_value) - float(baseline)
    return float(baseline) - float(model_value)


def _determine_overall_verdict(signal_strength: str, model_viability: str, risk_flags: list[str]) -> str:
    if "not_enough_rows" in risk_flags:
        return "not_enough_data"
    if _has_target_failure(risk_flags):
        return "needs_better_target"
    if signal_strength in {"strong", "medium"} and model_viability in {"strong", "promising"}:
        if "overfit_risk" in risk_flags:
            return "try_more"
        return "usable_signal"
    if signal_strength == "weak" or model_viability == "unclear":
        return "try_more"
    if signal_strength == "none" or model_viability == "not_useful":
        return "needs_better_features"
    return "try_more"


def _build_next_actions(
    target_kind: str,
    risk_flags: list[str],
    signal_strength: str,
    model_viability: str,
    warning_columns: dict[str, list[str]],
) -> list[ExplorationNextAction]:
    actions: list[ExplorationNextAction] = []

    def add(action: str, reason: str, priority: str) -> None:
        if any(item.action == action for item in actions):
            return
        actions.append(
            ExplorationNextAction(
                action=action,
                reason=reason,
                priority=priority,
                affected_columns=_affected_columns_for_action(risk_flags, action, warning_columns),
            )
        )

    if any(flag in risk_flags for flag in {"label_column_missing", "single_class_target", "non_numeric_target", "near_constant_target"}):
        add("change_target", "Current target configuration is not suitable for model learning.", "high")
    if any(flag in risk_flags for flag in {"not_enough_rows", "minority_class_too_small"}):
        add("collect_more_rows", "Sample size is too small for stable evaluation.", "high")
    if "class_imbalance" in risk_flags and target_kind == "classification":
        add("try_balanced_class_weight", "Class imbalance is likely reducing minority-class performance.", "high")
    if any(flag in risk_flags for flag in {"likely_identifier_features", "high_missing_rate_features", "low_variance_features"}):
        add("exclude_risky_columns", "Some selected features look unstable or non-informative.", "medium")
    if "overfit_risk" in risk_flags:
        add("try_regularized_model", "Train/test gap indicates overfitting risk.", "medium")
    if any(flag in risk_flags for flag in {"all_models_failed", "no_model_beats_baseline"}) or model_viability == "not_useful":
        add("inspect_features", "Current feature set does not beat baseline reliably.", "high")
    if signal_strength in {"strong", "medium"} and model_viability in {"promising", "strong"}:
        add("inspect_clusters", "Segment-level behavior can reveal where the model is strongest.", "low")
    if signal_strength in {"weak", "none"}:
        add("inspect_outliers", "Outliers may be hiding useful signal.", "low")

    return actions


def _has_target_failure(risk_flags: list[str]) -> bool:
    return any(flag in risk_flags for flag in {"label_column_missing", "single_class_target", "non_numeric_target", "near_constant_target"})


def _build_decision(verdict: str, risk_flags: list[str]) -> ExplorationDecision:
    if verdict == "usable_signal":
        return ExplorationDecision(
            primary_message="Signal looks usable. Proceed to workflow validation.",
            recommended_path="run_workflow",
            primary_blocker=None,
        )
    if verdict == "needs_better_target":
        return ExplorationDecision(
            primary_message="Current target configuration is not suitable for reliable learning.",
            recommended_path="change_target",
            primary_blocker="target_configuration",
        )
    if verdict == "not_enough_data":
        return ExplorationDecision(
            primary_message="Data volume is too small for stable model evaluation.",
            recommended_path="collect_more_data",
            primary_blocker="row_count",
        )
    if "overfit_risk" in risk_flags:
        return ExplorationDecision(
            primary_message="Potential overfitting detected. Improve data quality before workflow.",
            recommended_path="inspect_data_quality",
            primary_blocker="train_test_gap",
        )
    if "no_model_beats_baseline" in risk_flags:
        return ExplorationDecision(
            primary_message="Current feature set does not outperform baseline reliably.",
            recommended_path="use_baseline",
            primary_blocker="baseline_gap",
        )
    return ExplorationDecision(
        primary_message="Feature signal needs improvement before workflow execution.",
        recommended_path="adjust_features",
        primary_blocker="feature_quality",
    )


def _affected_columns_for_action(
    risk_flags: list[str],
    action: str,
    warning_columns: dict[str, list[str]],
) -> list[str]:
    if action != "exclude_risky_columns":
        return []
    risk_to_warning: dict[str, str] = {
        "likely_identifier_features": "likely_identifier",
        "high_missing_rate_features": "high_missing_rate",
        "low_variance_features": "low_variance",
    }
    columns: list[str] = []
    for risk_flag in risk_flags:
        warning = risk_to_warning.get(risk_flag)
        if warning:
            columns.extend(warning_columns.get(warning, []))
    return _dedupe(columns)


def _extract_test_r2(item: ModelSweepItem) -> float | None:
    if not isinstance(item.metrics, dict):
        return None
    return _to_float(item.metrics.get("test_r2", item.metrics.get("r2")))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
