from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any


def _candidate_env_paths() -> list[Path]:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / ".env",
        Path.cwd() / ".env",
        here.parents[5].parent / "composia-ui/.env",
    ]
    seen: set[Path] = set()
    result: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


@lru_cache(maxsize=1)
def _azure_openai_config() -> dict[str, str] | None:
    keys = {
        "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_DEPLOYMENT_NAME": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
    }
    if all(keys.values()):
        return {k: v for k, v in keys.items() if v}

    for env_path in _candidate_env_paths():
        loaded = _load_env_file(env_path)
        merged = {
            "AZURE_OPENAI_API_KEY": keys["AZURE_OPENAI_API_KEY"] or loaded.get("AZURE_OPENAI_API_KEY"),
            "AZURE_OPENAI_ENDPOINT": keys["AZURE_OPENAI_ENDPOINT"] or loaded.get("AZURE_OPENAI_ENDPOINT"),
            "AZURE_OPENAI_DEPLOYMENT_NAME": keys["AZURE_OPENAI_DEPLOYMENT_NAME"] or loaded.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
            "AZURE_OPENAI_API_VERSION": keys["AZURE_OPENAI_API_VERSION"] or loaded.get("AZURE_OPENAI_API_VERSION"),
        }
        if all(merged.values()):
            return {k: v for k, v in merged.items() if v}

    return None


def is_configured() -> bool:
    return _azure_openai_config() is not None


