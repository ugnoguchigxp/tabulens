# TabuLens 学習後レビュー 実装計画

この文書は、TabuLens の `Workflow` 実行後に、学習結果・検知結果・推薦結果をレビューし、改善提案と再実行判断につなげる **Model Review / Training QA** 機能の実装計画である。

`Prepare QA` は学習前のデータ品質と前処理の妥当性を扱う。  
`Model Review` は Workflow 実行後のモデル・結果・評価指標の妥当性を扱う。

## 1. 目的

Model Review の目的は、単に精度指標を表示することではない。  
次の問いに答えられる状態を作る。

- このモデルは実運用に使える品質か
- 見かけ上の精度が高いだけで、過学習・リーク・偏りがないか
- 少数クラス、外れ値、低信頼サンプル、特定クラスタなど、失敗しやすい領域はどこか
- 何を変えれば改善する可能性が高いか
- 改善提案を適用して再学習・再実行するべきか
- 改善後に、元の結果より良くなったと言えるか

LLM は最終判断者ではなく、バックエンドが集約した評価サマリを読み、改善候補を整理するレビュアーとして使う。

## 2. 現状

現在の実装には、次の基盤がある。

- `Prepare` と `Workflow` の責務分離
- Prepare 完了後にだけ Workflow を実行する導線
- `classification`, `prediction`, `anomaly_detection`, `recommendation`, `clustering`, `noise_reduction` の `use_case`
- 分類 / 回帰の train / test split
- 分類境界グラフ
- Workflow metrics
- Workflow result rows
- model artifact zip
- Prepare QA の LLM レビュー
- Apply / Discard 済み提案を `resolved_proposals` として扱い、同じ提案を再表示しない仕組み

不足しているものは、Workflow 実行後に結果をレビューする専用のサマリ、判定、改善提案、再実行導線である。

## 3. 責務分離

### 3.1 Prepare QA

対象:

- 欠損
- 外れ値
- 不要カラム
- 特徴量重要度
- ラベル列と特徴量列の整合性
- 学習前のクレンジング方針

主な出力:

- `ReviewSummary`
- `ReviewResult`
- `ReviewAction`
- Prepare proposal
- Prepare before / after comparison

### 3.2 Workflow

対象:

- 用途別のモデル実行
- 学習 / 検証分割
- metrics 生成
- result rows 生成
- model artifact 保存

主な出力:

- `ModelWorkflowResponse`
- `WorkflowMetrics`
- `results.csv`
- `export.xlsx`
- `model_artifact.zip`

### 3.3 Model Review

対象:

- Workflow 実行後の品質判定
- metrics の解釈
- 失敗サンプルの抽出
- 過学習・リーク・偏り・低信頼領域の検出
- 改善提案
- Apply & Retrain / Re-run

主な出力:

- `ModelReviewSummary`
- `ModelReviewResult`
- `ModelReviewProposal`
- `ModelReviewComparison`
- `model-review.json`
- `model-review-actions.json`

## 4. 基本ワークフロー

1. ユーザーが workbook をアップロードする
2. Mapping Settings で列を選ぶ
3. `Prepare` を実行する
4. 必要な Prepare 提案を Apply / Discard する
5. `Workflow` を開く
6. use case、アルゴリズム、分割方法、追加パラメータを設定する
7. Workflow を実行する
8. Workflow metrics と結果行を保存する
9. `Model Review` を実行する
10. バックエンドが use case 別にレビューサマリを作る
11. LLM または fallback がレビュー判定と改善提案を返す
12. ユーザーが提案を Apply / Discard する
13. Apply した提案で Workflow を再実行する
14. Before / After を比較する
15. 改善したモデルを artifact として保存・ダウンロードする

## 5. LLM の使い方

### 5.1 LLM に渡す情報

LLM に生データ全量は渡さない。  
渡すのは、バックエンドで deterministic に生成した短い JSON サマリに限定する。

含める情報:

- `workflow_id`
- `use_case`
- `algorithm`
- `row_count`
- `train_count`
- `test_count`
- `unused_count`
- `feature_columns`
- `label_column`
- `metrics`
- `quality_flags`
- `diagnostics`
- `sample_errors`
- `sample_low_confidence`
- `sample_outliers`
- `feature_importance`
- `boundary_summary`
- `split_summary`
- `previous_review_actions`

含めない情報:

- 全行データ
- API key
- user の個人情報
- 明示的に選ばれていない列の値
- 既に `resolved` になった同一提案

