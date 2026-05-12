from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.inspection import permutation_importance
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from app.services.ml.model_factory import build_model as _build_model


def run_analysis(
    df: pd.DataFrame,
    feature_cols: list,
    label_col: str = None,
    algorithm: str = "random_forest",
    preprocessing: dict = {},
    run_cleansing: bool = True,
    run_feature_selection: bool = True,
    run_ml: bool = True,
):
    metadata: dict = {}

    if not feature_cols:
        raise ValueError("At least one feature column must be selected")

    working_df = df.copy()
    working_df = working_df.reset_index(drop=True)
    working_df["_row_id"] = np.arange(1, len(working_df) + 1)

    X_raw = working_df[feature_cols].copy()
    numeric_cols = [col for col in X_raw.columns if pd.api.types.is_numeric_dtype(X_raw[col])]
    categorical_cols = [col for col in X_raw.columns if col not in numeric_cols]

    if run_cleansing and preprocessing.get("handle_missing") == "drop":
        drop_mask = X_raw.isna().any(axis=1)
        working_df = working_df.loc[~drop_mask].reset_index(drop=True)
        X_raw = working_df[feature_cols].copy()
        numeric_cols = [col for col in X_raw.columns if pd.api.types.is_numeric_dtype(X_raw[col])]
        categorical_cols = [col for col in X_raw.columns if col not in numeric_cols]

    if run_cleansing:
        missing_method = preprocessing.get("handle_missing", "mean")
        for col in numeric_cols:
            numeric_series = pd.to_numeric(X_raw[col], errors="coerce")
            fill_value = _resolve_numeric_fill_value(numeric_series, missing_method)
            X_raw[col] = numeric_series.fillna(fill_value)

        for col in categorical_cols:
            if X_raw[col].dropna().empty:
                fill_value = "unknown"
            else:
                fill_value = X_raw[col].mode(dropna=True).iloc[0]
            X_raw[col] = X_raw[col].fillna(fill_value).astype(str)

        if preprocessing.get("outlier_removal"):
            keep_mask = pd.Series(True, index=working_df.index)
            for col in numeric_cols:
                series = pd.to_numeric(X_raw[col], errors="coerce")
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                keep_mask &= series.between(lower, upper, inclusive="both")
            working_df = working_df.loc[keep_mask].reset_index(drop=True)
            X_raw = X_raw.loc[keep_mask].reset_index(drop=True)

    encoded_parts = []
    if numeric_cols:
        numeric_frame = X_raw[numeric_cols].apply(pd.to_numeric, errors="coerce")
        encoded_parts.append(numeric_frame)
    if categorical_cols:
        categorical_frame = X_raw[categorical_cols].astype(str)
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

    X_model = pd.concat(encoded_parts, axis=1)

    if run_cleansing and preprocessing.get("normalization", "minmax") != "none":
        norm_type = preprocessing.get("normalization", "minmax")
        scaler = MinMaxScaler() if norm_type == "minmax" else StandardScaler()
        X_scaled = scaler.fit_transform(X_model)
        X_model = pd.DataFrame(X_scaled, columns=X_model.columns, index=X_model.index)

    result_df = working_df.copy()
    if run_cleansing:
        # Reflect cleansing values directly into prepared rows so the grid shows
        # imputed/re-encoded source values rather than keeping blanks.
        for col in feature_cols:
            if col in X_raw.columns:
                result_df[col] = X_raw[col].values

        norm_prefix = preprocessing.get("normalization", "minmax")
        if numeric_cols and norm_prefix != "none":
            scaler = MinMaxScaler() if norm_prefix == "minmax" else StandardScaler()
            scaled_numeric = scaler.fit_transform(X_raw[numeric_cols].apply(pd.to_numeric, errors="coerce"))
            scaled_frame = pd.DataFrame(scaled_numeric, columns=numeric_cols, index=result_df.index)
            for col in numeric_cols:
                result_df[col] = scaled_frame[col]
                # Keep legacy normalized helper columns for compatibility.
                result_df[f"norm_{col}"] = scaled_frame[col]

    if run_feature_selection and label_col and label_col in result_df.columns:
        y_for_importance = result_df[label_col].copy()
        y_for_importance = y_for_importance.fillna(
            "unknown" if y_for_importance.dtype == object else 0
        )
        y_for_importance = y_for_importance.loc[X_model.index]

        importance_is_classification = (
            pd.api.types.is_object_dtype(y_for_importance)
            or pd.api.types.is_string_dtype(y_for_importance)
            or str(y_for_importance.dtype).startswith("category")
        )
        if importance_is_classification:
            importance_target = pd.factorize(y_for_importance.astype(str), sort=True)[0]
        else:
            importance_target = pd.to_numeric(y_for_importance, errors="coerce").fillna(0)

        importance_model = _build_model(
            algorithm,
            pd.Series(importance_target, index=X_model.index),
            force_classification=importance_is_classification,
        )
        if hasattr(importance_model, "fit"):
            importance_model.fit(X_model, importance_target)
            if hasattr(importance_model, "feature_importances_"):
                importance_map = {
                    column: float(score)
                    for column, score in zip(X_model.columns, importance_model.feature_importances_)
                }
            else:
                scoring = "accuracy" if importance_is_classification else "r2"
                try:
                    permutation = permutation_importance(
                        importance_model,
                        X_model,
                        importance_target,
                        n_repeats=10,
                        random_state=42,
                        scoring=scoring,
                    )
                    importance_map = {
                        column: float(max(0.0, score))
                        for column, score in zip(X_model.columns, permutation.importances_mean)
                    }
                except Exception:
                    importance_map = {}

            if importance_map:
                metadata["feature_importance"] = importance_map

    if run_ml and label_col and label_col in result_df.columns:
        y = result_df[label_col].copy()
        y = y.fillna("unknown" if y.dtype == object else 0)
        y = y.loc[X_model.index]

        if y.nunique(dropna=True) > 1:
            model = _build_model(algorithm, y)
            model.fit(X_model, y)
            predictions = model.predict(X_model)
            result_df["_predicted_class"] = predictions

            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(X_model)
                result_df["_prediction_confidence"] = np.max(probs, axis=1)
            else:
                result_df["_prediction_confidence"] = 1.0
        else:
            result_df["_predicted_class"] = y.iloc[0]
            result_df["_prediction_confidence"] = 1.0

    cluster_input = X_model.copy()
    if cluster_input.shape[1] > 1:
        pca_components = min(3, cluster_input.shape[1])
        cluster_basis = PCA(n_components=pca_components, random_state=42).fit_transform(cluster_input)
    else:
        cluster_basis = cluster_input.to_numpy()

    min_samples = max(2, min(10, max(1, len(cluster_input) // 20)))
    dbscan = DBSCAN(eps=0.8, min_samples=min_samples)
    cluster_labels = dbscan.fit_predict(cluster_basis)

    cluster_series = pd.Series(cluster_labels, index=result_df.index)
    cluster_sizes = cluster_series.value_counts().to_dict()
    is_outlier = cluster_series == -1
    island_threshold = max(3, len(result_df) // 20)
    is_island = cluster_series.map(lambda label: cluster_sizes.get(label, 0) <= island_threshold or label == -1)

    result_df["_cluster_id"] = cluster_series.map(lambda label: f"cluster_{label}" if label != -1 else "noise")
    result_df["_is_island"] = is_island.astype(bool)
    result_df["_is_outlier"] = is_outlier.astype(bool)

    cluster_major_class = {}
    if label_col and label_col in result_df.columns:
        for label in sorted(set(cluster_labels)):
            if label == -1:
                continue
            rows = result_df.loc[cluster_series == label, label_col]
            if not rows.empty:
                cluster_major_class[label] = rows.mode(dropna=True).iloc[0]

    centroids = {}
    for label in sorted(set(cluster_labels)):
        if label == -1:
            continue
        rows = cluster_basis[cluster_labels == label]
        if len(rows) > 0:
            centroids[label] = rows.mean(axis=0)

    nearest_major_class = []
    review_priority = []
    for idx, label in enumerate(cluster_labels):
        if centroids and len(centroids) > 1:
            candidate_labels = [cluster_label for cluster_label in centroids if cluster_label != label]
            if candidate_labels:
                distances = {
                    candidate: float(np.linalg.norm(cluster_basis[idx] - centroids[candidate]))
                    for candidate in candidate_labels
                }
                nearest_label = min(distances, key=distances.get)
            else:
                nearest_label = label
        else:
            nearest_label = label

        if label == -1 and centroids:
            distances = {
                candidate: float(np.linalg.norm(cluster_basis[idx] - centroid))
                for candidate, centroid in centroids.items()
            }
            nearest_label = min(distances, key=distances.get)

        if label_col and label_col in result_df.columns:
            nearest_major_class.append(cluster_major_class.get(nearest_label))
        else:
            nearest_major_class.append(f"cluster_{nearest_label}" if nearest_label != -1 else "noise")

        base_priority = 90 if label == -1 else 70 if cluster_sizes.get(label, 0) <= island_threshold else 30
        if "_prediction_confidence" in result_df.columns:
            confidence = result_df.loc[idx, "_prediction_confidence"]
            if pd.notna(confidence):
                base_priority = int(min(100, base_priority + max(0, int((1 - float(confidence)) * 20))))
        review_priority.append(base_priority)

    result_df["_nearest_major_class"] = nearest_major_class
    result_df["_review_priority"] = review_priority

    nano_decisions: dict[str, dict[str, str]] = {}
    for label in sorted(set(cluster_labels)):
        if label == -1:
            continue
        cluster_key = f"cluster_{label}"
        if not bool(is_island.loc[cluster_series == label].any()):
            continue
        cluster_rows = X_model.loc[cluster_series == label]
        if cluster_rows.empty:
            continue
        global_mean = X_model.mean(numeric_only=True)
        cluster_mean = cluster_rows.mean(numeric_only=True)
        feature_diffs = (
            (cluster_mean - global_mean)
            .abs()
            .sort_values(ascending=False)
            .head(3)
        )
        top_feature_differences = [
            {
                "feature": feature,
                "cluster_mean": float(cluster_mean.get(feature, 0.0)),
                "global_mean": float(global_mean.get(feature, 0.0)),
            }
            for feature in feature_diffs.index
        ]
        representative_index = cluster_rows.index[0]
        summary = {
            "cluster_id": cluster_key,
            "size": int(len(cluster_rows)),
            "predicted_class": (
                cluster_major_class.get(label) if cluster_major_class else None
            ),
            "nearby_major_class": nearest_major_class[representative_index] if representative_index < len(nearest_major_class) else None,
            "top_feature_differences": top_feature_differences,
            "is_outlier": False,
        }
        nano_decisions[cluster_key] = _fallback_cluster_explanation(summary)

    result_df["_nano_decision"] = ""
    result_df["_nano_reason"] = ""
    result_df["_nano_recommended_action"] = ""
    for idx, label in enumerate(cluster_labels):
        if label == -1:
            continue
        cluster_key = f"cluster_{label}"
        decision = nano_decisions.get(cluster_key)
        if not decision:
            continue
        result_df.loc[idx, "_nano_decision"] = decision.get("decision", "")
        result_df.loc[idx, "_nano_reason"] = decision.get("reason", "")
        result_df.loc[idx, "_nano_recommended_action"] = decision.get("recommended_action", "")

    metadata["row_count"] = int(len(result_df))
    metadata["feature_count"] = int(X_model.shape[1])
    metadata["island_count"] = int(is_island.sum())
    metadata["outlier_count"] = int(is_outlier.sum())
    metadata["nano_explanations"] = int(len(nano_decisions))

    return result_df, metadata


def _fallback_cluster_explanation(summary: dict) -> dict[str, str]:
    size = int(summary.get("size", 0) or 0)
    top_features = summary.get("top_feature_differences", []) or []
    feature_names = [str(item.get("feature")) for item in top_features if item.get("feature")]
    if size <= 3:
        return {
            "decision": "likely_outlier",
            "reason": "Small isolated cluster may be unstable for learning.",
            "recommended_action": "review_manually",
        }
    if feature_names:
        return {
            "decision": "merge_with_nearest_cluster",
            "reason": f"Cluster differs mainly on {', '.join(feature_names[:2])}.",
            "recommended_action": "review_manually",
        }
    return {
        "decision": "review_manually",
        "reason": "Cluster needs manual inspection.",
        "recommended_action": "review_manually",
    }


def _resolve_numeric_fill_value(series: pd.Series, method: str) -> float:
    if method == "median":
        fill_value = series.median()
    elif method == "zero":
        fill_value = 0.0
    else:
        fill_value = series.mean()
    if pd.isna(fill_value):
        return 0.0
    return float(fill_value)
