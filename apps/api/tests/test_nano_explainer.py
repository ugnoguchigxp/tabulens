import pytest
import json
from unittest.mock import patch, MagicMock
from app.services.llm.nano_explainer import (
    call_azure_openai_json,
    _parse_json_content,
    explain_cluster,
    review_job_summary,
    review_model_workflow_summary,
    _fallback_review
)

@pytest.fixture
def mock_azure_config():
    return {
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-deployment",
        "AZURE_OPENAI_API_VERSION": "2023-05-15"
    }

def test_parse_json_content_raw():
    content = '{"key": "value"}'
    assert _parse_json_content(content) == {"key": "value"}

def test_parse_json_content_markdown():
    content = '```json\n{"key": "value"}\n```'
    assert _parse_json_content(content) == {"key": "value"}

def test_parse_json_content_with_text():
    content = 'Here is the result: {"key": "value"} hope it helps.'
    assert _parse_json_content(content) == {"key": "value"}

@patch("app.services.llm.nano_explainer._azure_openai_config")
def test_call_azure_openai_fallback_when_no_config(mock_config):
    mock_config.return_value = None
    
    def fallback(payload):
        return {"status": "fallback_active"}
    
    result = call_azure_openai_json(
        system_prompt="test",
        user_payload={"data": 1},
        fallback=fallback
    )
    
    assert result == {"status": "fallback_active", "source": "fallback"}

@patch("app.services.llm.nano_explainer._azure_openai_config")
@patch("urllib.request.urlopen")
def test_call_azure_openai_success(mock_urlopen, mock_config, mock_azure_config):
    mock_config.return_value = mock_azure_config
    
    # Mock response
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{
            "message": {
                "content": '{"decision": "keep"}'
            }
        }]
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response
    
    result = call_azure_openai_json(
        system_prompt="test",
        user_payload={"data": 1},
        fallback=lambda x: {"status": "error"}
    )
    
    assert result == {"decision": "keep"}

def test_fallback_review_basic():
    summary = {
        "row_count": 10, # too small
        "missing_rate": 0.2, # too high
        "outlier_rate": 0.1
    }
    result = _fallback_review(summary)
    assert result["assessment"] == "needs_more_data"
    assert "データ件数が少なすぎる" in result["blocking_factors"]
    assert "欠損率が高い" in result["blocking_factors"]
    assert any(a["action"] == "change_missing" for a in result["recommended_actions"])

@patch("app.services.llm.nano_explainer._azure_openai_config")
def test_explain_cluster_fallback(mock_config):
    mock_config.return_value = None
    summary = {"size": 2, "is_outlier": True}
    result = explain_cluster(summary)
    assert result["decision"] == "likely_outlier"

def test_review_model_workflow_summary_fallback():
    summary = {
        "use_case": "classification",
        "row_count": 100,
        "metrics": {"accuracy": 0.4}, # very low
        "diagnostics": {"confidence_mean": 0.5},
        "quality_flags": ["class_imbalance"]
    }
    result = review_model_workflow_summary(summary, force_fallback=True)
    assert result["assessment"] == "reject"
    assert any(a["action"] == "rebalance_classes" for a in result["recommended_actions"])
    assert result["source"] == "fallback"