### 5.2 LLM の出力

LLM の出力は自然文だけにしない。  
必ず機械可読 JSON にする。

```json
{
  "assessment": "needs_improvement",
  "confidence": 0.82,
  "reason": "全体 accuracy は高いが、少数クラスの recall が低く、運用上重要な失敗を見逃す可能性がある。",
  "blocking_factors": [
    "minority_class_recall_low",
    "train_test_gap"
  ],
  "recommended_actions": [
    {
      "action": "rebalance_classes",
      "target": "label_column",
      "reason": "少数クラスの recall を改善するため",
      "expected_effect": "at_risk の取りこぼしを減らす",
      "safe_to_apply": true,
      "params": {
        "class_weight": "balanced"
      }
    }
  ],
  "safe_to_promote": false
}
```

### 5.3 fallback

OpenAI / Azure OpenAI が使えない場合でも、ルールベースの fallback を返す。

fallback の役割:

- 明らかな問題を検出する
- safe な提案を最低限返す
- UI と API の挙動を LLM 有無に依存させない

## 6. レビュー判定

`assessment` は Workflow の成果物に対する判断である。

| 値 | 意味 |
| --- | --- |
| `pass` | 現時点で大きな阻害要因はない |
| `needs_improvement` | 改善余地があり、再実行候補がある |
| `reject` | 実運用に使うべきではない |
| `review_manually` | 指標だけでは判断できない |
| `needs_more_data` | データ量や正解ラベルが不足している |

## 7. use case 別レビュー観点

### 7.1 Classification

入力:

- accuracy
- balanced accuracy
- precision
- recall
- F1
- confusion matrix
- prediction confidence
- train / test split
- class distribution
- misclassified samples
- low confidence samples
- decision boundary summary

検出したい問題:

- 全体 accuracy は高いが、少数クラス recall が低い
- train と test の差が大きい
- 特定クラスだけ誤分類が多い
- confidence が全体的に低い
- ラベル列が特徴量に混入している
- 境界グラフ上でクラスが強く混ざっている

改善提案:

- `rebalance_classes`
- `adjust_decision_threshold`
- `switch_algorithm`
- `tune_hyperparameters`
- `drop_leaky_features`
- `increase_test_size`
- `enable_stratified_split`
- `review_label_quality`

### 7.2 Prediction / Regression

入力:

- MAE
- RMSE
- R2
- residual mean
- residual std
- residual quantiles
- high error samples
- target distribution
- train / test split

検出したい問題:

- R2 が低い
- 残差が特定方向に偏っている
- 外れ値に引っ張られている
- 特定レンジだけ誤差が大きい
- train と test の差が大きい
- target がほぼ定数または極端に歪んでいる

改善提案:

- `remove_high_error_outliers`
- `transform_target`
- `switch_algorithm`
- `tune_hyperparameters`
- `normalize_features`
- `increase_test_size`
- `review_target_quality`

### 7.3 Anomaly Detection

入力:

- anomaly count
- anomaly rate
- score distribution
- score threshold
- known label がある場合の precision / recall / F1
- top anomaly samples

検出したい問題:

- anomaly rate が高すぎるまたは低すぎる
- contamination 設定がデータ規模に合っていない
- 正常データまで過剰に異常扱いしている
- known label があるのに recall が低い

改善提案:

- `adjust_contamination`
- `switch_detector`
- `review_anomaly_threshold`
- `remove_noise_features`
- `review_known_labels`

### 7.4 Recommendation

入力:

- recommendation count
- user count
- item count
- coverage
- top item concentration
- cold start user / item count
- rating column availability

検出したい問題:

- 人気アイテム偏重
- coverage が低い
- cold start が多い
- rating がないため品質評価が弱い
- interaction 数が少ない

改善提案:

- `increase_top_k`
- `add_rating_column`
- `switch_recommender`
- `filter_low_interaction_users`
- `improve_item_coverage`

### 7.5 Clustering

入力:

- cluster count
- cluster size distribution
- noise ratio
- small cluster count
- silhouette score
- representative samples
- distance to centroid distribution

検出したい問題:

- クラスタ数が多すぎるまたは少なすぎる
- ほぼ全件が 1 クラスタに偏る
- noise が多すぎる
- silhouette score が低い
- 小規模クラスタが多すぎる

改善提案:

