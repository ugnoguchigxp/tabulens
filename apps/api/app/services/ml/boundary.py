from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.inspection import permutation_importance

from app.models.schemas import BoundaryAxisRange, BoundaryGridCell, BoundaryPoint, BoundarySnapshot, JobRequest
from app.services.ml.classifier import _build_model


def build_boundary_snapshot(
    *,
    job_id: str,
    source_df: pd.DataFrame,
    result_df: pd.DataFrame,
    request: JobRequest,
    grid_resolution: int = 40,
) -> BoundarySnapshot:
    feature_cols = [col for col in request.mapping.feature_columns if col in source_df.columns]
    label_col = request.mapping.label_column if request.mapping.label_column in source_df.columns else None

    if not feature_cols:
        raise ValueError("Boundary explorer requires at least one feature column")
    if not label_col:
        raise ValueError("Boundary explorer requires a label column")
    if not request.run_ml:
        raise ValueError("Boundary explorer requires ML to be enabled")

    working_df, x_model, numeric_cols = _prepare_analysis_inputs(
        source_df,
        feature_cols,
        request.preprocessing.model_dump() if hasattr(request.preprocessing, "model_dump") else request.preprocessing.dict(),
        run_cleansing=request.run_cleansing,
    )

    if len(feature_cols) < 2:
        raise ValueError("Boundary explorer requires at least two feature columns")
    if x_model.shape[1] < 2:
        raise ValueError("Boundary explorer requires at least two usable features after preprocessing")

    y = working_df[label_col].copy()
    y = y.fillna("unknown" if _is_classification_target(y) else 0)
    if not _is_classification_target(y):
        raise ValueError("Boundary explorer is only available for classification jobs")
    if y.nunique(dropna=True) < 2:
        raise ValueError("Boundary explorer requires at least two classes")

    if request.run_feature_selection:
        x_model = _apply_feature_selection(
            x_model=x_model,
            y=y,
            algorithm=getattr(request.algorithm, "value", str(request.algorithm)),
            preprocessing=request.preprocessing.model_dump() if hasattr(request.preprocessing, "model_dump") else request.preprocessing.dict(),
        )

    if x_model.shape[1] < 2:
        raise ValueError("Boundary explorer requires at least two usable features after feature selection")

    model = _build_model(getattr(request.algorithm, "value", str(request.algorithm)), y, force_classification=True)
    model.fit(x_model, y)

    predictions = pd.Series(model.predict(x_model), index=working_df.index)
    confidences = _estimate_confidence(model, x_model)

    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(x_model)
    x_min = float(coords[:, 0].min())
    x_max = float(coords[:, 0].max())
    y_min = float(coords[:, 1].min())
    y_max = float(coords[:, 1].max())
    x_span = max(x_max - x_min, 1e-6)
    y_span = max(y_max - y_min, 1e-6)
    x_margin = x_span * 0.18
    y_margin = y_span * 0.18

    x_values = np.linspace(x_min - x_margin, x_max + x_margin, grid_resolution)
    y_values = np.linspace(y_min - y_margin, y_max + y_margin, grid_resolution)
    grid_x, grid_y = np.meshgrid(x_values, y_values)
    grid_points = np.column_stack([grid_x.ravel(), grid_y.ravel()])
    model_points = pca.inverse_transform(grid_points)
    grid_predictions = pd.Series(model.predict(model_points))
    grid_confidence = _estimate_confidence(model, pd.DataFrame(model_points, columns=x_model.columns))

    result_indexed = result_df.copy()
    if "_row_id" in result_indexed.columns:
        result_indexed = result_indexed.set_index("_row_id", drop=False)
    else:
        result_indexed = result_indexed.copy()
        result_indexed["_row_id"] = working_df["_row_id"].values
        result_indexed = result_indexed.set_index("_row_id", drop=False)

    points: list[BoundaryPoint] = []
    for position, (row_id, row) in enumerate(working_df.set_index("_row_id", drop=False).iterrows()):
        source_row = result_indexed.loc[row_id] if row_id in result_indexed.index else row
        true_value = row[label_col]
        predicted_value = source_row.get("_predicted_class", predictions.iloc[position])
        confidence_value = source_row.get("_prediction_confidence", confidences[position])
        is_misclassified = _stringify(true_value) != _stringify(predicted_value)
        cluster_id = source_row.get("_cluster_id")
        if isinstance(cluster_id, float) and pd.isna(cluster_id):
            cluster_id = None

        points.append(
            BoundaryPoint(
                row_id=int(row_id),
                x=float(coords[position, 0]),
                y=float(coords[position, 1]),
                true_label=_stringify(true_value),
                predicted_label=_stringify(predicted_value),
                confidence=float(confidence_value) if pd.notna(confidence_value) else 0.0,
                is_misclassified=is_misclassified,
                is_outlier=bool(source_row.get("_is_outlier", False)),
                is_island=bool(source_row.get("_is_island", False)),
                review_priority=int(source_row.get("_review_priority", 0) or 0),
                cluster_id=_stringify(cluster_id) if cluster_id not in {None, ""} else None,
            )
        )

    grid: list[BoundaryGridCell] = []
    for idx, (gx, gy) in enumerate(grid_points):
        grid.append(
            BoundaryGridCell(
                x=float(gx),
                y=float(gy),
                predicted_label=_stringify(grid_predictions.iloc[idx]),
                confidence=float(grid_confidence[idx]) if pd.notna(grid_confidence[idx]) else 0.0,
            )
        )

    classes = [str(value) for value in getattr(model, "classes_", pd.unique(y))]
    statistics = {
        "point_count": int(len(points)),
        "misclassified_count": int(sum(1 for item in points if item.is_misclassified)),
        "low_confidence_count": int(sum(1 for item in points if item.confidence < 0.6)),
        "outlier_count": int(sum(1 for item in points if item.is_outlier)),
        "island_count": int(sum(1 for item in points if item.is_island)),
        "feature_count": int(x_model.shape[1]),
        "numeric_feature_count": int(len(numeric_cols)),
        "grid_point_count": int(len(grid)),
    }
    if hasattr(pca, "explained_variance_ratio_"):
        statistics["explained_variance_ratio"] = [float(value) for value in pca.explained_variance_ratio_]

    return BoundarySnapshot(
        job_id=job_id,
        projection="pca",
        x_axis=BoundaryAxisRange(label="PCA 1", minimum=x_min - x_margin, maximum=x_max + x_margin),
        y_axis=BoundaryAxisRange(label="PCA 2", minimum=y_min - y_margin, maximum=y_max + y_margin),
        grid_resolution=grid_resolution,
        grid_step_x=float((x_values[1] - x_values[0]) if len(x_values) > 1 else 0.0),
        grid_step_y=float((y_values[1] - y_values[0]) if len(y_values) > 1 else 0.0),
        class_labels=classes,
        explained_variance_ratio=[float(value) for value in getattr(pca, "explained_variance_ratio_", [])],
        points=points,
        grid=grid,
        statistics=statistics,
    )


