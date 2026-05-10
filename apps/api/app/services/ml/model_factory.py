from __future__ import annotations

from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.svm import SVC, SVR
import pandas as pd


def build_model(
    algorithm: str,
    y: pd.Series,
    force_classification: bool | None = None,
    params: dict | None = None,
):
    params = params or {}
    is_classification = force_classification if force_classification is not None else (
        pd.api.types.is_object_dtype(y)
        or pd.api.types.is_string_dtype(y)
        or str(y.dtype).startswith("category")
    )
    class_weight = params.get("class_weight")

    if algorithm == "random_forest":
        if is_classification:
            kwargs = {"random_state": 42}
            if class_weight is not None:
                kwargs["class_weight"] = class_weight
            return RandomForestClassifier(**kwargs)
        return RandomForestRegressor(random_state=42)
    if algorithm == "gradient_boosting":
        return GradientBoostingClassifier(random_state=42) if is_classification else GradientBoostingRegressor(random_state=42)
    if algorithm == "svm":
        if is_classification:
            kwargs = {"probability": True}
            if class_weight is not None:
                kwargs["class_weight"] = class_weight
            return SVC(**kwargs)
        return SVR()
    if algorithm == "logistic_regression":
        if is_classification:
            kwargs = {"max_iter": 1000}
            if class_weight is not None:
                kwargs["class_weight"] = class_weight
            return LogisticRegression(**kwargs)
        return LinearRegression()
    if algorithm == "linear_regression":
        if is_classification:
            kwargs = {"max_iter": 1000}
            if class_weight is not None:
                kwargs["class_weight"] = class_weight
            return LogisticRegression(**kwargs)
        return LinearRegression()
    if is_classification:
        kwargs = {"random_state": 42}
        if class_weight is not None:
            kwargs["class_weight"] = class_weight
        return RandomForestClassifier(**kwargs)
    return RandomForestRegressor(random_state=42)
