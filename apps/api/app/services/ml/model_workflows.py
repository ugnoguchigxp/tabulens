from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    silhouette_score,
)
from sklearn.model_selection import train_test_split
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.svm import OneClassSVM

from app.models.schemas import ColumnMapping, ModelWorkflowRequest, UseCaseType
from app.services.ml.model_factory import build_model


@dataclass
class WorkflowResult:
    result_df: pd.DataFrame
    metrics: dict[str, Any]
    metadata: dict[str, Any]
    model_artifacts: dict[str, Any] | None = None


def run_model_workflow(df: pd.DataFrame, request: ModelWorkflowRequest, workflow_id: str) -> WorkflowResult:
    use_case = request.use_case
    if use_case in {UseCaseType.CLASSIFICATION, UseCaseType.PREDICTION}:
        return _run_prediction_workflow(df, request, workflow_id)
    if use_case == UseCaseType.ANOMALY_DETECTION:
        return _run_anomaly_workflow(df, request, workflow_id)
    if use_case == UseCaseType.RECOMMENDATION:
        return _run_recommendation_workflow(df, request, workflow_id)
    if use_case == UseCaseType.CLUSTERING:
        return _run_clustering_workflow(df, request, workflow_id)
    if use_case == UseCaseType.NOISE_REDUCTION:
        return _run_noise_reduction_workflow(df, request, workflow_id)
    raise ValueError(f"Unsupported use_case: {use_case}")


