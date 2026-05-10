import pytest
import pandas as pd
import numpy as np
from app.services.ml.model_workflows import _run_prediction_workflow, run_model_workflow
from app.models.schemas import ModelWorkflowRequest, UseCaseType, ColumnMapping, PreprocessingSettings

def test_run_prediction_workflow_classification():
    df = pd.DataFrame({
        "f1": [1.0, 2.0, 1.1, 2.1, 1.2, 2.2, 1.3, 2.3, 1.4, 2.4],
        "target": ["A", "B", "A", "B", "A", "B", "A", "B", "A", "B"],
        "id": range(10)
    })
    
    mapping = ColumnMapping(feature_columns=["f1"], label_column="target", id_column="id")
    request = ModelWorkflowRequest(
        workbook_id="w1",
        sheet_name="s1",
        use_case=UseCaseType.CLASSIFICATION,
        mapping=mapping,
        algorithm="random_forest",
        params={"test_size": 0.2, "random_state": 42}
    )
    
    result = _run_prediction_workflow(df, request, "wf-123")
    
    assert result.result_df.shape[0] == 10
    assert "_predicted_class" in result.result_df.columns
    assert "accuracy" in result.metrics
    assert result.metadata["use_case"] == "classification"

def test_run_prediction_workflow_regression():
    df = pd.DataFrame({
        "f1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        "target": [1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1, 9.1, 10.1],
        "id": range(10)
    })
    
    mapping = ColumnMapping(feature_columns=["f1"], label_column="target", id_column="id")
    request = ModelWorkflowRequest(
        workbook_id="w1",
        sheet_name="s1",
        use_case=UseCaseType.PREDICTION,
        mapping=mapping,
        algorithm="random_forest",
        params={"task_type": "regression", "test_size": 0.2, "random_state": 42}
    )
    
    result = _run_prediction_workflow(df, request, "wf-123")
    
    assert "_predicted_value" in result.result_df.columns
    assert "mae" in result.metrics
    assert result.metrics["r2"] > 0

def test_run_anomaly_workflow():
    df = pd.DataFrame({
        "f1": [1.0, 1.1, 1.2, 10.0, 1.1, 1.2],
        "target": [0, 0, 0, 1, 0, 0] # 10.0 is an outlier
    })
    request = ModelWorkflowRequest(
        workbook_id="w1",
        sheet_name="s1",
        use_case=UseCaseType.ANOMALY_DETECTION,
        algorithm="isolation_forest",
        mapping=ColumnMapping(feature_columns=["f1"], label_column="target")
    )
    
    result = run_model_workflow(df, request, "wf_anomaly")
    
    assert "_anomaly_score" in result.result_df.columns
    assert result.result_df["_is_anomaly"].any()
    assert "anomaly_count" in result.metrics

def test_run_clustering_workflow():
    df = pd.DataFrame({
        "f1": [1.0, 1.1, 5.0, 5.1, 10.0, 10.1],
        "f2": [1.0, 1.1, 5.0, 5.1, 10.0, 10.1]
    })
    request = ModelWorkflowRequest(
        workbook_id="w1",
        sheet_name="s1",
        use_case=UseCaseType.CLUSTERING,
        algorithm="kmeans",
        params={"cluster_count": 3},
        mapping=ColumnMapping(feature_columns=["f1", "f2"])
    )
    
    result = run_model_workflow(df, request, "wf_clustering")
    
    assert "_cluster_id" in result.result_df.columns
    assert result.result_df["_cluster_id"].nunique() <= 3
    assert "cluster_count" in result.metrics

def test_run_recommendation_workflow():
    df = pd.DataFrame({
        "user_id": ["u1", "u1", "u2", "u3"],
        "item_id": ["i1", "i2", "i1", "i3"],
        "rating": [5, 4, 5, 2]
    })
    request = ModelWorkflowRequest(
        workbook_id="w1",
        sheet_name="s1",
        use_case=UseCaseType.RECOMMENDATION,
        algorithm="popularity_baseline",
        params={"top_k": 2},
        mapping=ColumnMapping(
            user_id_column="user_id",
            item_id_column="item_id",
            rating_column="rating"
        )
    )
    
    result = run_model_workflow(df, request, "wf_rec")
    
    assert "recommended_item_id" in result.result_df.columns
    assert len(result.result_df) > 0
    assert "user_count" in result.metrics
