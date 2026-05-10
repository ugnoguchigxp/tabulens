from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.paths import RESULT_DIR


def job_directory(job_id: str) -> Path:
    path = RESULT_DIR / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def job_state_path(job_id: str) -> Path:
    return job_directory(job_id) / "state.json"


def job_artifact_path(job_id: str, name: str, suffix: str) -> Path:
    return job_directory(job_id) / f"{name}.{suffix}"


def save_job_state(state: dict[str, Any]) -> None:
    job_id = str(state["job_id"])
    job_state_path(job_id).write_text(
        json.dumps(_to_jsonable(state), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_job_state(job_id: str) -> dict[str, Any] | None:
    state_file = job_state_path(job_id)
    if state_file.exists():
        return json.loads(state_file.read_text(encoding="utf-8"))

    legacy_csv = RESULT_DIR / f"{job_id}.csv"
    legacy_xlsx = RESULT_DIR / f"{job_id}.xlsx"
    if legacy_csv.exists() or legacy_xlsx.exists():
        return {
            "job_id": job_id,
            "status": "completed",
            "result_path": str(legacy_csv if legacy_csv.exists() else legacy_xlsx),
            "result_xlsx_path": str(legacy_xlsx) if legacy_xlsx.exists() else None,
            "metadata": {},
        }
    return None


def save_result_artifacts(job_id: str, result_df: pd.DataFrame, name: str = "current") -> tuple[Path, Path]:
    csv_path = job_artifact_path(job_id, name, "csv")
    xlsx_path = job_artifact_path(job_id, name, "xlsx")
    result_df.to_csv(csv_path, index=False)
    result_df.to_excel(xlsx_path, index=False)
    return csv_path, xlsx_path


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        try:
            return _to_jsonable(value.model_dump(mode="json"))
        except TypeError:
            return _to_jsonable(value.model_dump())
    if hasattr(value, "value") and type(value).__name__ != "str":
        try:
            return value.value
        except Exception:
            return str(value)
    if isinstance(value, float) and not pd.notna(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