def _prepare_analysis_inputs(
    df: pd.DataFrame,
    feature_cols: list[str],
    preprocessing: dict[str, Any],
    *,
    run_cleansing: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    working_df = df.copy()
    working_df = working_df.reset_index(drop=True)
    working_df["_row_id"] = np.arange(1, len(working_df) + 1)

    x_raw = working_df[feature_cols].copy()
    numeric_cols = [col for col in x_raw.columns if pd.api.types.is_numeric_dtype(x_raw[col])]
    categorical_cols = [col for col in x_raw.columns if col not in numeric_cols]

    if run_cleansing and preprocessing.get("handle_missing") == "drop":
        drop_mask = x_raw.isna().any(axis=1)
        working_df = working_df.loc[~drop_mask].reset_index(drop=True)
        x_raw = working_df[feature_cols].copy()
        numeric_cols = [col for col in x_raw.columns if pd.api.types.is_numeric_dtype(x_raw[col])]
        categorical_cols = [col for col in x_raw.columns if col not in numeric_cols]

    if run_cleansing:
        missing_method = preprocessing.get("handle_missing", "mean")
        for col in numeric_cols:
            numeric_series = pd.to_numeric(x_raw[col], errors="coerce")
            if missing_method == "mean":
                fill_value = numeric_series.mean()
            elif missing_method == "median":
                fill_value = numeric_series.median()
            elif missing_method == "zero":
                fill_value = 0
            else:
                fill_value = numeric_series.mean()
            x_raw[col] = numeric_series.fillna(fill_value)

        for col in categorical_cols:
            if x_raw[col].dropna().empty:
                fill_value = "unknown"
            else:
                fill_value = x_raw[col].mode(dropna=True).iloc[0]
            x_raw[col] = x_raw[col].fillna(fill_value).astype(str)

        if preprocessing.get("outlier_removal"):
            keep_mask = pd.Series(True, index=working_df.index)
            for col in numeric_cols:
                series = pd.to_numeric(x_raw[col], errors="coerce")
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                keep_mask &= series.between(lower, upper, inclusive="both")
            working_df = working_df.loc[keep_mask].reset_index(drop=True)
            x_raw = x_raw.loc[keep_mask].reset_index(drop=True)

    encoded_parts: list[pd.DataFrame] = []
    if numeric_cols:
        numeric_frame = x_raw[numeric_cols].apply(pd.to_numeric, errors="coerce")
        encoded_parts.append(numeric_frame)
    if categorical_cols:
        categorical_frame = x_raw[categorical_cols].astype(str)
        encoding = preprocessing.get("categorical_encoding", "label")
        if encoding == "onehot":
            encoded_parts.append(pd.get_dummies(categorical_frame, prefix=categorical_cols, dummy_na=False))
        else:
            label_encoded = pd.DataFrame(index=categorical_frame.index)
            for col in categorical_cols:
                codes, _ = pd.factorize(categorical_frame[col], sort=True)
                label_encoded[col] = codes.astype(float)
            encoded_parts.append(label_encoded)

    if not encoded_parts:
        raise ValueError("No usable features found after preprocessing")

    x_model = pd.concat(encoded_parts, axis=1)

    if run_cleansing and preprocessing.get("normalization", "minmax") != "none":
        norm_type = preprocessing.get("normalization", "minmax")
        scaler = None
        if norm_type == "minmax":
            from sklearn.preprocessing import MinMaxScaler

            scaler = MinMaxScaler()
        else:
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x_model)
        x_model = pd.DataFrame(x_scaled, columns=x_model.columns, index=x_model.index)

    return working_df, x_model, numeric_cols


