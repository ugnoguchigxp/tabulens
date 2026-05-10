import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, MagicMock
import pandas as pd
from app.models.schemas import JobResponse

client = TestClient(app)

@patch("app.routers.jobs.run_analysis")
@patch("app.routers.jobs.review_job")
@patch("app.routers.jobs.save_result_artifacts")
@patch("app.routers.jobs._resolve_workbook_path")
@patch("app.routers.jobs._load_source_df")
def test_create_job(mock_load_source, mock_resolve, mock_save_artifacts, mock_review, mock_run_analysis):
    mock_resolve.return_value = MagicMock()
    mock_load_source.return_value = pd.DataFrame({"a": [1]})
    mock_run_analysis.return_value = (pd.DataFrame({"a": [1]}), {"meta": "data"})
    mock_save_artifacts.return_value = (MagicMock(), MagicMock())
    
    from app.models.schemas import ReviewResult
    mock_review.return_value = ReviewResult(assessment="keep", recommended_actions=[])

    response = client.post(
        "/api/jobs/run",
        json={
            "workbook_id": "w1",
            "sheet_name": "s1",
            "mapping": {"feature_columns": ["a"], "label_column": "b", "id_column": "id"},
            "algorithm": "random_forest"
        }
    )
    
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "completed"

def test_get_job_not_found():
    response = client.get("/api/jobs/non-existent")
    assert response.status_code == 404
