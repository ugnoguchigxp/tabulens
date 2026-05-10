# TabuLens 探索評価機能 実装計画

この文書は、TabuLens の `Explore` に **特徴量が出ているか、ML が効いていそうか、次に何を試すべきかを評価する機能** を追加するための実装計画である。

ここで扱う機能は、削除済みの `Prepare Review` / `Model Review` を復活させるものではない。  
目的は、本番投入判断や提案の Apply / Discard ではなく、手元データの一時解析で「このデータは掘る価値があるか」を短時間で判断することである。

## 1. 目的

探索評価機能は、次の問いに答える。

- 選択した target に対して特徴量の信号があるか
- baseline より ML モデルが改善しているか
- 複数モデルの中で有望な候補があるか
- train / test gap が大きすぎないか
- データ品質や target の性質が結果の信用性を下げていないか
- 次に試すべき操作は feature の見直しか、target の見直しか、モデル設定の変更か

成功条件は、ユーザーが `Explore` 実行後に、次の判断を UI 上でできることである。

- `このデータは使えそう`
- `特徴量は弱いが追加調査の余地がある`
- `target または feature 設計を見直すべき`
- `ML を使うより baseline / ルールで十分そう`

## 2. 非目的

この機能では次を扱わない。

- 本番投入可否の判定
- `safe_to_promote`
- LLM による長文レビューを主導線にすること
- proposal の Apply / Discard / Rerun workflow
- model artifact の保存・ダウンロード
- 長期的な実験管理

## 3. 追加する概念

### 3.1 ExplorationEvaluation

`ExplorationResponse` に `evaluation` を追加する。

```python
class ExplorationEvaluation(BaseModel):
    signal_strength: Literal["none", "weak", "medium", "strong", "unknown"]
    model_viability: Literal["not_useful", "unclear", "promising", "strong", "unknown"]
    overall_verdict: Literal["try_more", "usable_signal", "needs_better_features", "needs_better_target", "not_enough_data"]
    confidence: float
    reasons: list[str]
    risk_flags: list[str]
    next_actions: list[ExplorationNextAction]
```

### 3.2 ExplorationNextAction

```python
class ExplorationNextAction(BaseModel):
    action: Literal[
        "inspect_features",
        "exclude_risky_columns",
        "change_target",
        "collect_more_rows",
        "try_balanced_class_weight",
        "try_regularized_model",
        "inspect_clusters",
        "inspect_outliers"
    ]
    reason: str
    priority: Literal["high", "medium", "low"]
```

### 3.3 FeatureSignal

既存の `DataProfileColumn` とは別に、target との関係を持つ feature 評価を追加する。

```python
class FeatureSignal(BaseModel):
    feature: str
    score: float
    score_kind: Literal["correlation", "mutual_information", "model_importance", "permutation_importance"]
    warning_flags: list[str]
```

MVP では `FeatureSignal` は `evaluation` 内の補助情報、または `feature_signal_report` として返す。

## 4. 判定ロジック

まずは deterministic ルールで実装する。  
OpenAI / Azure OpenAI は初期実装に含めない。

### 4.1 signal_strength

分類:

- `strong`: best model の test F1 または balanced accuracy が baseline より十分に高い
- `medium`: baseline 改善はあるが train / test gap または class imbalance がある
- `weak`: baseline 改善が小さい、または有効 feature が少ない
- `none`: baseline とほぼ同等、または全モデル失敗
- `unknown`: target 不明、データ不足、評価不能

回帰:

- `strong`: best model の RMSE / MAE が baseline より大きく改善し、R2 が正で安定
- `medium`: 改善はあるが gap または外れ値影響が大きい
- `weak`: 改善が小さい、R2 が低い
- `none`: baseline 未満または全モデル失敗
- `unknown`: target 不明、データ不足、評価不能

### 4.2 model_viability

分類:

- `strong`: 複数モデルが baseline を超え、gap が小さい
- `promising`: 1 つ以上のモデルが baseline を超える
- `unclear`: 改善はあるが、データ品質 warning が強い
- `not_useful`: baseline と同等以下

回帰:

- `strong`: R2 が十分に正で、RMSE / MAE が baseline から改善
- `promising`: best model は改善しているが gap がある
- `unclear`: 外れ値や target 分布の問題で判断が弱い
- `not_useful`: baseline と同等以下

### 4.3 risk_flags

最低限、次を返す。

- `label_column_missing`
- `not_enough_rows`
- `single_class_target`
- `minority_class_too_small`
- `class_imbalance`
- `near_constant_target`
- `high_missing_rate`
- `likely_identifier_features`
- `overfit_risk`
- `all_models_failed`
- `no_model_beats_baseline`

### 4.4 next_actions

判定は UI でそのまま表示できる粒度にする。

例:

- `exclude_risky_columns`: ID らしい列や高欠損列が feature に含まれる
- `change_target`: target が単一クラス、低分散、欠損過多
- `collect_more_rows`: 行数や minority class が少ない
- `try_balanced_class_weight`: class imbalance がある
- `try_regularized_model`: Random Forest が過学習し、線形モデルが安定している
- `inspect_clusters`: 特定クラスタに誤差や外れ値が偏る

