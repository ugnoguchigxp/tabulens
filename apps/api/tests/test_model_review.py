import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from app.services.ml.model_review import (
    build_model_review_summary,
    review_model_workflow,
    _apply_single_proposal,
    ModelReviewActionType
)
from app.models.schemas import ModelWorkflowRequest, UseCaseType, ColumnMapping, ModelReviewSummary, ModelReviewAction

@pytest.fixture
def sample_result_df():
    return pd.DataFrame({
        "f1": [1, 2, 3, 4, 5],
        "target": ["A", "B", "A", "B", "A"],
        "_row_id": range(1, 6),
        "_predicted_class": ["A", "B", "B", "B", "A"],
        "_prediction_confidence": [0.9, 0.8, 0.4, 0.7, 0.9],
        "_error_flag": [False, False, True, False, False],
        "_split_role": ["train", "train", "test", "test", "test"]
    })

@pytest.fixture
def sample_request():
    return ModelWorkflowRequest(
        workbook_id="w1",
        sheet_name="s1",
        use_case=UseCaseType.CLASSIFICATION,
        algorithm="random_forest",
        mapping=ColumnMapping(feature_columns=["f1"], label_column="target")
    )

def test_build_model_review_summary_classification(sample_result_df, sample_request):
    metadata = {
        "metrics": {
            "accuracy": 0.8,
            "balanced_accuracy": 0.75,
            "train_count": 2,
            "test_count": 3
        },
        "feature_importance": {"f1": 1.0}
    }
    
    summary = build_model_review_summary(
        workflow_id="wf1",
        workbook_id="w1",
        sheet_name="s1",
        request=sample_request,
        result_df=sample_result_df,
        metadata=metadata
    )
    
    assert summary.workflow_id == "wf1"
    assert summary.use_case == UseCaseType.CLASSIFICATION
    assert summary.metrics["accuracy"] == 0.8
    assert "small_sample" in summary.quality_flags
    assert len(summary.feature_importance) == 1
    assert summary.feature_importance[0]["feature"] == "f1"

def test_apply_single_proposal_rebalance(sample_request):
    proposal = ModelReviewAction(
        action=ModelReviewActionType.REBALANCE_CLASSES,
        reason="imbalance detected",
        target="model"
    )
    
    next_request, df = _apply_single_proposal(
        current_request=sample_request,
        source_df=pd.DataFrame({"f1": [1, 2]}),
        current_result_df=pd.DataFrame({"f1": [1, 2]}),
        proposal=proposal
    )
    
    assert next_request.params["class_weight"] == "balanced"

@patch("app.services.ml.model_review.review_model_workflow_summary")
def test_review_model_workflow_success(mock_llm_review, sample_request, sample_result_df):
    summary = build_model_review_summary(
        workflow_id="wf1",
        workbook_id="w1",
        sheet_name="s1",
        request=sample_request,
        result_df=sample_result_df,
        metadata={}
    )
    
    mock_llm_review.return_value = {
        "assessment": "pass",
        "rationale": "Looks good",
        "recommended_actions": [
            {
                "action": "tune_hyperparameters",
                "reason": "slightly overfitting",
                "target": "params",
                "params": {"n_estimators": 200}
            }
        ]
    }
    
    result = review_model_workflow(summary=summary)
    
    assert result.assessment == "pass"
    assert len(result.recommended_actions) == 1
    assert result.recommended_actions[0].action == ModelReviewActionType.TUNE_HYPERPARAMETERS
    assert result.recommended_actions[0].params["n_estimators"] == 200

def test_build_model_review_summary_regression(sample_result_df):
    request = ModelWorkflowRequest(
        workbook_id="w1",
        sheet_name="s1",
        use_case=UseCaseType.PREDICTION,
        algorithm="random_forest",
        mapping=ColumnMapping(feature_columns=["f1"], label_column="target")
    )
    
    # Add regression-specific columns
    df = sample_result_df.copy()
    df["_actual_value"] = [1.0, 2.0, 3.0, 4.0, 5.0]
    df["_predicted_value"] = [1.1, 1.9, 3.5, 3.8, 5.2]
    df["_residual"] = df["_actual_value"] - df["_predicted_value"]
    df["_absolute_error"] = df["_residual"].abs()
    
    metadata = {
        "metrics": {
            "r2": 0.95,
            "mae": 0.2
        }
    }
    
    summary = build_model_review_summary(
        workflow_id="wf2",
        workbook_id="w1",
        sheet_name="s1",
        request=request,
        result_df=df,
        metadata=metadata
    )
    
    assert summary.use_case == UseCaseType.PREDICTION
    assert summary.metrics["r2"] == 0.95
    assert len(summary.sample_errors) > 0 # MAE exists

def test_feature_importance_normalization(sample_request, sample_result_df):
    metadata = {
        "feature_importance": {"f1": 0.8, "f2": 0.2, "f3": 0.5}
    }
    summary = build_model_review_summary(
        workflow_id="wf3",
        workbook_id="w1",
        sheet_name="s1",
        request=sample_request,
        result_df=sample_result_df,
        metadata=metadata
    )
    
    assert summary.feature_importance[0]["feature"] == "f1"
    assert summary.feature_importance[1]["feature"] == "f3" # 0.5 > 0.2

def test_sample_records_outliers(sample_request):
    df = pd.DataFrame({
        "f1": [1, 2, 100],
        "target": ["A", "A", "B"],
        "_is_outlier": [False, False, True],
        "_row_id": [1, 2, 3]
    })
    
    summary = build_model_review_summary(
        workflow_id="wf4",
        workbook_id="w1",
        sheet_name="s1",
        request=sample_request,
        result_df=df,
        metadata={}
    )
    
    assert len(summary.sample_outliers) == 1
    assert summary.sample_outliers[0]["row_id"] == 3
