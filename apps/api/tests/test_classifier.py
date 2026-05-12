import pytest
import pandas as pd
import numpy as np
from app.services.ml.classifier import run_analysis

def test_run_analysis_basic():
    df = pd.DataFrame({
        "f1": [1.0, 1.1, 1.2, 5.0, 5.1, 5.2, 10.0],
        "target": ["A", "A", "A", "B", "B", "B", "C"],
        "id": range(7)
    })
    
    result_df, metadata = run_analysis(
        df=df,
        feature_cols=["f1"],
        label_col="target",
        run_ml=True,
        run_cleansing=True
    )
    
    assert "_cluster_id" in result_df.columns
    assert "_predicted_class" in result_df.columns
    assert "feature_importance" in metadata
    assert metadata["row_count"] == 7

def test_run_analysis_no_label():
    df = pd.DataFrame({
        "f1": [1.0, 1.1, 1.2, 5.0, 5.1, 5.2, 10.0],
        "id": range(7)
    })
    
    result_df, metadata = run_analysis(
        df=df,
        feature_cols=["f1"],
        label_col=None,
        run_ml=False
    )
    
    assert "_cluster_id" in result_df.columns
    assert "_predicted_class" not in result_df.columns
    assert "feature_importance" not in metadata

def test_run_analysis_categorical():
    df = pd.DataFrame({
        "cat": ["X", "X", "Y", "Y", "Z", "Z"],
        "f1": [1, 2, 3, 4, 5, 6],
        "target": ["A", "A", "B", "B", "C", "C"]
    })
    
    result_df, metadata = run_analysis(
        df=df,
        feature_cols=["cat", "f1"],
        label_col="target",
        preprocessing={"categorical_encoding": "onehot"}
    )
    
    assert metadata["feature_count"] > 2 # because of one-hot


def test_run_analysis_reflects_imputation_and_normalization_in_feature_columns():
    df = pd.DataFrame({
        "f1": [1.0, np.nan, 3.0],
        "f2": [10.0, 20.0, np.nan],
        "target": ["A", "B", "A"],
    })

    result_df, _ = run_analysis(
        df=df,
        feature_cols=["f1", "f2"],
        label_col="target",
        preprocessing={"handle_missing": "mean", "normalization": "minmax"},
        run_cleansing=True,
        run_feature_selection=False,
        run_ml=False,
    )

    assert result_df["f1"].isna().sum() == 0
    assert result_df["f2"].isna().sum() == 0
    assert float(result_df["f1"].min()) >= 0.0
    assert float(result_df["f1"].max()) <= 1.0
    assert float(result_df["f2"].min()) >= 0.0
    assert float(result_df["f2"].max()) <= 1.0
    assert "norm_f1" in result_df.columns
    assert "norm_f2" in result_df.columns


def test_run_analysis_fills_all_missing_numeric_features_with_zero_when_mean_is_nan():
    df = pd.DataFrame({
        "f1": [np.nan, np.nan, np.nan],
        "target": ["A", "A", "A"],
    })

    result_df, _ = run_analysis(
        df=df,
        feature_cols=["f1"],
        label_col="target",
        preprocessing={"handle_missing": "mean", "normalization": "none"},
        run_cleansing=True,
        run_feature_selection=False,
        run_ml=False,
    )

    assert result_df["f1"].isna().sum() == 0
    assert set(result_df["f1"].tolist()) == {0.0}