def _run_prediction_workflow(df: pd.DataFrame, request: ModelWorkflowRequest, workflow_id: str) -> WorkflowResult:
    mapping = request.mapping
    label_column = mapping.label_column
    feature_cols = _resolve_feature_columns(mapping, df, require_label=True)
    if not label_column or label_column not in df.columns:
        raise ValueError("Prediction requires a valid label_column")
    if len(feature_cols) == 0:
        raise ValueError("Prediction requires at least one feature column")

    task_type = "classification" if request.use_case == UseCaseType.CLASSIFICATION else str(request.params.get("task_type", "regression")).lower()
    test_size = request.params.get("test_size", 0.2)
    train_size = request.params.get("train_size")
    split_mode = str(request.params.get("split_mode", "ratio")).lower()
    random_state = int(request.params.get("random_state", 42))
    shuffle = bool(request.params.get("shuffle", True))

    working_df = df.copy().reset_index(drop=True)
    working_df["_row_id"] = np.arange(1, len(working_df) + 1)
    working_df, feature_cols = _apply_row_filters(working_df, feature_cols, label_column, request.preprocessing)
    _ensure_min_rows(working_df, 2, "Prediction")

    X = working_df[feature_cols].copy()
    y = working_df[label_column].copy()
    if task_type == "regression":
        numeric_y = pd.to_numeric(y, errors="coerce")
        if numeric_y.isna().any():
            raise ValueError("Regression requires a numeric label_column without missing values")
        y = numeric_y

    stratify = y if task_type == "classification" and y.nunique(dropna=True) > 1 else None
    split_kwargs: dict[str, Any] = {
        "random_state": random_state,
        "shuffle": shuffle,
    }
    if split_mode == "count":
        total_rows = len(X)
        train_count = int(train_size) if train_size is not None else None
        test_count = int(test_size) if test_size is not None else None
        if train_count is None and test_count is None:
            raise ValueError("Count split mode requires train_size or test_size")
        if train_count is None and test_count is not None:
            train_count = total_rows - test_count
        if test_count is None and train_count is not None:
            test_count = total_rows - train_count
        if train_count is None or test_count is None:
            raise ValueError("Count split mode requires both train and test counts")
        if train_count <= 0 or test_count <= 0:
            raise ValueError("Train and test counts must be greater than zero")
        if train_count + test_count > total_rows:
            raise ValueError("Train and test counts exceed available rows")
        split_kwargs["train_size"] = train_count
        split_kwargs["test_size"] = test_count
    else:
        split_kwargs["test_size"] = test_size
        if train_size is not None:
            split_kwargs["train_size"] = train_size
    if stratify is not None:
        split_kwargs["stratify"] = stratify

    try:
        X_train, X_test, y_train, y_test, train_idx, test_idx = _split_with_indices(
            X,
            y,
            **split_kwargs,
        )
    except ValueError:
        split_kwargs.pop("stratify", None)
        X_train, X_test, y_train, y_test, train_idx, test_idx = _split_with_indices(
            X,
            y,
            **split_kwargs,
        )

    preprocessor = _build_preprocessor(X_train, request.preprocessing)
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)
    X_all_proc = preprocessor.transform(X)

    model = build_model(
        request.algorithm,
        y_train,
        force_classification=task_type == "classification",
        params=dict(request.params),
    )
    model.fit(X_train_proc, y_train)

    all_predictions = model.predict(X_all_proc)
    result_df = working_df.copy()
    result_df["_split_role"] = "unused"
    result_df.loc[train_idx, "_split_role"] = "train"
    result_df.loc[test_idx, "_split_role"] = "test"
    unused_count = int((result_df["_split_role"] == "unused").sum())

    metadata: dict[str, Any] = {
        "workflow_id": workflow_id,
        "use_case": request.use_case.value,
        "task_type": task_type,
        "algorithm": request.algorithm,
        "feature_columns": feature_cols,
        "label_column": label_column,
        "train_count": int(len(train_idx)),
        "test_count": int(len(test_idx)),
        "unused_count": unused_count,
        "row_count": int(len(result_df)),
    }

    if task_type == "classification":
        train_predictions = pd.Series(model.predict(X_train_proc), index=y_train.index)
        result_df["_predicted_class"] = all_predictions
        if hasattr(model, "predict_proba"):
            all_confidence = np.max(model.predict_proba(X_all_proc), axis=1)
            result_df["_prediction_confidence"] = all_confidence
            test_confidence = np.max(model.predict_proba(X_test_proc), axis=1)
            train_confidence = np.max(model.predict_proba(X_train_proc), axis=1)
        else:
            result_df["_prediction_confidence"] = 1.0
            test_confidence = np.ones(len(X_test))
            train_confidence = np.ones(len(X_train))
        result_df["_is_correct"] = result_df[label_column].astype(str) == result_df["_predicted_class"].astype(str)
        result_df["_error_flag"] = False
        result_df.loc[test_idx, "_error_flag"] = ~result_df.loc[test_idx, "_is_correct"]

        y_test_pred = pd.Series(model.predict(X_test_proc), index=y_test.index)
        y_train_pred = train_predictions
        metrics = {
            "accuracy": float(accuracy_score(y_test.astype(str), y_test_pred.astype(str))),
            "balanced_accuracy": float(balanced_accuracy_score(y_test.astype(str), y_test_pred.astype(str))),
            "precision": float(precision_score(y_test.astype(str), y_test_pred.astype(str), average="weighted", zero_division=0)),
            "recall": float(recall_score(y_test.astype(str), y_test_pred.astype(str), average="weighted", zero_division=0)),
            "f1": float(f1_score(y_test.astype(str), y_test_pred.astype(str), average="weighted", zero_division=0)),
            "confidence_mean": float(np.mean(test_confidence)) if len(test_confidence) else 0.0,
            "train_accuracy": float(accuracy_score(y_train.astype(str), y_train_pred.astype(str))),
            "train_balanced_accuracy": float(balanced_accuracy_score(y_train.astype(str), y_train_pred.astype(str))),
            "train_precision": float(precision_score(y_train.astype(str), y_train_pred.astype(str), average="weighted", zero_division=0)),
            "train_recall": float(recall_score(y_train.astype(str), y_train_pred.astype(str), average="weighted", zero_division=0)),
            "train_f1": float(f1_score(y_train.astype(str), y_train_pred.astype(str), average="weighted", zero_division=0)),
            "train_confidence_mean": float(np.mean(train_confidence)) if len(train_confidence) else 0.0,
            "test_accuracy": float(accuracy_score(y_test.astype(str), y_test_pred.astype(str))),
            "test_balanced_accuracy": float(balanced_accuracy_score(y_test.astype(str), y_test_pred.astype(str))),
            "test_precision": float(precision_score(y_test.astype(str), y_test_pred.astype(str), average="weighted", zero_division=0)),
            "test_recall": float(recall_score(y_test.astype(str), y_test_pred.astype(str), average="weighted", zero_division=0)),
            "test_f1": float(f1_score(y_test.astype(str), y_test_pred.astype(str), average="weighted", zero_division=0)),
            "confusion_matrix": _build_confusion_matrix(y_test.astype(str), y_test_pred.astype(str)),
            "train_count": int(len(train_idx)),
            "test_count": int(len(test_idx)),
            "unused_count": unused_count,
        }
    else:
        all_predictions = pd.to_numeric(all_predictions, errors="coerce")
        result_df["_predicted_value"] = all_predictions
        actual = pd.to_numeric(result_df[label_column], errors="coerce")
        result_df["_actual_value"] = actual
        result_df["_residual"] = result_df["_actual_value"] - result_df["_predicted_value"]
        result_df["_absolute_error"] = result_df["_residual"].abs()
        result_df["_prediction_confidence"] = 1.0
        threshold = float(np.nanpercentile(result_df.loc[test_idx, "_absolute_error"], 90)) if len(test_idx) else 0.0
        result_df["_error_flag"] = False
        result_df.loc[test_idx, "_error_flag"] = result_df.loc[test_idx, "_absolute_error"] >= threshold if len(test_idx) else False

        y_test_pred = pd.Series(model.predict(X_test_proc), index=y_test.index)
        y_test_actual = pd.to_numeric(y_test, errors="coerce")
        y_train_pred = pd.Series(model.predict(X_train_proc), index=y_train.index)
        y_train_actual = pd.to_numeric(y_train, errors="coerce")
        metrics = {
            "mae": float(mean_absolute_error(y_test_actual, y_test_pred)),
            "rmse": float(np.sqrt(np.mean((y_test_actual - y_test_pred) ** 2))),
            "r2": float(r2_score(y_test_actual, y_test_pred)),
            "train_mae": float(mean_absolute_error(y_train_actual, y_train_pred)),
            "train_rmse": float(np.sqrt(np.mean((y_train_actual - y_train_pred) ** 2))),
            "train_r2": float(r2_score(y_train_actual, y_train_pred)),
            "test_mae": float(mean_absolute_error(y_test_actual, y_test_pred)),
            "test_rmse": float(np.sqrt(np.mean((y_test_actual - y_test_pred) ** 2))),
            "test_r2": float(r2_score(y_test_actual, y_test_pred)),
            "residual_mean": float(np.nanmean(result_df.loc[test_idx, "_residual"])) if len(test_idx) else 0.0,
            "residual_std": float(np.nanstd(result_df.loc[test_idx, "_residual"])) if len(test_idx) else 0.0,
            "train_count": int(len(train_idx)),
            "test_count": int(len(test_idx)),
            "unused_count": unused_count,
        }

    metadata["metrics"] = metrics
    metadata["model_artifact_available"] = True
    model_artifacts = {
        "model": model,
        "preprocessor": preprocessor,
        "feature_columns": feature_cols,
        "label_column": label_column,
        "task_type": task_type,
        "algorithm": request.algorithm,
        "params": dict(request.params),
        "preprocessing": request.preprocessing.model_dump(mode="json")
        if hasattr(request.preprocessing, "model_dump")
        else dict(request.preprocessing),
    }
    return WorkflowResult(result_df=result_df, metrics=metrics, metadata=metadata, model_artifacts=model_artifacts)


