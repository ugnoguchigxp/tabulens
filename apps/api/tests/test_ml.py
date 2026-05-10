import pytest
import pandas as pd
from app.services.ml.model_factory import build_model
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.svm import SVC

def test_build_model_classification():
    y = pd.Series(["a", "b", "a"])
    model = build_model("random_forest", y)
    assert isinstance(model, RandomForestClassifier)

def test_build_model_regression():
    y = pd.Series([1.0, 2.0, 3.0])
    model = build_model("random_forest", y)
    assert isinstance(model, RandomForestRegressor)

def test_build_model_svm():
    y = pd.Series(["a", "b", "a"])
    model = build_model("svm", y)
    assert isinstance(model, SVC)

def test_build_model_force():
    y = pd.Series([1.0, 2.0, 1.0])
    model = build_model("random_forest", y, force_classification=True)
    assert isinstance(model, RandomForestClassifier)
