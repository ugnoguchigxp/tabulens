import pytest
import pandas as pd
import numpy as np
from app.services.analysis_review import build_review_summary, _to_jsonable
from app.models.schemas import JobRequest, ColumnMapping

def test_to_jsonable():
    assert _to_jsonable(np.nan) is None
    assert _to_jsonable(np.inf) is None
    assert _to_jsonable(np.int64(42)) == 42
    assert _to_jsonable({"a": 1}) == {"a": 1}

def test_build_review_summary():
    mapping = ColumnMapping(feature_columns=["f1"], label_column="target", id_column="id")
    request = JobRequest(
        workbook_id="w1",
        sheet_name="s1",
        mapping=mapping,
        algorithm="random_forest"
    )
    
    source_df = pd.DataFrame({
        "id": [1, 2],
        "f1": [1.0, np.nan],
        "target": ["A", "B"]
    })
    
    result_df = source_df.copy()
    result_df["_prediction_confidence"] = [0.9, 0.8]
    result_df["_row_id"] = [1, 2]
    
    metadata = {"feature_importance": {"f1": 1.0}}
    
    summary = build_review_summary(
        job_id="j1",
        workbook_id="w1",
        sheet_name="s1",
        request=request,
        source_df=source_df,
        result_df=result_df,
        metadata=metadata
    )
    
    assert summary.job_id == "j1"
    assert summary.row_count == 2
    assert summary.feature_count == 1
    assert summary.missing_rate == 0.5
    assert summary.prediction_confidence.mean == pytest.approx(0.85)