- `adjust_cluster_count`
- `switch_clustering_algorithm`
- `adjust_dbscan_eps`
- `remove_noise_features`
- `normalize_features`
- `review_cluster_semantics`

### 7.6 Noise Reduction

入力:

- noise candidate count
- retained count
- candidate rate
- noise reasons
- duplicate count
- missing row count
- anomaly score distribution

検出したい問題:

- 除外候補が多すぎる
- auto apply が危険
- 欠損理由と外れ値理由が混ざっている
- 重要クラスの行まで除外候補になっている

改善提案:

- `switch_to_preview_mode`
- `adjust_noise_threshold`
- `separate_missing_and_outlier_rules`
- `review_noise_candidates`
- `apply_noise_reduction`

## 8. データモデル

### 8.1 ModelReviewSummary

```python
class ModelReviewSummary(BaseModel):
    workflow_id: str
    source_job_id: str | None = None
    workbook_id: str
    sheet_name: str
    use_case: UseCaseType
    algorithm: str
    row_count: int
    train_count: int = 0
    test_count: int = 0
    unused_count: int = 0
    feature_columns: list[str] = []
    label_column: str | None = None
    metrics: dict[str, Any] = {}
    quality_flags: list[str] = []
    diagnostics: dict[str, Any] = {}
    feature_importance: list[dict[str, Any]] = []
    sample_errors: list[dict[str, Any]] = []
    sample_low_confidence: list[dict[str, Any]] = []
    sample_outliers: list[dict[str, Any]] = []
    boundary_summary: dict[str, Any] = {}
    split_summary: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
```

### 8.2 ModelReviewAction

```python
class ModelReviewAction(BaseModel):
    proposal_id: str
    action: ModelReviewActionType
    target: Any = None
    reason: str = ""
    expected_effect: str | None = None
    safe_to_apply: bool = False
    params: dict[str, Any] = {}
    status: ProposalStatus = ProposalStatus.PENDING
```

### 8.3 ModelReviewResult

```python
class ModelReviewResult(BaseModel):
    assessment: ModelReviewAssessment
    confidence: float = 0.0
    reason: str = ""
    blocking_factors: list[str] = []
    recommended_actions: list[ModelReviewAction] = []
    safe_to_promote: bool = False
    source: str = "openai"
    summary: ModelReviewSummary | None = None
```

### 8.4 ModelReviewComparison

```python
class ModelReviewComparison(BaseModel):
    workflow_id: str
    before_workflow_id: str
    after_workflow_id: str
    before: ModelReviewSummary
    after: ModelReviewSummary
    deltas: dict[str, Any]
    applied_actions: list[ModelReviewAction]
    accepted: bool
```

## 9. Action Type

初期対応する提案種別:

| action | use case | 自動適用 | 内容 |
| --- | --- | --- | --- |
| `adjust_decision_threshold` | classification | 条件付き | confidence threshold や positive class threshold を変える |
| `rebalance_classes` | classification | 可 | `class_weight=balanced` などを有効化 |
| `enable_stratified_split` | classification | 可 | stratify を強制する |
| `increase_test_size` | classification, prediction | 可 | test split を増やす |
| `switch_algorithm` | all | 可 | アルゴリズムを変更する |
| `tune_hyperparameters` | all | 条件付き | 限定された param grid を使う |
| `drop_leaky_features` | supervised | 要確認 | ラベルリーク疑いの特徴量を外す |
| `normalize_features` | supervised, clustering | 可 | standard / minmax を変更する |
| `adjust_contamination` | anomaly, noise | 可 | contamination を変更する |
| `adjust_cluster_count` | clustering | 可 | cluster_count を変更する |
| `adjust_dbscan_eps` | clustering | 可 | DBSCAN eps を変更する |
| `switch_to_preview_mode` | noise_reduction | 可 | auto 除外を preview に戻す |
| `review_label_quality` | supervised | 不可 | 人間確認を促す |
| `collect_more_data` | all | 不可 | データ追加を促す |

## 10. API 設計

### 10.1 レビュー取得

```txt
GET /api/model-workflows/{workflow_id}/review-summary
GET /api/model-workflows/{workflow_id}/review
```

挙動:

- 保存済みレビューがあれば返す
- なければ 404 または空状態を返す
- UI は Workflow 完了後に `Review Model` を表示する

### 10.2 レビュー実行

```txt
POST /api/model-workflows/{workflow_id}/review
```

挙動:

- Workflow state, metrics, result rows を読み込む
- `ModelReviewSummary` を生成する
- LLM または fallback で `ModelReviewResult` を生成する
- `resolved_model_review_proposals` と照合し、同一提案を active list に戻さない
- state と artifact に保存する

### 10.3 提案一覧

```txt
GET /api/model-workflows/{workflow_id}/review-proposals
```

挙動:

- active な ModelReviewAction だけ返す
- applied / discarded は `resolved_model_review_proposals` に保持する

### 10.4 提案適用と再実行

```txt
POST /api/model-workflows/{workflow_id}/review-proposals/{proposal_id}/apply
POST /api/model-workflows/{workflow_id}/review-proposals/{proposal_id}/discard
POST /api/model-workflows/{workflow_id}/review-rerun
```

挙動:

- Apply 時は元 Workflow request をコピーする
- 提案内容を request.params / algorithm / mapping / preprocessing に反映する
- 新しい Workflow を作成して再実行する
- Before / After の `ModelReviewComparison` を作る
- 元 workflow には `child_workflow_ids` を保存する
- 新 workflow には `parent_workflow_id` と `applied_model_review_actions` を保存する

## 11. 保存形式

Workflow state に追加する項目:

```json
{
  "model_review_summary": {},
  "model_review_result": {},
  "model_review_proposals": [],
  "resolved_model_review_proposals": [],
  "last_applied_model_review_proposals": [],
  "model_review_comparison": null,
  "parent_workflow_id": null,
  "child_workflow_ids": []
}
```

artifact に追加するファイル:

```txt
model_review_summary.json
model_review_result.json
model_review_actions.json
model_review_comparison.json
```

`model_artifact.zip` にも追加する:

```txt
model_review_summary.json
model_review_result.json
model_review_comparison.json
```

## 12. UI 設計

### 12.1 Workflow Panel

Workflow 完了後の右側パネルに `Model Review` セクションを追加する。

表示内容:

- assessment badge
- confidence
- safe to promote
- reason
- blocking factors
- review button
- proposal count

### 12.2 Model Review Modal

詳細表示はモーダルにする。  
Workflow Panel に全部詰め込むと、metrics、結果サンプル、境界グラフと競合するため。

モーダル構成:

- Overview
- Metrics Review
- Error Analysis
- Low Confidence Samples
- Feature / Boundary Review
- Proposals
- Before / After Comparison

### 12.3 Apply & Retrain

提案カードには次を表示する。

- action
- target
- reason
- expected effect
- safe / manual
- Apply & Retrain
- Discard

適用後:

- ボタンを disabled にする
- active proposals からは消す
- `resolved` に保存する
- comparison に表示する
- 同じ提案は再レビューで出さない

## 13. 改善判定

Before / After の accepted 判定は use case ごとに変える。

### 13.1 Classification

優先順:

1. macro F1 または balanced accuracy が改善
2. 重要クラス recall が改善
3. test accuracy が大きく悪化していない
4. train / test gap が広がっていない
5. low confidence rate が下がる

### 13.2 Prediction

優先順:

1. RMSE が下がる
2. MAE が下がる
3. R2 が上がる
4. residual bias が小さくなる
5. high error sample rate が下がる

### 13.3 Anomaly Detection

優先順:

1. known label があれば F1 / recall が改善
2. anomaly rate が設定範囲に入る
3. score separation が改善
4. top anomaly の説明可能性が上がる

### 13.4 Recommendation

優先順:

1. precision@k / recall@k が改善
2. coverage が改善
3. 人気偏重が下がる
4. recommendation count が十分に残る

### 13.5 Clustering

優先順:

1. silhouette score が改善
2. cluster size の偏りが下がる
3. noise ratio が下がる
4. 代表サンプルの一貫性が上がる

### 13.6 Noise Reduction

優先順:

1. candidate rate が妥当範囲に入る
2. retained count が十分に残る
3. noise reason が明確になる
4. 重要ラベルの行を過剰除外しない

## 14. 実装フェーズ

### Phase 1: サマリ生成基盤

対象ファイル:

- `apps/api/app/models/schemas.py`
- `apps/api/app/services/ml/model_review.py`
- `apps/api/app/routers/model_workflows.py`

実装内容:

- `ModelReviewSummary`
- `ModelReviewResult`
- `ModelReviewAction`
- `ModelReviewComparison`
- `build_model_review_summary`
- classification / prediction の deterministic diagnostics