def _is_classification_target(y: pd.Series) -> bool:
    return (
        pd.api.types.is_object_dtype(y)
        or pd.api.types.is_string_dtype(y)
        or str(y.dtype).startswith("category")
    )


def _apply_feature_selection(
    *,
    x_model: pd.DataFrame,
    y: pd.Series,
    algorithm: str,
    preprocessing: dict[str, Any],
) -> pd.DataFrame:
    importance_is_classification = _is_classification_target(y)
    if importance_is_classification:
        importance_target = y.astype(str)
    else:
        importance_target = pd.to_numeric(y, errors="coerce").fillna(0)

    importance_model = _build_model(
        algorithm,
        pd.Series(importance_target, index=x_model.index),
        force_classification=importance_is_classification,
    )
    if not hasattr(importance_model, "fit"):
        return x_model

    importance_model.fit(x_model, importance_target)
    if hasattr(importance_model, "feature_importances_"):
        importance_map = {
            column: float(score)
            for column, score in zip(x_model.columns, importance_model.feature_importances_)
        }
    else:
        scoring = "accuracy" if importance_is_classification else "r2"
        try:
            permutation = permutation_importance(
                importance_model,
                x_model,
                importance_target,
                n_repeats=10,
                random_state=42,
                scoring=scoring,
            )
            importance_map = {
                column: float(max(0.0, score))
                for column, score in zip(x_model.columns, permutation.importances_mean)
            }
        except Exception:
            importance_map = {}

    threshold = preprocessing.get("feature_selection_threshold")
    if threshold is None or not importance_map:
        return x_model

    selected_features = [col for col, score in importance_map.items() if score >= threshold]
    if not selected_features:
        return x_model
    return x_model[selected_features]


def _estimate_confidence(model: Any, features: pd.DataFrame | np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(features)
        return np.max(probs, axis=1)
    if hasattr(model, "decision_function"):
        raw_scores = model.decision_function(features)
        scores = np.asarray(raw_scores)
        if scores.ndim == 1:
            return 1 / (1 + np.exp(-np.abs(scores)))
        shifted = scores - np.max(scores, axis=1, keepdims=True)
        exp_scores = np.exp(shifted)
        probs = exp_scores / np.clip(exp_scores.sum(axis=1, keepdims=True), 1e-9, None)
        return np.max(probs, axis=1)
    return np.full(shape=(len(features),), fill_value=0.5, dtype=float)


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    return str(value)