## 5. API 方針

既存の `POST /api/explorations/run` を拡張する。

変更前:

```json
{
  "data_profile": {},
  "target_feasibility": {},
  "model_sweep": {}
}
```

変更後:

```json
{
  "data_profile": {},
  "target_feasibility": {},
  "model_sweep": {},
  "evaluation": {
    "signal_strength": "medium",
    "model_viability": "promising",
    "overall_verdict": "usable_signal",
    "confidence": 0.72,
    "reasons": [
      "Best model improves over baseline.",
      "Train/test gap is moderate."
    ],
    "risk_flags": [
      "class_imbalance"
    ],
    "next_actions": [
      {
        "action": "try_balanced_class_weight",
        "reason": "Minority class count is low.",
        "priority": "high"
      }
    ]
  }
}
```

別 endpoint は作らない。  
探索の評価は `Explore` 結果の一部であり、review workflow ではないためである。

## 6. 実装対象

### Backend

変更対象:

- `apps/api/app/models/schemas.py`
- `apps/api/app/services/exploration.py`
- `apps/api/app/routers/explorations.py`
- `apps/api/tests/test_explorations.py`

追加する関数:

- `build_exploration_evaluation(...)`
- `_evaluate_classification_signal(...)`
- `_evaluate_regression_signal(...)`
- `_baseline_improvement(...)`
- `_build_next_actions(...)`

`build_model_sweep` の結果を利用し、モデルを再実行しない。

### Frontend

変更対象:

- `apps/web/src/components/exploration-panel.tsx`
- `apps/web/src/App.tsx` は原則最小変更

表示する情報:

- signal strength
- model viability
- overall verdict
- confidence
- risk flags
- next actions
- reasons

UI 方針:

- 既存の右側 `ExplorationPanel` に集約する
- Review Panel / Modal は復活させない
- 長文説明ではなく、短い判定と理由を表示する

## 7. OpenAI / LLM 方針

初期実装では OpenAI / Azure OpenAI を使わない。

理由:

- 探索評価は数値指標から deterministic に出せる
- API key の有無でユーザー体験が変わると MVP の検証がぶれる
- 以前の review workflow と混同しやすい

将来追加する場合は、次の制約を置く。

- endpoint は増やさず `evaluation.summary_text` の生成だけに使う
- deterministic な `evaluation` を入力にする
- LLM の出力は意思決定の根拠ではなく、短い説明文に限定する
- API key がなくても完全に同じ評価が返る

## 8. 実装フェーズ

### Phase 1: スキーマと deterministic 評価

作業:

- `ExplorationEvaluation` と `ExplorationNextAction` を追加
- `ExplorationResponse` に `evaluation` を追加
- `build_exploration_evaluation` を実装
- 分類 / 回帰の baseline 改善を判定

完了条件:

- `POST /api/explorations/run` が `evaluation` を返す
- target 不明、分類、回帰、全モデル失敗のテストがある

### Phase 2: UI 表示

作業:

- `ExplorationPanel` に評価カードを追加
- risk flags と next actions を表示
- best model だけでなく、なぜその判定なのかを短く表示

完了条件:

- `Explore` 実行後に、特徴量が効いていそうかが画面上で分かる
- review / proposal / artifact 導線は復活していない

### Phase 3: FeatureSignal Report

作業:

- 分類では mutual information または model importance を出す
- 回帰では correlation と model importance を出す
- `likely_identifier` や `high_missing_rate` と合わせて feature 単位の評価を返す

完了条件:

- 上位 feature と除外候補が画面に表示される
- signal_strength の理由に feature signal が反映される

### Phase 4: Cluster / Outlier 連携

作業:

- clustering / anomaly の結果を exploration evaluation に入れる
- error rate または target distribution がクラスタに偏るかを見る
- `inspect_clusters` / `inspect_outliers` を next action として出す

完了条件:

- 分類・回帰だけでなく、クラスタ構造が探索判断に使われる

## 9. テスト方針

Backend:

- label なしで `unknown` が返る
- 分類で baseline を超えると `usable_signal` が返る
- 単一クラス target で `needs_better_target` が返る
- 回帰で baseline 改善がない場合に `needs_better_features` が返る
- 全モデル失敗時に `all_models_failed` が返る

Frontend:

- `ExplorationPanel` が `signal_strength` と `next_actions` を表示する
- `risk_flags` が空でも表示崩れしない
- 既存の `Explore` 実行導線が壊れない

検証コマンド:

```bash
python3 -m py_compile \
  apps/api/app/models/schemas.py \
  apps/api/app/services/exploration.py \
  apps/api/app/routers/explorations.py

pnpm --dir apps/web build
pnpm --dir apps/web test -- --run
```

## 10. 判断ルール

- 評価は `Explore` の結果として返す
- Review / Proposal / Rerun の概念は戻さない
- OpenAI は初期実装に入れない
- まず deterministic な評価を完成させる
- UI は「判定」「理由」「次の一手」だけを短く表示する
- モデル実行、クラスタリング、境界グラフは維持する

