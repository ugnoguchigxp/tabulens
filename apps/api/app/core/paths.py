from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
API_DIR = APP_DIR.parent
PROJECT_DIR = API_DIR.parent.parent
STORAGE_DIR = PROJECT_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
RESULT_DIR = STORAGE_DIR / "results"

for directory in (UPLOAD_DIR, RESULT_DIR):
    directory.mkdir(parents=True, exist_ok=True)
