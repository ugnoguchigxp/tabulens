from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.routers.explorations.resolve_workbook_path")
@patch("app.routers.explorations.load_workbook_sheet")
def test_run_exploration_success(mock_load_sheet, mock_resolve_path):
    mock_resolve_path.return_value = "/tmp/sample.csv"
    mock_load_sheet.return_value = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5, 6],
            "f1": [0.1, 0.2, 0.4, 0.3, 0.9, 0.8],
            "f2": [1, 1, 0, 0, 1, 0],
            "target": ["A", "A", "B", "B", "A", "B"],
        }
    )

    payload = {
        "workbook_id": "wb-1",
        "sheet_name": "Sheet1",
        "mapping": {
            "id_column": "id",
            "label_column": "target",
            "feature_columns": ["f1", "f2"],
        },
        "task_type": "classification",
    }
    response = client.post("/api/explorations/run", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["workbook_id"] == "wb-1"
    assert body["target_feasibility"]["target_kind"] == "classification"
    assert len(body["model_sweep"]["items"]) == 4
    assert "evaluation" in body
    assert body["evaluation"]["overall_verdict"] in {
        "try_more",
        "usable_signal",
        "needs_better_features",
        "needs_better_target",
        "not_enough_data",
    }
    assert 0.0 <= body["evaluation"]["confidence"] <= 1.0
    assert isinstance(body["evaluation"]["risk_flags"], list)
    assert isinstance(body["evaluation"]["next_actions"], list)
    assert "decision" in body["evaluation"]
    assert body["evaluation"]["decision"]["recommended_path"] in {
        "run_workflow",
        "adjust_features",
        "change_target",
        "collect_more_data",
        "inspect_data_quality",
        "use_baseline",
    }


@patch("app.routers.explorations.resolve_workbook_path")
@patch("app.routers.explorations.load_workbook_sheet")
def test_run_exploration_without_label_returns_unknown_evaluation(mock_load_sheet, mock_resolve_path):
    mock_resolve_path.return_value = "/tmp/sample.csv"
    mock_load_sheet.return_value = pd.DataFrame(
        {
            "f1": [0.1, 0.2, 0.4, 0.3],
            "f2": [1, 1, 0, 0],
        }
    )

    payload = {
        "workbook_id": "wb-2",
        "sheet_name": "Sheet1",
        "mapping": {
            "feature_columns": ["f1", "f2"],
        },
        "task_type": "auto",
    }
    response = client.post("/api/explorations/run", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["target_feasibility"]["target_kind"] == "unknown"
    assert body["evaluation"]["signal_strength"] == "unknown"
    assert body["evaluation"]["overall_verdict"] == "needs_better_target"
    assert body["evaluation"]["decision"]["recommended_path"] == "change_target"
    assert "label_column_missing" in body["evaluation"]["risk_flags"]


@patch("app.routers.explorations.resolve_workbook_path")
@patch("app.routers.explorations.load_workbook_sheet")
def test_run_exploration_risky_columns_are_in_next_actions(mock_load_sheet, mock_resolve_path):
    mock_resolve_path.return_value = "/tmp/sample.csv"
    mock_load_sheet.return_value = pd.DataFrame(
        {
            "f1": [1, None, None, None, None],
            "f2": [0, 1, 0, 1, 0],
            "target": ["A", "B", "A", "B", "A"],
        }
    )

    payload = {
        "workbook_id": "wb-3",
        "sheet_name": "Sheet1",
        "mapping": {
            "label_column": "target",
            "feature_columns": ["f1", "f2"],
        },
        "task_type": "classification",
    }
    response = client.post("/api/explorations/run", json=payload)
    assert response.status_code == 200
    body = response.json()
    actions = body["evaluation"]["next_actions"]
    exclude_action = next((item for item in actions if item["action"] == "exclude_risky_columns"), None)
    assert exclude_action is not None
    assert "f1" in exclude_action["affected_columns"]


@patch("app.routers.explorations.resolve_workbook_path")
def test_run_exploration_workbook_not_found(mock_resolve_path):
    mock_resolve_path.return_value = None
    payload = {
        "workbook_id": "missing",
        "sheet_name": "Sheet1",
        "mapping": {"feature_columns": []},
    }
    response = client.post("/api/explorations/run", json=payload)
    assert response.status_code == 404
    assert "Workbook not found" in response.json()["error"]["message"]