def call_azure_openai_json(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    fallback: Any,
    temperature: float = 0.2,
    max_completion_tokens: int = 300,
) -> dict[str, Any]:
    config = _azure_openai_config()
    if not config:
        fallback_payload = fallback(user_payload)
        if isinstance(fallback_payload, dict):
            fallback_payload.setdefault("source", "fallback")
        return fallback_payload

    endpoint = config["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    deployment = config["AZURE_OPENAI_DEPLOYMENT_NAME"]
    api_version = config["AZURE_OPENAI_API_VERSION"]
    api_key = config["AZURE_OPENAI_API_KEY"]

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    body = {
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
        "temperature": temperature,
        "max_completion_tokens": max_completion_tokens,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        parsed = _parse_json_content(content)
        if isinstance(parsed, dict):
            return parsed
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError, TimeoutError, ValueError):
        pass

    fallback_payload = fallback(user_payload)
    if isinstance(fallback_payload, dict):
        fallback_payload.setdefault("source", "fallback")
    return fallback_payload


def explain_cluster(summary: dict[str, Any]) -> dict[str, str]:
    parsed = call_azure_openai_json(
        system_prompt=(
            "You are a careful data review assistant. "
            "Return only JSON with keys decision, reason, recommended_action. "
            "decision must be one of keep_as_class, merge_with_nearest_cluster, new_subclass_candidate, likely_outlier, review_manually, exclude_from_training, needs_more_data."
        ),
        user_payload=summary,
        fallback=_fallback_cluster_explanation,
        temperature=0.2,
        max_completion_tokens=250,
    )
    parsed.setdefault("source", "openai" if is_configured() else "fallback")
    return {
        "decision": str(parsed.get("decision", "review_manually")),
        "reason": str(parsed.get("reason", "")),
        "recommended_action": str(parsed.get("recommended_action", "")),
    }


def review_job_summary(summary: dict[str, Any], force_fallback: bool = False) -> dict[str, Any]:
    if force_fallback:
        parsed = _fallback_review(summary)
        parsed.setdefault("source", "fallback")
        return parsed

    parsed = call_azure_openai_json(
        system_prompt=(
            "あなたは表形式データのレビュー担当です。出力は JSON のみ。日本語で簡潔に。"
            "JSON 形式は次の形に厳密に従う: "
            "{\"assessment\":\"needs_improvement\",\"confidence\":0.74,\"blocking_factors\":[\"短い一文\"],\"recommended_actions\":[{\"action\":\"remove_outliers\",\"target\":\"...\",\"reason\":\"...\",\"expected_effect\":\"...\",\"safe_to_apply\":true,\"params\":{}}],\"safe_to_apply\":false}. "
            "assessment は keep / needs_improvement / disable / review_manually / needs_more_data のいずれか。"
            "confidence は 0 から 1 の数値。"
            "blocking_factors は文字列の配列で最大 3 件。"
            "recommended_actions は最大 3 件のオブジェクト配列で、各要素は action, target, reason, expected_effect, safe_to_apply, params を持つ。"
            "safe_to_apply は true か false の真偽値のみ。"
            "action は remove_outliers / exclude_islands / drop_features / change_missing / change_normalization / switch_algorithm / review_manually のいずれか。"
            "prediction threshold の調整は提案しない。"
        ),
        user_payload=summary,
        fallback=_fallback_review,
        temperature=0.1,
        max_completion_tokens=700,
    )
    parsed.setdefault("source", "openai" if is_configured() else "fallback")
    return parsed


def review_model_workflow_summary(summary: dict[str, Any], force_fallback: bool = False) -> dict[str, Any]:
    if force_fallback:
        parsed = _fallback_model_review(summary)
        parsed.setdefault("source", "fallback")
        return parsed

    parsed = call_azure_openai_json(
        system_prompt=(
            "あなたは学習後のモデルレビュー担当です。出力は JSON のみ。日本語で簡潔に。"
            "JSON 形式は次の形に厳密に従う: "
            "{\"assessment\":\"needs_improvement\",\"confidence\":0.74,\"reason\":\"...\",\"blocking_factors\":[\"...\"],\"recommended_actions\":[{\"action\":\"rebalance_classes\",\"target\":\"label_column\",\"reason\":\"...\",\"expected_effect\":\"...\",\"safe_to_apply\":true,\"params\":{}}],\"safe_to_promote\":false}. "
            "assessment は pass / needs_improvement / reject / review_manually / needs_more_data のいずれか。"
            "confidence は 0 から 1 の数値。"
            "blocking_factors は最大 3 件の文字列配列。"
            "recommended_actions は最大 3 件のオブジェクト配列で、各要素は action, target, reason, expected_effect, safe_to_apply, params を持つ。"
            "action は adjust_decision_threshold / rebalance_classes / enable_stratified_split / increase_test_size / switch_algorithm / tune_hyperparameters / drop_leaky_features / normalize_features / adjust_contamination / adjust_cluster_count / adjust_dbscan_eps / switch_to_preview_mode / review_label_quality / collect_more_data のいずれか。"
            "safe_to_promote は最終承認ではなく参考値。"
        ),
        user_payload=summary,
        fallback=_fallback_model_review,
        temperature=0.1,
        max_completion_tokens=800,
    )
    parsed.setdefault("source", "openai" if is_configured() else "fallback")
    return parsed


def _parse_json_content(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first : last + 1]
    parsed = json.loads(text)
    return parsed if isinstance(parsed, dict) else None


def _fallback_cluster_explanation(summary: dict[str, Any]) -> dict[str, str]:
    size = int(summary.get("size", 0) or 0)
    if summary.get("is_outlier"):
        decision = "likely_outlier"
        action = "外れ値候補として人間レビューしてください。"
    elif size <= 3:
        decision = "new_subclass_candidate"
        action = "小規模クラスタとして別カテゴリ候補を確認してください。"
    else:
        decision = "review_manually"
        action = "クラスタ単位で手動レビューしてください。"

    return {
        "decision": decision,
        "reason": "Azure OpenAI が利用できないため、ルールベースの暫定判断を返しました。",
        "recommended_action": action,
        "source": "fallback",
    }


def _fallback_review(summary: dict[str, Any]) -> dict[str, Any]:
    row_count = int(summary.get("row_count", 0) or 0)
    missing_rate = float(summary.get("missing_rate", 0.0) or 0.0)
    outlier_rate = float(summary.get("outlier_rate", 0.0) or 0.0)
    island_rate = float(summary.get("island_rate", 0.0) or 0.0)
    confidence = summary.get("prediction_confidence", {}) or {}
    confidence_mean = float(confidence.get("mean", 0.0) or 0.0)
    feature_importance_top = summary.get("feature_importance_top", []) or []
    class_distribution = summary.get("class_distribution", []) or []

    blocking_factors: list[str] = []
    recommended_actions: list[dict[str, Any]] = []

    if row_count < 20:
        blocking_factors.append("データ件数が少なすぎる")
    if missing_rate >= 0.15:
        blocking_factors.append("欠損率が高い")
        recommended_actions.append(
            {
                "action": "change_missing",
                "target": "median",
                "reason": "欠損が多いため中央値補完を優先する",
                "expected_effect": "外れ値の影響を抑えた補完",
                "safe_to_apply": True,
                "params": {"handle_missing": "median"},
            }
        )
    if outlier_rate >= 0.05:
        blocking_factors.append("外れ値が多い")
        recommended_actions.append(
            {
                "action": "remove_outliers",
                "target": "current_outliers",
                "reason": "外れ値が分類境界を歪めている",
                "expected_effect": "分類境界の安定化",
                "safe_to_apply": False,
                "params": {"scope": "outliers"},
            }
        )
    if island_rate >= 0.03:
        blocking_factors.append("飛び地クラスタがある")
        recommended_actions.append(
            {
                "action": "exclude_islands",
                "target": "current_islands",
                "reason": "孤立クラスタが学習を阻害している",
                "expected_effect": "ノイズ混入の低減",
                "safe_to_apply": False,
                "params": {"scope": "islands"},
            }
        )
    if confidence_mean and confidence_mean < 0.65:
        blocking_factors.append("予測確信度が低い")
        if feature_importance_top:
            tail_features = [item.get("feature") for item in feature_importance_top[-2:] if item.get("feature")]
            if tail_features:
                recommended_actions.append(
                    {
                        "action": "drop_features",
                        "target": tail_features,
                        "reason": "重要度の低い特徴量を除いて再学習する",
                        "expected_effect": "ノイズ抑制",
                        "safe_to_apply": True,
                        "params": {},
                    }
                )
    if len(class_distribution) > 1:
        counts = [int(item.get("count", 0) or 0) for item in class_distribution]
        if counts and min(counts) > 0 and max(counts) / min(counts) >= 5:
            blocking_factors.append("クラス不均衡が大きい")
            recommended_actions.append(
                {
                    "action": "review_manually",
                    "target": "class_balance",
                    "reason": "ラベル偏りが大きく、単純な自動補正では危険",
                    "expected_effect": "人間確認の優先度上昇",
                    "safe_to_apply": False,
                    "params": {},
                }
            )

    assessment = "keep"
    if blocking_factors:
        assessment = "needs_improvement"
    if row_count < 20:
        assessment = "needs_more_data"

    safe_to_apply = any(bool(action.get("safe_to_apply")) for action in recommended_actions)
    if not recommended_actions and blocking_factors:
        recommended_actions.append(
            {
                "action": "review_manually",
                "target": "analysis",
                "reason": "自動適用より人間確認を優先する",
                "expected_effect": "誤適用の回避",
                "safe_to_apply": False,
                "params": {},
            }
        )

    return {
        "assessment": assessment,
        "confidence": 0.72 if blocking_factors else 0.88,
        "blocking_factors": blocking_factors,
        "recommended_actions": recommended_actions,
        "reason": "Azure OpenAI が利用できないため、ルールベースの暫定レビューを返しました。",
        "safe_to_apply": safe_to_apply,
        "source": "fallback",
    }


def _fallback_model_review(summary: dict[str, Any]) -> dict[str, Any]:
    use_case = str(summary.get("use_case", "")).lower()
    metrics = summary.get("metrics", {}) or {}
    quality_flags = [str(flag) for flag in summary.get("quality_flags", []) or []]
    diagnostics = summary.get("diagnostics", {}) or {}
    blocking_factors: list[str] = []
    recommended_actions: list[dict[str, Any]] = []

    if use_case == "classification":
        accuracy = float(metrics.get("accuracy", 0.0) or 0.0)
        balanced_accuracy = float(metrics.get("balanced_accuracy", 0.0) or 0.0)
        confidence_mean = float(diagnostics.get("confidence_mean", metrics.get("confidence_mean", 0.0)) or 0.0)
        train_test_gap = abs(float(diagnostics.get("train_accuracy", metrics.get("train_accuracy", 0.0)) or 0.0) - float(diagnostics.get("test_accuracy", metrics.get("test_accuracy", accuracy)) or accuracy))
        if accuracy < 0.65:
            blocking_factors.append("accuracy が低い")
        if balanced_accuracy < 0.6:
            blocking_factors.append("balanced accuracy が低い")
        if confidence_mean and confidence_mean < 0.65:
            blocking_factors.append("confidence が低い")
        if train_test_gap > 0.15:
            blocking_factors.append("train/test gap が大きい")
            recommended_actions.append(
                {
                    "action": "increase_test_size",
                    "target": "split_ratio",
                    "reason": "評価分割を広げて過学習を確認する",
                    "expected_effect": "汎化性能の把握精度向上",
                    "safe_to_apply": True,
                    "params": {"test_size": 0.3},
                }
            )
        if "class_imbalance" in quality_flags:
            blocking_factors.append("クラス不均衡がある")
            recommended_actions.append(
                {
                    "action": "rebalance_classes",
                    "target": "label_column",
                    "reason": "少数クラスの取りこぼしを抑える",
                    "expected_effect": "少数クラス recall の改善",
                    "safe_to_apply": True,
                    "params": {"class_weight": "balanced"},
                }
            )
        if "low_confidence" in quality_flags:
            recommended_actions.append(
                {
                    "action": "normalize_features",
                    "target": "feature_columns",
                    "reason": "特徴量のスケール差を抑える",
                    "expected_effect": "confidence の安定化",
                    "safe_to_apply": True,
                    "params": {"normalization": "standard"},
                }
            )
        assessment = "pass"
        if blocking_factors:
            assessment = "needs_improvement"
        if accuracy < 0.5 and balanced_accuracy < 0.5:
            assessment = "reject"
        if summary.get("row_count", 0) < 30:
            assessment = "needs_more_data"
    elif use_case == "prediction":
        r2 = float(metrics.get("r2", 0.0) or 0.0)
        mae = float(metrics.get("mae", 0.0) or 0.0)
        rmse = float(metrics.get("rmse", 0.0) or 0.0)
        residual_mean = float(diagnostics.get("residual_mean", metrics.get("residual_mean", 0.0)) or 0.0)
        residual_std = float(diagnostics.get("residual_std", metrics.get("residual_std", 0.0)) or 0.0)
        if r2 < 0.3:
            blocking_factors.append("R2 が低い")
        if mae > 0 and rmse > 0 and rmse > mae * 1.25:
            blocking_factors.append("誤差が大きい")
        if abs(residual_mean) > max(1e-6, residual_std * 0.25):
            blocking_factors.append("残差に偏りがある")
        if "train_test_gap" in quality_flags:
            recommended_actions.append(
                {
                    "action": "increase_test_size",
                    "target": "split_ratio",
                    "reason": "検証条件を厳しくして汎化を確認する",
                    "expected_effect": "評価信頼性の向上",
                    "safe_to_apply": True,
                    "params": {"test_size": 0.3},
                }
            )
        if "low_r2" in quality_flags or "high_error" in quality_flags:
            recommended_actions.append(
                {
                    "action": "switch_algorithm",
                    "target": "model",
                    "reason": "別アルゴリズムで誤差構造が改善する可能性がある",
                    "expected_effect": "予測誤差の削減",
                    "safe_to_apply": True,
                    "params": {"algorithm": "gradient_boosting"},
                }
            )
        assessment = "pass"
        if blocking_factors:
            assessment = "needs_improvement"
        if r2 < 0.0 and mae > 0:
            assessment = "reject"
        if summary.get("row_count", 0) < 30:
            assessment = "needs_more_data"
    else:
        assessment = "review_manually"
        blocking_factors.append("use case が未対応")
        recommended_actions.append(
            {
                "action": "collect_more_data",
                "target": "workflow",
                "reason": "自動判定より先にデータ条件を見直す",
                "expected_effect": "判断材料の増加",
                "safe_to_apply": False,
                "params": {},
            }
        )

    if not recommended_actions and blocking_factors:
        recommended_actions.append(
            {
                "action": "review_label_quality" if use_case in {"classification", "prediction"} else "collect_more_data",
                "target": "workflow",
                "reason": "自動適用より人間確認を優先する",
                "expected_effect": "誤適用の回避",
                "safe_to_apply": False,
                "params": {},
            }
        )

    safe_to_promote = assessment == "pass" and not blocking_factors
    return {
        "assessment": assessment,
        "confidence": 0.82 if blocking_factors else 0.9,
        "reason": "Azure OpenAI が利用できないため、ルールベースの暫定レビューを返しました。",
        "blocking_factors": blocking_factors,
        "recommended_actions": recommended_actions,
        "safe_to_promote": safe_to_promote,
        "source": "fallback",
    }
