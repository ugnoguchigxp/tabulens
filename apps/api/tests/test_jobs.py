import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, MagicMock
import pandas as pd
from app.models.schemas import JobResponse

client = TestClient(app)

@patch("app.routers.jobs.run_analysis")
@patch("app.routers.jobs.save_result_artifacts")
@patch("app.routers.jobs._resolve_workbook_path")
@patch("app.routers.jobs._load_source_df")
def test_create_job(mock_load_source, mock_resolve, mock_save_artifacts, mock_run_analysis):
    mock_resolve.return_value = MagicMock()
    mock_load_source.return_value = pd.DataFrame({"a": [1]})
    mock_run_analysis.return_value = (pd.DataFrame({"a": [1]}), {"meta": "data"})
    mock_save_artifacts.return_value = (MagicMock(), MagicMock())

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


@patch("app.routers.jobs.run_analysis")
@patch("app.routers.jobs.save_result_artifacts")
@patch("app.routers.jobs._resolve_workbook_path")
@patch("app.routers.jobs._load_source_df")
def test_create_job_with_nan_metadata_is_json_safe(mock_load_source, mock_resolve, mock_save_artifacts, mock_run_analysis):
    mock_resolve.return_value = MagicMock()
    mock_load_source.return_value = pd.DataFrame({"a": [1]})
    mock_run_analysis.return_value = (pd.DataFrame({"a": [1]}), {"feature_importance": {"a": float("nan")}})
    mock_save_artifacts.return_value = (MagicMock(), MagicMock())

    response = client.post(
        "/api/jobs/run",
        json={
            "workbook_id": "w1",
            "sheet_name": "s1",
            "mapping": {"feature_columns": ["a"], "label_column": "b", "id_column": "id"},
            "algorithm": "random_forest"
        }
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["feature_importance"]["a"] is None


def test_prepare_rows_reflect_preprocessing_values():
    df = pd.DataFrame({
        "f1": [1.0, None, 3.0],
        "f2": [10.0, 20.0, None],
        "target": ["A", "B", "A"],
    })
    csv_content = df.to_csv(index=False).encode()

    upload_response = client.post(
        "/api/workbooks/upload",
        files={"file": ("prep.csv", csv_content, "text/csv")},
    )
    assert upload_response.status_code == 200
    workbook_id = upload_response.json()["workbook_id"]
    sheet_name = upload_response.json()["sheets"][0]["name"]

    run_response = client.post(
        "/api/jobs/run",
        json={
            "workbook_id": workbook_id,
            "sheet_name": sheet_name,
            "mapping": {"feature_columns": ["f1", "f2"], "label_column": "target", "id_column": ""},
            "algorithm": "random_forest",
            "preprocessing": {
                "handle_missing": "mean",
                "normalization": "minmax",
                "outlier_removal": False,
                "categorical_encoding": "label",
                "calculate_importance": True,
                "feature_selection_threshold": 0.01,
            },
            "run_cleansing": True,
            "run_feature_selection": False,
            "run_ml": False,
        },
    )
    assert run_response.status_code == 200
    job_id = run_response.json()["job_id"]

    rows_response = client.get(f"/api/jobs/{job_id}/rows")
    assert rows_response.status_code == 200
    rows = rows_response.json()
    assert len(rows) == 3
    assert all(row["f1"] is not None for row in rows)
    assert all(row["f2"] is not None for row in rows)
    assert min(row["f1"] for row in rows) >= 0.0
    assert max(row["f1"] for row in rows) <= 1.0
    assert min(row["f2"] for row in rows) >= 0.0
    assert max(row["f2"] for row in rows) <= 1.0


@patch("app.routers.jobs.build_boundary_snapshot")
@patch("app.routers.jobs._read_dataframe")
@patch("app.routers.jobs._resolve_result_path")
@patch("app.routers.jobs._load_source_df")
@patch("app.routers.jobs._get_job_state")
def test_get_job_boundary_success(mock_get_state, mock_load_source, mock_resolve, mock_read_df, mock_build_boundary):
    mock_get_state.return_value = {
        "job_id": "job-1",
        "sheet_name": "s1",
        "source_path": "/tmp/source.csv",
        "request": {
            "workbook_id": "w1",
            "sheet_name": "s1",
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
            "run_cleansing": True,
            "run_feature_selection": False,
            "run_ml": True,
        },
    }
    mock_load_source.return_value = pd.DataFrame({"f1": [1], "f2": [2], "target": ["A"]})
    mock_resolve.return_value = MagicMock()
    mock_read_df.return_value = pd.DataFrame({"f1": [1], "f2": [2], "_predicted_class": ["A"]})
    mock_build_boundary.return_value = {
        "job_id": "job-1",
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

    response = client.get("/api/jobs/job-1/boundary")
    assert response.status_code == 200
    mock_build_boundary.assert_called_once()
    assert mock_build_boundary.call_args.kwargs["job_id"] == "job-1"


@patch("app.routers.jobs.build_boundary_snapshot")
@patch("app.routers.jobs._read_dataframe")
@patch("app.routers.jobs._resolve_result_path")
@patch("app.routers.jobs._load_source_df")
@patch("app.routers.jobs._get_job_state")
def test_get_job_boundary_value_error_maps_to_400(mock_get_state, mock_load_source, mock_resolve, mock_read_df, mock_build_boundary):
    mock_get_state.return_value = {
        "job_id": "job-1",
        "sheet_name": "s1",
        "source_path": "/tmp/source.csv",
        "request": {
            "workbook_id": "w1",
            "sheet_name": "s1",
            "mapping": {"feature_columns": ["f1"], "label_column": "target", "id_column": "id"},
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
            "run_cleansing": True,
            "run_feature_selection": False,
            "run_ml": True,
        },
    }
    mock_load_source.return_value = pd.DataFrame({"f1": [1], "target": ["A"]})
    mock_resolve.return_value = MagicMock()
    mock_read_df.return_value = pd.DataFrame({"f1": [1], "_predicted_class": ["A"]})
    mock_build_boundary.side_effect = ValueError("Boundary explorer requires at least two feature columns")

    response = client.get("/api/jobs/job-1/boundary")
    assert response.status_code == 400
    assert "at least two feature columns" in response.json()["error"]["message"]
