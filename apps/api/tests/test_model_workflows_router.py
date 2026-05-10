import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, MagicMock
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
def test_run_workflow_success(mock_save_export, mock_save_state, mock_save_artifacts, mock_run, mock_load_source):
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
        model_artifacts=None
    )
    
    mock_save_artifacts.return_value = (MagicMock(), MagicMock())
    
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
