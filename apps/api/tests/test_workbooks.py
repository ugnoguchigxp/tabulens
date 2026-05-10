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

def test_upload_invalid_file():
    response = client.post(
        "/api/workbooks/upload",
        files={"file": ("test.txt", b"hello", "text/plain")}
    )
    assert response.status_code == 400
    assert "Only .xlsx and .csv files are supported" in response.json()["error"]["message"]
