from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.paths import UPLOAD_DIR


def workbook_formula_metadata_path(workbook_id: str) -> Path:
    return UPLOAD_DIR / f"{workbook_id}.formulas.json"


def save_workbook_formula_metadata(workbook_id: str, metadata: dict[str, Any]) -> Path:
    path = workbook_formula_metadata_path(workbook_id)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def load_workbook_formula_metadata(workbook_id: str) -> dict[str, Any] | None:
    path = workbook_formula_metadata_path(workbook_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
