import pytest
from fastapi.testclient import TestClient
from app.main import app
import io
import pandas as pd

client = TestClient(app)

def test_upload_csv():
    # Create a dummy CSV
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    csv_content = df.to_csv(index=False).encode()
    
    response = client.post(
        "/api/workbooks/upload",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "workbook_id" in data
    assert len(data["sheets"]) == 1
    assert data["sheets"][0]["name"] == "CSV Data"
    assert data["sheets"][0]["row_count"] == 2
    assert "rows" not in data["sheets"][0]


def test_sheet_rows_and_profile():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [3, None, 4]})
    csv_content = df.to_csv(index=False).encode()
    upload_response = client.post(
        "/api/workbooks/upload",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )
    assert upload_response.status_code == 200
    workbook_id = upload_response.json()["workbook_id"]

    rows_response = client.get(f"/api/workbooks/{workbook_id}/sheets/CSV Data/rows?offset=1&limit=1")
    assert rows_response.status_code == 200
    rows_body = rows_response.json()
    assert rows_body["offset"] == 1
    assert rows_body["limit"] == 1
    assert rows_body["row_count"] == 3
    assert len(rows_body["rows"]) == 1

    profile_response = client.get(f"/api/workbooks/{workbook_id}/sheets/CSV Data/profile")
    assert profile_response.status_code == 200
    profile_body = profile_response.json()
    assert profile_body["row_count"] == 3
    assert profile_body["column_count"] == 2
    assert "missing_rate_overall" in profile_body


def test_sheet_rows_sheet_not_found_for_xlsx():
    excel_buffer = io.BytesIO()
    pd.DataFrame({"a": [1, 2]}).to_excel(excel_buffer, sheet_name="Data", index=False)
    excel_buffer.seek(0)

    upload_response = client.post(
        "/api/workbooks/upload",
        files={"file": ("test.xlsx", excel_buffer.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert upload_response.status_code == 200
    workbook_id = upload_response.json()["workbook_id"]

    rows_response = client.get(f"/api/workbooks/{workbook_id}/sheets/Unknown/rows")
    assert rows_response.status_code == 404
    assert "Sheet not found" in rows_response.json()["error"]["message"]

def test_upload_invalid_file():
    response = client.post(
        "/api/workbooks/upload",
        files={"file": ("test.txt", b"hello", "text/plain")}
    )
    assert response.status_code == 400
    assert "Only .xlsx and .csv files are supported" in response.json()["error"]["message"]
