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


def build_model(algorithm: str, y: pd.Series, force_classification: bool | None = None):
    is_classification = force_classification if force_classification is not None else (
        pd.api.types.is_object_dtype(y)
        or pd.api.types.is_string_dtype(y)
        or str(y.dtype).startswith("category")
    )

    if algorithm == "random_forest":
        return RandomForestClassifier(random_state=42) if is_classification else RandomForestRegressor(random_state=42)
    if algorithm == "gradient_boosting":
        return GradientBoostingClassifier(random_state=42) if is_classification else GradientBoostingRegressor(random_state=42)
    if algorithm == "svm":
        return SVC(probability=True) if is_classification else SVR()
    if algorithm == "logistic_regression":
        return LogisticRegression(max_iter=1000) if is_classification else LinearRegression()
    if algorithm == "linear_regression":
        return LogisticRegression(max_iter=1000) if is_classification else LinearRegression()
    return RandomForestClassifier(random_state=42) if is_classification else RandomForestRegressor(random_state=42)
