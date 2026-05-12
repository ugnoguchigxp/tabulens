import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd
from app.models.schemas import ModelWorkflowRequest, UseCaseType

client = TestClient(app)

def test_run_workflow_error_no_source():
    response = client.post("/api/model-workflows/run", json={
        "workbook_id": "w1",
        "sheet_name": "s1",
        "use_case": "classification",
        "mapping": {"feature_columns": ["f1"], "label_column": "target", "id_column": "id"},
        "algorithm": "random_forest",
        "params": {},
        "preprocessing": {
            "handle_missing": "mean",
            "normalization": "minmax",
            "outlier_removal": False,
            "categorical_encoding": "label",
            "calculate_importance": False,
            "feature_selection_threshold": 0.05
        }
    })
    assert response.status_code == 400
    # Custom error handler wraps details in error.message
    data = response.json()
    assert "requires a completed Prepare job" in data["error"]["message"]

@patch("app.routers.model_workflows._load_workflow_source")
@patch("app.routers.model_workflows.run_model_workflow")
@patch("app.routers.model_workflows.save_result_artifacts")
@patch("app.routers.model_workflows.save_job_state")
@patch("app.routers.model_workflows._save_workflow_export")
@patch("app.routers.model_workflows.save_model_artifacts")
def test_run_workflow_success(mock_save_model_artifacts, mock_save_export, mock_save_state, mock_save_artifacts, mock_run, mock_load_source):
    # Setup mocks
    mock_request = MagicMock(spec=ModelWorkflowRequest)
    mock_request.use_case = UseCaseType.CLASSIFICATION
    mock_request.workbook_id = "w1"
    mock_request.sheet_name = "s1"
    mock_request.source_job_id = "prep-123"
    mock_request.model_dump.return_value = {}
    
    mock_load_source.return_value = (
        pd.DataFrame({"f1": [1, 2], "target": ["A", "B"], "id": [0, 1]}),
        {"source_kind": "prepare_job"},
        mock_request
    )
    
    mock_run.return_value = MagicMock(
        result_df=pd.DataFrame({"f1": [1, 2], "_predicted_class": ["A", "B"]}),
        metrics={"accuracy": 1.0},
        metadata={"some": "meta"},
        model_artifacts={"model": "stub"}
    )
    
    mock_save_artifacts.return_value = (MagicMock(), MagicMock())
    mock_save_model_artifacts.return_value = "artifact.joblib"
    
    payload = {
        "workbook_id": "w1",
        "sheet_name": "s1",
        "source_job_id": "prep-123",
        "use_case": "classification",
        "mapping": {"feature_columns": ["f1"], "label_column": "target", "id_column": "id"},
        "algorithm": "random_forest",
        "params": {},
        "preprocessing": {
            "handle_missing": "mean",
            "normalization": "minmax",
            "outlier_removal": False,
            "categorical_encoding": "label",
            "calculate_importance": False,
            "feature_selection_threshold": 0.05
        }
    }
    
    response = client.post("/api/model-workflows/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    mock_save_model_artifacts.assert_called_once()

@patch("app.routers.model_workflows._get_workflow_state")
@patch("app.routers.model_workflows._read_dataframe")
@patch("app.routers.model_workflows._resolve_result_path")
def test_get_workflow_success(mock_resolve, mock_read_df, mock_get_state):
    mock_get_state.return_value = {
        "workflow_id": "wf-123",
        "status": "completed",
        "use_case": "classification",
        "metrics": {"accuracy": 0.9}
    }
    mock_read_df.return_value = pd.DataFrame({"f1": [1], "_predicted_class": ["A"]})
    
    response = client.get("/api/model-workflows/wf-123")
    assert response.status_code == 200
    assert response.json()["metrics"]["values"]["accuracy"] == 0.9


@patch("app.routers.model_workflows._get_workflow_state")
@patch("app.routers.model_workflows.load_model_artifacts")
def test_predict_workflow_success(mock_load_artifacts, mock_get_state):
    mock_get_state.return_value = {"workflow_id": "wf-123", "workbook_id": "w1"}
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array(["A", "B"])
    mock_model.predict_proba.return_value = np.array([[0.9, 0.1], [0.2, 0.8]])
    mock_preprocessor = MagicMock()
    mock_preprocessor.transform.return_value = np.array([[1.0], [2.0]])
    mock_load_artifacts.return_value = {
        "model": mock_model,
        "preprocessor": mock_preprocessor,
        "feature_columns": ["f1"],
        "task_type": "classification",
        "algorithm": "random_forest",
    }

    response = client.post("/api/model-workflows/wf-123/predict", json={"rows": [{"f1": 1.0}, {"f1": 2.0}]})
    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == "wf-123"
    assert len(body["predictions"]) == 2
    assert body["predictions"][0]["value"] == "A"
    assert body["predictions"][0]["confidence"] == 0.9


@patch("app.routers.model_workflows._get_workflow_state")
@patch("app.routers.model_workflows.load_model_artifacts")
def test_predict_workflow_feature_mismatch(mock_load_artifacts, mock_get_state):
    mock_get_state.return_value = {"workflow_id": "wf-123", "workbook_id": "w1"}
    mock_load_artifacts.return_value = {
        "model": MagicMock(),
        "preprocessor": MagicMock(),
        "feature_columns": ["f1", "f2"],
    }
    response = client.post("/api/model-workflows/wf-123/predict", json={"rows": [{"f1": 1.0}]})
    assert response.status_code == 400
    assert "Feature columns mismatch" in response.json()["error"]["message"]


@patch("app.routers.model_workflows._get_workflow_state")
@patch("app.routers.model_workflows.load_model_artifacts")
def test_predict_workflow_artifact_missing(mock_load_artifacts, mock_get_state):
    mock_get_state.return_value = {"workflow_id": "wf-123", "workbook_id": "w1"}
    mock_load_artifacts.return_value = None
    response = client.post("/api/model-workflows/wf-123/predict", json={"rows": [{"f1": 1.0}]})
    assert response.status_code == 409
    assert "Model artifacts are not available" in response.json()["error"]["message"]


@patch("app.routers.model_workflows.build_boundary_snapshot")
@patch("app.routers.model_workflows._read_dataframe")
@patch("app.routers.model_workflows._resolve_result_path")
@patch("app.routers.model_workflows._load_workflow_source")
@patch("app.routers.model_workflows._get_workflow_state")
def test_get_workflow_boundary_success(mock_get_state, mock_load_source, mock_resolve, mock_read_df, mock_build_boundary):
    mock_get_state.return_value = {
        "workflow_id": "wf-123",
        "request": {
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
        },
    }
    resolved_request = ModelWorkflowRequest.model_validate(mock_get_state.return_value["request"])
    mock_load_source.return_value = (pd.DataFrame({"f1": [1], "f2": [2], "target": ["A"]}), {}, resolved_request)
    mock_resolve.return_value = MagicMock()
    mock_read_df.return_value = pd.DataFrame({"f1": [1], "f2": [2], "_predicted_class": ["A"]})
    mock_build_boundary.return_value = {
        "job_id": "wf-123",
        "projection": "pca",
        "x_axis": {"label": "PCA 1", "minimum": 0, "maximum": 1},
        "y_axis": {"label": "PCA 2", "minimum": 0, "maximum": 1},
        "grid_resolution": 2,
        "grid_step_x": 1,
        "grid_step_y": 1,
        "class_labels": ["A"],
        "explained_variance_ratio": [1.0, 0.0],
        "points": [],
        "grid": [],
        "statistics": {},
    }

    response = client.get("/api/model-workflows/wf-123/boundary")
    assert response.status_code == 200
    mock_build_boundary.assert_called_once()
    assert mock_build_boundary.call_args.kwargs["job_id"] == "wf-123"


@patch("app.routers.model_workflows.build_boundary_snapshot")
@patch("app.routers.model_workflows._read_dataframe")
@patch("app.routers.model_workflows._resolve_result_path")
@patch("app.routers.model_workflows._load_workflow_source")
@patch("app.routers.model_workflows._get_workflow_state")
def test_get_workflow_boundary_value_error_maps_to_400(mock_get_state, mock_load_source, mock_resolve, mock_read_df, mock_build_boundary):
    mock_get_state.return_value = {
        "workflow_id": "wf-123",
        "request": {
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
        },
    }
    resolved_request = ModelWorkflowRequest.model_validate(mock_get_state.return_value["request"])
    mock_load_source.return_value = (pd.DataFrame({"f1": [1], "f2": [2], "target": ["A"]}), {}, resolved_request)
    mock_resolve.return_value = MagicMock()
    mock_read_df.return_value = pd.DataFrame({"f1": [1], "f2": [2], "_predicted_class": ["A"]})
    mock_build_boundary.side_effect = ValueError("Boundary explorer requires at least two classes")

    response = client.get("/api/model-workflows/wf-123/boundary")
    assert response.status_code == 400
    assert "at least two classes" in response.json()["error"]["message"]


@patch("app.routers.model_workflows.build_boundary_snapshot")
@patch("app.routers.model_workflows._read_dataframe")
@patch("app.routers.model_workflows._resolve_result_path")
@patch("app.routers.model_workflows._load_workflow_source")
@patch("app.routers.model_workflows._get_workflow_state")
def test_get_workflow_boundary_allows_clustering(mock_get_state, mock_load_source, mock_resolve, mock_read_df, mock_build_boundary):
    mock_get_state.return_value = {
        "workflow_id": "wf-cluster",
        "request": {
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
        },
    }
    resolved_request = ModelWorkflowRequest.model_validate(mock_get_state.return_value["request"])
    mock_load_source.return_value = (pd.DataFrame({"f1": [1], "f2": [2]}), {}, resolved_request)
    mock_resolve.return_value = MagicMock()
    mock_read_df.return_value = pd.DataFrame({"f1": [1], "f2": [2], "_cluster_id": ["cluster_0"]})
    mock_build_boundary.return_value = {
        "job_id": "wf-cluster",
        "projection": "pca",
        "x_axis": {"label": "PCA 1", "minimum": 0, "maximum": 1},
        "y_axis": {"label": "PCA 2", "minimum": 0, "maximum": 1},
        "grid_resolution": 2,
        "grid_step_x": 1,
        "grid_step_y": 1,
        "class_labels": ["cluster_0"],
        "explained_variance_ratio": [1.0, 0.0],
        "points": [],
        "grid": [],
        "statistics": {"graph_kind": "clustering"},
    }

    response = client.get("/api/model-workflows/wf-cluster/boundary")
    assert response.status_code == 200
    mock_build_boundary.assert_called_once()


@patch("app.routers.model_workflows._get_workflow_state")
def test_get_workflow_boundary_rejects_non_supported_use_case(mock_get_state):
    mock_get_state.return_value = {
        "workflow_id": "wf-unsupported",
        "request": {
            "workbook_id": "w1",
            "sheet_name": "s1",
            "source_job_id": "job-1",
            "use_case": "prediction",
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
        },
    }

    response = client.get("/api/model-workflows/wf-unsupported/boundary")
    assert response.status_code == 400
    assert "classification or clustering" in response.json()["error"]["message"]
