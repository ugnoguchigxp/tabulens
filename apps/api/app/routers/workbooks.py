import os
import uuid
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models.schemas import WorkbookUploadResponse, SheetInfo, ColumnInfo
from app.core.paths import UPLOAD_DIR

router = APIRouter()

@router.post("/upload", response_model=WorkbookUploadResponse)
async def upload_workbook(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".xlsx", ".csv"]:
        raise HTTPException(status_code=400, detail="Only .xlsx and .csv files are supported")
    
    workbook_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{workbook_id}{ext}"
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    try:
        sheets_info = []
        
        if ext == ".xlsx":
            excel_file = pd.ExcelFile(file_path)
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                sheets_info.append(_process_dataframe(df, sheet_name))
        else:
            # Handle CSV as a single sheet
            df = pd.read_csv(file_path)
            sheets_info.append(_process_dataframe(df, "CSV Data"))
            
        return WorkbookUploadResponse(
            workbook_id=workbook_id,
            sheets=sheets_info
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.get("/{workbook_id}", response_model=WorkbookUploadResponse)
async def get_workbook(workbook_id: str):
    for ext in [".xlsx", ".csv"]:
        file_path = UPLOAD_DIR / f"{workbook_id}{ext}"
        if file_path.exists():
            try:
                return _load_workbook(file_path, workbook_id)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Error reading workbook: {exc}") from exc
    raise HTTPException(status_code=404, detail="Workbook not found")


@router.get("/{workbook_id}/sheets/{sheet_name}/preview")
async def preview_sheet(workbook_id: str, sheet_name: str):
    for ext in [".xlsx", ".csv"]:
        file_path = UPLOAD_DIR / f"{workbook_id}{ext}"
        if not file_path.exists():
            continue
        try:
            if ext == ".xlsx":
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                if sheet_name not in {"CSV Data", "Sheet1"}:
                    continue
                df = pd.read_csv(file_path)
            preview_df = df.head(10).fillna("")
            return {
                "workbook_id": workbook_id,
                "sheet_name": sheet_name,
                "preview_rows": preview_df.to_dict(orient="records"),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error creating preview: {exc}") from exc
    raise HTTPException(status_code=404, detail="Workbook not found")

def _process_dataframe(df: pd.DataFrame, sheet_name: str) -> SheetInfo:
    columns = []
    for col in df.columns:
        inferred_type = str(df[col].dtype)
        missing_count = int(df[col].isna().sum())
        columns.append(ColumnInfo(
            name=str(col),
            inferred_type=inferred_type,
            missing_count=missing_count
        ))

    display_df = df.fillna("")
    rows = display_df.to_dict(orient="records")
    preview_rows = rows[:10]
    
    return SheetInfo(
        name=sheet_name,
        row_count=len(df),
        columns=columns,
        rows=rows,
        preview_rows=preview_rows
    )


def _load_workbook(file_path, workbook_id: str) -> WorkbookUploadResponse:
    sheets_info = []
    if str(file_path).endswith(".xlsx"):
        excel_file = pd.ExcelFile(file_path)
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            sheets_info.append(_process_dataframe(df, sheet_name))
    else:
        df = pd.read_csv(file_path)
        sheets_info.append(_process_dataframe(df, "CSV Data"))
    return WorkbookUploadResponse(workbook_id=workbook_id, sheets=sheets_info)
