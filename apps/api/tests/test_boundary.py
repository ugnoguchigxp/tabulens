import pytest
import pandas as pd
import numpy as np
from app.services.ml.boundary import build_boundary_snapshot
from app.models.schemas import JobRequest, ColumnMapping, PreprocessingSettings

def test_build_boundary_snapshot_basic():
    df = pd.DataFrame({
        "f1": [1.0, 2.0, 1.1, 2.1, 1.2, 2.2, 1.3, 2.3, 1.4, 2.4],
        "f2": [5.0, 6.0, 5.1, 6.1, 5.2, 6.2, 5.3, 6.3, 5.4, 6.4],
        "target": ["A", "B", "A", "B", "A", "B", "A", "B", "A", "B"],
        "_row_id": range(1, 11)
    })
    
    mapping = ColumnMapping(feature_columns=["f1", "f2"], label_column="target")
    request = JobRequest(
        workbook_id="w1",
        sheet_name="s1",
        mapping=mapping,
        run_ml=True,
        run_cleansing=True,
        run_feature_selection=False
    )
    
    snapshot = build_boundary_snapshot(
        job_id="job-123",
        source_df=df,
        result_df=df,
        request=request,
        grid_resolution=10
    )
    
    assert snapshot.job_id == "job-123"
    assert len(snapshot.points) == 10
    assert len(snapshot.grid) == 100 # 10x10
    assert "accuracy" not in snapshot.statistics # it's not in stats but statistics has point_count
    assert snapshot.statistics["point_count"] == 10
