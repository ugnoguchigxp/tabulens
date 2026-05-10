from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.paths import RESULT_DIR

EXPLORATION_DIR = RESULT_DIR / "_explorations"
EXPLORATION_DIR.mkdir(parents=True, exist_ok=True)


def _exploration_path(workbook_id: str, sheet_name: str) -> Path:
    safe_sheet = sheet_name.replace("/", "_")
    return EXPLORATION_DIR / f"{workbook_id}__{safe_sheet}.json"


def save_exploration_result(workbook_id: str, sheet_name: str, payload: dict[str, Any]) -> Path:
    path = _exploration_path(workbook_id, sheet_name)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_exploration_result(workbook_id: str, sheet_name: str) -> dict[str, Any] | None:
    path = _exploration_path(workbook_id, sheet_name)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