完了条件:

- Workflow ID から review summary を生成できる
- LLM なしでも fallback review を返せる

### Phase 2: LLM レビュー

対象ファイル:

- `apps/api/app/services/llm/nano_explainer.py`
- `apps/api/app/services/ml/model_review.py`

実装内容:

- `review_model_workflow_summary`
- OpenAI / Azure OpenAI 用 prompt
- JSON validation
- fallback
- source tracking

完了条件:

- `POST /api/model-workflows/{workflow_id}/review` で review result を生成できる
- LLM失敗時も fallback で UI が動く

### Phase 3: 提案状態管理

対象ファイル:

- `apps/api/app/routers/model_workflows.py`
- `apps/api/app/services/ml/model_review.py`

実装内容:

- active proposals
- resolved proposals
- proposal key
- Apply / Discard
- 同一提案の再表示抑止

完了条件:

- Apply / Discard 済み提案が再レビューで出続けない
- params が違う提案は別提案として扱う

### Phase 4: Apply & Retrain

対象ファイル:

- `apps/api/app/services/ml/model_review.py`
- `apps/api/app/services/ml/model_workflows.py`
- `apps/api/app/routers/model_workflows.py`

実装内容:

- proposal to request patch
- Workflow 再実行
- parent / child workflow state
- before / after comparison
- accepted 判定

完了条件:

- safe proposal を適用して新しい Workflow を作れる
- 比較結果を UI に返せる

### Phase 5: UI

対象ファイル:

- `apps/web/src/lib/api-client.ts`
- `apps/web/src/hooks/use-tabulens.ts`
- `apps/web/src/components/workflow-panel.tsx`
- `apps/web/src/components/model-review-modal.tsx`

実装内容:

- Model Review セクション
- Review Model ボタン
- Model Review modal
- proposal cards
- Apply & Retrain
- comparison view

完了条件:

- Workflow 完了後にレビューを実行できる
- レビュー結果と提案を確認できる
- 提案を適用して再学習できる

### Phase 6: artifact / export

対象ファイル:

- `apps/api/app/routers/model_workflows.py`

実装内容:

- review JSON 保存
- artifact zip への同梱
- export.xlsx に `model_review` sheet 追加

完了条件:

- モデル成果物だけで、学習設定・評価・レビュー・改善履歴を追える

### Phase 7: テスト

追加する検証:

- classification review summary
- prediction review summary
- fallback review
- proposal dedupe
- apply & retrain
- comparison accepted 判定
- artifact zip contents
- frontend build

最低限のコマンド:

```bash
apps/api/.venv/bin/python -m py_compile \
  apps/api/app/models/schemas.py \
  apps/api/app/services/ml/model_review.py \
  apps/api/app/routers/model_workflows.py

pnpm --dir apps/web build
```

## 15. 初期実装スコープ

最初に作るべき範囲:

1. classification / prediction の `ModelReviewSummary`
2. fallback review
3. LLM review
4. active / resolved proposal 管理
5. Workflow Panel の Model Review 表示
6. Apply & Retrain は `rebalance_classes`, `increase_test_size`, `switch_algorithm`, `normalize_features` から開始

後回しにする範囲:

- recommendation の本格評価
- clustering のセマンティックレビュー
- anomaly detection の既知ラベル評価 UI
- hyperparameter search の広範囲対応
- モデル昇格 / registry

## 16. 実装上の注意

- LLM に判断を丸投げしない
- 指標計算は必ずバックエンドで行う
- LLM の提案は allowlist された action だけ適用する
- Apply は既存 Workflow を破壊せず、新しい Workflow を作る
- 同じ提案が出続けないよう、Prepare QA と同じく `resolved` 管理を使う
- `safe_to_promote` は最終リリース判定ではなく、UI 上の参考値に留める
- `artifact.zip` にはレビュー結果を入れるが、API key や生データ全量は入れない

## 17. 完了条件

この機能の完了条件は次の通り。

- Workflow 実行後に Model Review を実行できる
- use case 別に妥当なレビューサマリを生成できる
- LLM または fallback でレビュー結果を返せる
- 改善提案を active proposals として表示できる
- Apply / Discard 済み提案は再表示されない
- safe な提案を適用して Workflow を再実行できる
- Before / After の比較で改善有無を確認できる
- review 結果が artifact / export に保存される
- フロントエンドでレビュー、提案、再実行、比較まで確認できる
