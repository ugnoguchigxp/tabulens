import pytest
import pandas as pd
import numpy as np
from app.services.ml.boundary import build_boundary_snapshot
from app.models.schemas import JobRequest, ColumnMapping, ModelWorkflowRequest

def test_build_boundary_snapshot_basic():
    df = pd.DataFrame({
        "f1": [1.0, 2.0, 1.1, 2.1, 1.2, 2.2, 1.3, 2.3, 1.4, 2.4],
        "f2": [5.0, 6.0, 5.1, 6.1, 5.2, 6.2, 5.3, 6.3, 5.4, 6.4],
        "target": ["A", "B", "A", "B", "A", "B", "A", "B", "A", "B"],
        "_row_id": range(1, 11)
    })
    
    mapping = ColumnMapping(feature_columns=["f1", "f2"], label_column="target")
    request = JobRequest(
        workbook_id="w1",
        sheet_name="s1",
        mapping=mapping,
        run_ml=True,
        run_cleansing=True,
        run_feature_selection=False
    )
    
    snapshot = build_boundary_snapshot(
        job_id="job-123",
        source_df=df,
        result_df=df,
        request=request,
        grid_resolution=10
    )
    
    assert snapshot.job_id == "job-123"
    assert len(snapshot.points) == 10
    assert len(snapshot.grid) == 100 # 10x10
    assert "accuracy" not in snapshot.statistics # it's not in stats but statistics has point_count
    assert snapshot.statistics["point_count"] == 10


def test_build_boundary_snapshot_accepts_model_workflow_request_without_run_cleansing():
    df = pd.DataFrame({
        "f1": [1.0, 2.0, 1.1, 2.1],
        "f2": [5.0, 6.0, 5.1, 6.1],
        "target": ["A", "B", "A", "B"],
        "_predicted_class": ["A", "B", "A", "B"],
        "_row_id": [1, 2, 3, 4],
    })

    request = ModelWorkflowRequest.model_validate({
        "workbook_id": "w1",
        "sheet_name": "s1",
        "source_job_id": "job-1",
        "use_case": "classification",
        "mapping": {"feature_columns": ["f1", "f2"], "label_column": "target", "id_column": "id"},
        "algorithm": "random_forest",
        "params": {},
        "preprocessing": {
            "handle_missing": "mean",
            "normalization": "minmax",
            "outlier_removal": False,
            "categorical_encoding": "label",
            "calculate_importance": True,
            "feature_selection_threshold": 0.01,
        },
    })

    snapshot = build_boundary_snapshot(
        job_id="wf-123",
        source_df=df,
        result_df=df,
        request=request,
        grid_resolution=5,
    )

    assert snapshot.job_id == "wf-123"
    assert len(snapshot.points) == 4


def test_build_boundary_snapshot_clustering_mode():
    df = pd.DataFrame({
        "f1": [1.0, 1.1, 5.0, 5.2],
        "f2": [2.0, 2.1, 8.0, 8.2],
        "_cluster_id": ["cluster_0", "cluster_0", "cluster_1", "cluster_1"],
        "_is_noise": [False, False, False, False],
        "_is_small_cluster": [False, False, False, False],
        "_row_id": [1, 2, 3, 4],
    })

    request = ModelWorkflowRequest.model_validate({
        "workbook_id": "w1",
        "sheet_name": "s1",
        "source_job_id": "job-1",
        "use_case": "clustering",
        "mapping": {"feature_columns": ["f1", "f2"], "label_column": None, "id_column": "id"},
        "algorithm": "kmeans",
        "params": {},
        "preprocessing": {
            "handle_missing": "mean",
            "normalization": "minmax",
            "outlier_removal": False,
            "categorical_encoding": "label",
            "calculate_importance": True,
            "feature_selection_threshold": 0.01,
        },
    })

    snapshot = build_boundary_snapshot(
        job_id="wf-cluster",
        source_df=df,
        result_df=df,
        request=request,
        grid_resolution=6,
    )

    assert snapshot.job_id == "wf-cluster"
    assert snapshot.statistics["graph_kind"] == "clustering"
    assert len(snapshot.class_labels) >= 2
    assert len(snapshot.points) == 4
