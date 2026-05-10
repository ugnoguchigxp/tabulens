from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.paths import UPLOAD_DIR


def resolve_workbook_path(workbook_id: str) -> Path | None:
    for ext in [".xlsx", ".csv"]:
        file_path = UPLOAD_DIR / f"{workbook_id}{ext}"
        if file_path.exists():
            return file_path
    return None


def load_workbook_sheet(file_path: Path, sheet_name: str) -> pd.DataFrame:
    if str(file_path).endswith(".xlsx"):
        return pd.read_excel(file_path, sheet_name=sheet_name)
    return pd.read_csv(file_path)
