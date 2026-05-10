import pytest
import pandas as pd
from pathlib import Path
from app.services.workbook_loader import load_workbook_sheet, resolve_workbook_path
from app.core.paths import UPLOAD_DIR

def test_resolve_workbook_path(tmp_path):
    # Mock UPLOAD_DIR
    import app.services.workbook_loader as wl
    original_dir = wl.UPLOAD_DIR
    wl.UPLOAD_DIR = tmp_path
    try:
        workbook_id = "test-id"
        file_path = tmp_path / f"{workbook_id}.csv"
        file_path.write_text("a,b\n1,2")
        
        resolved = wl.resolve_workbook_path(workbook_id)
        assert resolved == file_path
        
        assert wl.resolve_workbook_path("non-existent") is None
    finally:
        wl.UPLOAD_DIR = original_dir

def test_load_workbook_sheet_csv(tmp_path):
    file_path = tmp_path / "test.csv"
    file_path.write_text("a,b\n1,2")
    df = load_workbook_sheet(file_path, "any")
    assert len(df) == 1
    assert list(df.columns) == ["a", "b"]