def _run_anomaly_workflow(df: pd.DataFrame, request: ModelWorkflowRequest, workflow_id: str) -> WorkflowResult:
    feature_cols = _resolve_feature_columns(request.mapping, df, require_label=False)
    if len(feature_cols) == 0:
        raise ValueError("Anomaly detection requires at least one feature column")

    working_df = df.copy().reset_index(drop=True)
    working_df["_row_id"] = np.arange(1, len(working_df) + 1)
    working_df, feature_cols = _apply_row_filters(working_df, feature_cols, "", request.preprocessing)
    _ensure_min_rows(working_df, 2, "Anomaly detection")
    X = working_df[feature_cols].copy()
    preprocessor = _build_preprocessor(X, request.preprocessing)
    X_proc = preprocessor.fit_transform(X)

    contamination = float(request.params.get("contamination", 0.1))
    algorithm = str(request.algorithm or request.params.get("algorithm", "isolation_forest")).lower()

    if algorithm == "one_class_svm":
        model = OneClassSVM(nu=max(0.01, min(0.5, contamination)), gamma="scale")
        labels = model.fit_predict(X_proc)
        score = -model.decision_function(X_proc)
    elif algorithm == "local_outlier_factor":
        n_neighbors = int(request.params.get("n_neighbors", min(20, max(2, len(X_proc) // 2))))
        n_neighbors = max(1, min(n_neighbors, max(1, len(X_proc) - 1)))
        model = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination)
        labels = model.fit_predict(X_proc)
        score = -model.negative_outlier_factor_
    else:
        model = IsolationForest(random_state=42, contamination=contamination)
        labels = model.fit_predict(X_proc)
        score = -model.decision_function(X_proc)

    threshold = float(np.nanpercentile(score, 100 * (1 - contamination))) if len(score) else 0.0
    result_df = working_df.copy()
    result_df["_anomaly_score"] = score
    result_df["_is_anomaly"] = labels == -1
    result_df["_anomaly_rank"] = pd.Series(score).rank(ascending=False, method="first").astype(int)
    result_df["_anomaly_reason"] = np.where(result_df["_is_anomaly"], "score_above_threshold", "within_normal_range")

    metrics = {
        "anomaly_count": int(result_df["_is_anomaly"].sum()),
        "anomaly_rate": float(result_df["_is_anomaly"].mean()) if len(result_df) else 0.0,
        "score_mean": float(np.nanmean(score)) if len(score) else 0.0,
        "score_p90": float(np.nanpercentile(score, 90)) if len(score) else 0.0,
        "threshold": threshold,
        "algorithm": algorithm,
    }
    if request.mapping.label_column and request.mapping.label_column in result_df.columns:
        y_true = _coerce_binary_labels(result_df[request.mapping.label_column])
        if y_true is not None and len(set(y_true)) > 1:
            y_pred = (result_df["_is_anomaly"]).astype(int)
            metrics.update(
                {
                    "precision": float(precision_score(y_true, y_pred, zero_division=0)),
                    "recall": float(recall_score(y_true, y_pred, zero_division=0)),
                    "f1": float(f1_score(y_true, y_pred, zero_division=0)),
                }
            )

    metadata = {
        "workflow_id": workflow_id,
        "use_case": request.use_case.value,
        "feature_columns": feature_cols,
        "row_count": int(len(result_df)),
        "metrics": metrics,
    }
    return WorkflowResult(result_df=result_df, metrics=metrics, metadata=metadata)


def _run_recommendation_workflow(df: pd.DataFrame, request: ModelWorkflowRequest, workflow_id: str) -> WorkflowResult:
    mapping = request.mapping
    user_col = mapping.user_id_column
    item_col = mapping.item_id_column
    rating_col = mapping.rating_column
    if not user_col or user_col not in df.columns:
        raise ValueError("Recommendation requires user_id_column")
    if not item_col or item_col not in df.columns:
        raise ValueError("Recommendation requires item_id_column")

    top_k = int(request.params.get("top_k", 5))
    working_df = df.copy().reset_index(drop=True)
    user_history = working_df.groupby(user_col)[item_col].apply(lambda s: set(s.astype(str))).to_dict()
    item_scores = _build_item_scores(working_df, item_col, rating_col)
    all_items = [str(value) for value in working_df[item_col].astype(str).dropna().unique().tolist()]

    rows: list[dict[str, Any]] = []
    for user_value, seen_items in user_history.items():
        recommended = [
            (item, score)
            for item, score in sorted(item_scores.items(), key=lambda item: item[1], reverse=True)
            if item not in seen_items
        ][:top_k]
        for rank, (item, score) in enumerate(recommended, start=1):
            rows.append(
                {
                    user_col: user_value,
                    "recommended_item_id": item,
                    "_recommendation_score": float(score),
                    "_rank": rank,
                    "_recommendation_reason": "popularity_baseline",
                }
            )

    result_df = pd.DataFrame(rows)
    metrics = {
        "user_count": int(len(user_history)),
        "item_count": int(len(all_items)),
        "recommendation_count": int(len(result_df)),
        "coverage": float(len(result_df["recommended_item_id"].unique()) / max(1, len(all_items))) if len(result_df) else 0.0,
        "top_k": top_k,
    }
    metadata = {
        "workflow_id": workflow_id,
        "use_case": request.use_case.value,
        "user_column": user_col,
        "item_column": item_col,
        "rating_column": rating_col,
        "row_count": int(len(result_df)),
        "metrics": metrics,
    }
    return WorkflowResult(result_df=result_df, metrics=metrics, metadata=metadata)


def _run_clustering_workflow(df: pd.DataFrame, request: ModelWorkflowRequest, workflow_id: str) -> WorkflowResult:
    feature_cols = _resolve_feature_columns(request.mapping, df, require_label=False)
    if len(feature_cols) == 0:
        raise ValueError("Clustering requires at least one feature column")

    working_df = df.copy().reset_index(drop=True)
    working_df["_row_id"] = np.arange(1, len(working_df) + 1)
    working_df, feature_cols = _apply_row_filters(working_df, feature_cols, "", request.preprocessing)
    _ensure_min_rows(working_df, 2, "Clustering")
    X = working_df[feature_cols].copy()
    preprocessor = _build_preprocessor(X, request.preprocessing)
    X_proc = preprocessor.fit_transform(X)

    algorithm = str(request.algorithm or request.params.get("algorithm", "kmeans")).lower()
    if algorithm == "dbscan":
        eps = float(request.params.get("eps", 0.8))
        min_samples = int(request.params.get("min_samples", max(2, min(10, len(X_proc) // 20 or 2))))
        model = DBSCAN(eps=eps, min_samples=min_samples)
        labels = model.fit_predict(X_proc)
        centroids = _cluster_centroids(X_proc, labels)
        distances = _distance_to_centroids(X_proc, labels, centroids)
    else:
        n_clusters = int(request.params.get("cluster_count", max(2, min(8, int(math.sqrt(max(1, len(X_proc))))))))
        n_clusters = max(1, min(n_clusters, len(X_proc)))
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
        labels = model.fit_predict(X_proc)
        distances = np.min(model.transform(X_proc), axis=1)
        centroids = {label: model.cluster_centers_[label] for label in range(model.n_clusters)}

    cluster_series = pd.Series(labels)
    cluster_sizes = cluster_series.value_counts().to_dict()
    small_threshold = max(3, len(cluster_series) // 20)

    result_df = working_df.copy()
    result_df["_cluster_id"] = cluster_series.map(lambda label: f"cluster_{label}" if label != -1 else "noise")
    result_df["_cluster_size"] = cluster_series.map(lambda label: int(cluster_sizes.get(label, 0)))
    result_df["_distance_to_centroid"] = distances
    result_df["_is_noise"] = cluster_series == -1
    result_df["_is_small_cluster"] = cluster_series.map(lambda label: cluster_sizes.get(label, 0) <= small_threshold or label == -1)

    metrics = {
        "cluster_count": int(len([label for label in set(labels) if label != -1])),
        "noise_count": int((cluster_series == -1).sum()),
        "noise_ratio": float((cluster_series == -1).mean()) if len(cluster_series) else 0.0,
        "small_cluster_count": int(sum(1 for label, size in cluster_sizes.items() if size <= small_threshold and label != -1)),
        "algorithm": algorithm,
    }
    if len(set(labels)) > 1 and len(cluster_series) > len(set(labels)):
        try:
            metrics["silhouette_score"] = float(silhouette_score(X_proc, labels))
        except Exception:
            metrics["silhouette_score"] = None

    metadata = {
        "workflow_id": workflow_id,
        "use_case": request.use_case.value,
        "feature_columns": feature_cols,
        "row_count": int(len(result_df)),
        "metrics": metrics,
    }
    return WorkflowResult(result_df=result_df, metrics=metrics, metadata=metadata)


def _run_noise_reduction_workflow(df: pd.DataFrame, request: ModelWorkflowRequest, workflow_id: str) -> WorkflowResult:
    feature_cols = _resolve_feature_columns(request.mapping, df, require_label=False)
    working_df = df.copy().reset_index(drop=True)
    working_df["_row_id"] = np.arange(1, len(working_df) + 1)
    working_df, feature_cols = _apply_row_filters(working_df, feature_cols, "", request.preprocessing)
    _ensure_min_rows(working_df, 1, "Noise reduction")

    result_df = working_df.copy()
    result_df["_noise_score"] = 0.0
    result_df["_is_noise_candidate"] = False
    result_df["_noise_reason"] = ""
    result_df["_proposed_action"] = "keep"
    result_df["_applied_action"] = "keep"
    candidate_mask = pd.Series(False, index=result_df.index)

    if feature_cols:
        X = working_df[feature_cols].copy()
        preprocessor = _build_preprocessor(X, request.preprocessing)
        X_proc = preprocessor.fit_transform(X)
        contamination = float(request.params.get("contamination", 0.1))
        if len(X_proc) > 2:
            detector = IsolationForest(random_state=42, contamination=contamination)
            scores = -detector.fit(X_proc).decision_function(X_proc)
            anomaly_flags = detector.predict(X_proc) == -1
        else:
            scores = np.zeros(len(X_proc))
            anomaly_flags = np.zeros(len(X_proc), dtype=bool)
        result_df["_noise_score"] = scores
        result_df["_is_noise_candidate"] = anomaly_flags
        result_df["_noise_reason"] = np.where(anomaly_flags, "outlier_candidate", "stable")
        candidate_mask |= pd.Series(anomaly_flags, index=result_df.index)

    missing_ratio = working_df.isna().mean(axis=1)
    missing_mask = missing_ratio >= float(request.params.get("missing_row_threshold", 0.5))
    result_df.loc[missing_mask, "_is_noise_candidate"] = True
    result_df.loc[missing_mask, "_noise_reason"] = "high_missing_rate"
    result_df.loc[missing_mask, "_proposed_action"] = "drop_row"
    candidate_mask |= missing_mask

    duplicate_mask = working_df.duplicated(keep=False)
    result_df.loc[duplicate_mask, "_is_noise_candidate"] = True
    result_df.loc[duplicate_mask, "_noise_reason"] = "duplicate_row"
    result_df.loc[duplicate_mask, "_proposed_action"] = "drop_row"
    candidate_mask |= duplicate_mask

    apply_mode = str(request.params.get("apply_mode", "preview")).lower()
    if apply_mode == "auto":
        result_df = result_df.loc[~candidate_mask].reset_index(drop=True)
        result_df["_applied_action"] = "keep_after_auto_drop"

    metrics = {
        "noise_candidate_count": int(candidate_mask.sum()),
        "retained_count": int(len(result_df)),
        "apply_mode": apply_mode,
    }
    metadata = {
        "workflow_id": workflow_id,
        "use_case": request.use_case.value,
        "feature_columns": feature_cols,
        "row_count": int(len(result_df)),
        "metrics": metrics,
    }
    return WorkflowResult(result_df=result_df, metrics=metrics, metadata=metadata)


def _apply_row_filters(
    working_df: pd.DataFrame,
    feature_cols: list[str],
    label_column: str,
    preprocessing,
) -> tuple[pd.DataFrame, list[str]]:
    filtered_df = working_df.copy().reset_index(drop=True)
    active_features = list(feature_cols)

    if label_column and label_column in filtered_df.columns:
        filtered_df = filtered_df.dropna(subset=[label_column]).reset_index(drop=True)

    handle_missing = str(getattr(preprocessing, "handle_missing", "mean"))
    if handle_missing == "drop":
        drop_columns = [col for col in active_features if col in filtered_df.columns]
        if label_column in filtered_df.columns:
            drop_columns.append(label_column)
        drop_columns = [col for col in drop_columns if col in filtered_df.columns]
        if drop_columns:
            filtered_df = filtered_df.dropna(subset=drop_columns).reset_index(drop=True)

    if getattr(preprocessing, "outlier_removal", False) and active_features:
        numeric_feature_cols = [col for col in active_features if col in filtered_df.columns and pd.api.types.is_numeric_dtype(filtered_df[col])]
        if numeric_feature_cols:
            keep_mask = pd.Series(True, index=filtered_df.index)
            for col in numeric_feature_cols:
                series = pd.to_numeric(filtered_df[col], errors="coerce")
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                if pd.isna(iqr) or iqr == 0:
                    continue
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                keep_mask &= series.between(lower, upper, inclusive="both")
            filtered_df = filtered_df.loc[keep_mask].reset_index(drop=True)

    return filtered_df, active_features


def _ensure_min_rows(df: pd.DataFrame, minimum: int, workflow_name: str) -> None:
    if len(df) < minimum:
        raise ValueError(f"{workflow_name} requires at least {minimum} usable rows after preprocessing")


def _resolve_feature_columns(mapping: ColumnMapping, df: pd.DataFrame, require_label: bool) -> list[str]:
    excluded = {
        c
        for c in [
            mapping.label_column,
            mapping.id_column,
            mapping.user_id_column,
            mapping.item_id_column,
            mapping.rating_column,
            mapping.timestamp_column,
        ]
        if c
    }
    feature_cols = [col for col in mapping.feature_columns if col in df.columns and col not in excluded]
    if require_label and mapping.label_column and mapping.label_column in feature_cols:
        feature_cols = [col for col in feature_cols if col != mapping.label_column]
    if not feature_cols:
        feature_cols = [col for col in df.columns if col not in excluded]
    return feature_cols


def _build_preprocessor(X: pd.DataFrame, preprocessing) -> ColumnTransformer:
    numeric_cols = [col for col in X.columns if pd.api.types.is_numeric_dtype(X[col])]
    categorical_cols = [col for col in X.columns if col not in numeric_cols]

    missing_strategy = str(getattr(preprocessing, "handle_missing", "mean"))
    normalization = str(getattr(preprocessing, "normalization", "minmax"))
    categorical_encoding = str(getattr(preprocessing, "categorical_encoding", "label"))

    if missing_strategy == "median":
        numeric_imputer = SimpleImputer(strategy="median")
    elif missing_strategy == "zero":
        numeric_imputer = SimpleImputer(strategy="constant", fill_value=0)
    else:
        numeric_imputer = SimpleImputer(strategy="mean")

    numeric_steps = [("imputer", numeric_imputer)]
    if normalization == "standard":
        numeric_steps.append(("scaler", StandardScaler()))
    elif normalization == "minmax":
        numeric_steps.append(("scaler", MinMaxScaler()))

    if categorical_encoding == "onehot":
        try:
            categorical_encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        except TypeError:
            categorical_encoder = OneHotEncoder(handle_unknown="ignore", sparse=False)
    else:
        categorical_encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)

    transformers = []
    if numeric_cols:
        transformers.append(("numeric", Pipeline(numeric_steps), numeric_cols))
    if categorical_cols:
        transformers.append((
            "categorical",
            Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", categorical_encoder),
            ]),
            categorical_cols,
        ))

    return ColumnTransformer(transformers=transformers, remainder="drop")


def _split_with_indices(X: pd.DataFrame, y: pd.Series, **kwargs):
    indices = np.arange(len(X))
    train_idx, test_idx = train_test_split(indices, **kwargs)
    return (
        X.iloc[train_idx].reset_index(drop=True),
        X.iloc[test_idx].reset_index(drop=True),
        y.iloc[train_idx].reset_index(drop=True),
        y.iloc[test_idx].reset_index(drop=True),
        train_idx,
        test_idx,
    )


def _build_confusion_matrix(y_true: pd.Series, y_pred: pd.Series) -> dict[str, Any]:
    labels = sorted(set(y_true.astype(str).tolist()) | set(y_pred.astype(str).tolist()))
    matrix = confusion_matrix(y_true.astype(str), y_pred.astype(str), labels=labels)
    return {
        "labels": labels,
        "matrix": matrix.tolist(),
    }


def _coerce_binary_labels(series: pd.Series) -> list[int] | None:
    normalized = series.astype(str).str.lower().str.strip()
    positive_values = {"1", "true", "yes", "anomaly", "outlier", "bad", "noise"}
    negative_values = {"0", "false", "no", "normal", "clean", "ok"}
    if not set(normalized.unique()).issubset(positive_values | negative_values):
        return None
    return [1 if value in positive_values else 0 for value in normalized]


def _build_item_scores(df: pd.DataFrame, item_col: str, rating_col: str | None) -> dict[str, float]:
    if rating_col and rating_col in df.columns:
        numeric_rating = pd.to_numeric(df[rating_col], errors="coerce")
        grouped = df.assign(_rating=numeric_rating).groupby(item_col)["_rating"].agg(["mean", "count"])
        return {
            str(item): float(row["mean"] if pd.notna(row["mean"]) else 0.0) + float(row["count"]) * 0.01
            for item, row in grouped.iterrows()
        }
    counts = df[item_col].astype(str).value_counts()
    return {str(item): float(count) for item, count in counts.items()}


def _cluster_centroids(X_proc, labels):
    centroids: dict[int, np.ndarray] = {}
    for label in sorted(set(labels)):
        if label == -1:
            continue
        members = X_proc[labels == label]
        if len(members) > 0:
            centroids[int(label)] = np.asarray(members).mean(axis=0)
    return centroids


def _distance_to_centroids(X_proc, labels, centroids: dict[int, np.ndarray]) -> np.ndarray:
    distances = np.zeros(len(X_proc))
    for index, label in enumerate(labels):
        if label == -1 or int(label) not in centroids:
            if centroids:
                distances[index] = min(float(np.linalg.norm(np.asarray(X_proc[index]) - centroid)) for centroid in centroids.values())
            continue
        distances[index] = float(np.linalg.norm(np.asarray(X_proc[index]) - centroids[int(label)]))
    return distances
