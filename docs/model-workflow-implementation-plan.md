# TabuLens モデルワークフロー 実装計画

この文書は、TabuLens で **Prepare 済みデータを入力にして、用途を選んでモデル処理を実行できる機能** の実装計画である。

現在の実装は、学習前準備を行う `Prepare` と、学習・検知・推薦などを行う `Workflow` に分ける方向へ整理している。Workflow は Prepare 完了後にだけ実行でき、ユーザーが目的を選び、それに応じて必要な列設定、アルゴリズム、評価指標、出力、保存成果物を切り替えられるようにする。

## 1. 目的

TabuLens のモデルワークフローでは、次の用途を選択できる状態を目指す。

- 分類モデル生成
- 予測モデル生成
- 異常検知
- レコメンド
- クラスタリング
- ノイズ除去

重要なのは、すべての用途を分類問題として扱わないことである。  
用途ごとに、必要な入力列、評価方法、出力列、保存する成果物が異なるため、最初に `use_case` を選ぶ設計にする。

## 2. 現状

現在の実装には、以下が存在する。

- 表形式ファイルのアップロード
- シートと列のマッピング
- Prepare ジョブの実行
- クレンジング、特徴量重要度、飛び地検出
- Prepare レビューと改善提案
- Workflow による用途別モデル実行
- 結果とモデル成果物のエクスポート

現在の Prepare 処理は `apps/api/app/services/ml/classifier.py` を使っているが、ML 実行は `run_ml=false` として学習前準備に限定する。
モデルワークフローでは、分類だけではなく、用途ごとのモデル実行を扱うため、`classifier.py` に機能を足し続けるのではなく、用途別のサービスへ分ける。

## 3. 設計原則

### 3.1 最初に用途を選ぶ

UI と API の入口で `use_case` を選ぶ。

- `classification`
- `prediction`
- `anomaly_detection`
- `recommendation`
- `clustering`
- `noise_reduction`

選ばれた用途に応じて、必要な設定だけを表示・送信する。  
例えば、クラスタリングや異常検知では `Label Column` は必須ではない。レコメンドでは `user_id`、`item_id`、`rating` または interaction 列が重要になる。

### 3.2 用途ごとに評価方法を変える

分類と同じ評価指標を全用途に流用しない。

- 分類モデル: accuracy、balanced accuracy、precision、recall、F1、confusion matrix
- 予測モデル: holdout / cross-validation の精度、MAE、RMSE、R2、残差分布
- 異常検知: anomaly score、検知件数、既知ラベルがある場合の precision / recall
- レコメンド: precision@k、recall@k、coverage、人気偏り
- クラスタリング: silhouette score、cluster size、noise ratio
- ノイズ除去: 除去件数、残存件数、除去理由、前後比較

### 3.3 supervised と unsupervised を分ける

予測モデルは教師あり学習を基本にする。  
異常検知、クラスタリング、ノイズ除去はラベルなしでも実行できる。  
ただし、ラベルや正解フラグがある場合は評価に使えるようにする。

### 3.4 前処理は共通化し、fit / transform を分ける

用途に関係なく、欠損処理、カテゴリ変換、スケーリング、列除外は共通基盤にする。  
教師あり評価では、学習データだけで fit し、検証データには transform のみ適用する。

### 3.5 成果物は用途ごとに保存する

モデル、設定、評価指標、結果行、エクスポート情報を `model_job` として保存する。  
予測モデルだけでなく、異常検知モデル、クラスタリング結果、ノイズ除去ルールも成果物として扱う。

## 4. 想定ワークフロー

1. 表形式ファイルをアップロードする
2. シートを選ぶ
3. `Prepare` でクレンジング、特徴量選択、不要カラム候補、AI レビューを実行する
4. Prepare 提案を Apply / Discard し、処理済みデータを作る
5. `Workflow` で用途を選ぶ
6. 用途に応じた列設定を行う
7. アルゴリズムを選ぶ
8. 必要なら学習 / 検証分割を設定する
9. モデルワークフローを実行する
10. 用途別の結果と評価指標を確認する
11. 成果物を保存またはエクスポートする

## 5. 用途別仕様

### 5.1 分類モデル生成

目的:

- カテゴリラベルを分類するモデルを作る
- 未使用データで分類精度を確認する
- 良いモデルを保存して再利用する

必要な列:

- `label_column`
- `feature_columns`
- 任意の `id_column`

主な設定:

- `train_size`
- `test_size`
- `split_mode`: `count` または `ratio`
- `shuffle`
- `stratify`
- `random_state`

主なアルゴリズム:

- Random Forest
- Gradient Boosting
- SVM
- Logistic Regression

出力:

- `_split_role`
- `_predicted_class`
- `_prediction_confidence`
- `_is_correct`
- `_error_flag`

評価:

- accuracy
- balanced accuracy
- precision
- recall
- F1
- confusion matrix

### 5.2 予測モデル生成

目的:

- 数値ターゲットを予測するモデルを作る
- 未使用データで予測誤差を確認する
- 良いモデルを保存して再利用する

必要な列:

- `label_column`
- `feature_columns`
- 任意の `id_column`

主な設定:

- `train_size`
- `test_size`
- `split_mode`: `count` または `ratio`
- `shuffle`
- `random_state`

主なアルゴリズム:

- Random Forest
- Gradient Boosting
- SVM
- Linear Regression

出力:

- `_split_role`
- `_predicted_value`
- `_actual_value`
- `_residual`
- `_absolute_error`
- `_error_flag`

評価:

- MAE
- RMSE
- R2
- 残差分布

### 5.3 異常検知

目的:

- 通常パターンから外れる行を検出する
- 異常スコアと理由を付与し、レビュー対象を絞る

必要な列:

- `feature_columns`
- 任意の `id_column`
- 任意の `known_anomaly_label`

主な設定:

- `algorithm`: isolation forest、local outlier factor、one-class SVM など
- `contamination`: 想定異常率
- `threshold_mode`: 自動、パーセンタイル、手動しきい値

出力:

- `_anomaly_score`
- `_is_anomaly`
- `_anomaly_rank`
- `_anomaly_reason`
- `_review_priority`

評価:

- 既知ラベルなし: 検知件数、score 分布、上位異常行
- 既知ラベルあり: precision、recall、F1、confusion matrix

### 5.4 レコメンド

目的:

- ユーザーや対象物に対して推薦候補を生成する
- 推薦結果の妥当性、偏り、カバレッジを確認する

必要な列:

- `user_id_column`
- `item_id_column`
- 任意の `rating_column`
- 任意の `timestamp_column`
- 任意の user / item feature columns

主な設定:

- `recommendation_type`: interaction、content-based、hybrid
- `top_k`
- `min_interactions`
- `evaluation_split`: random、leave-last-out、time-based

出力:

- `_recommended_item_id`
- `_recommendation_score`
- `_rank`
- `_recommendation_reason`

評価:

- precision@k
- recall@k
- hit rate
- coverage
- popularity bias

### 5.5 クラスタリング

目的:

- ラベルなしデータをグループ化する
- 似た行のまとまり、孤立クラスタ、ノイズを確認する

必要な列:

- `feature_columns`
- 任意の `id_column`

主な設定:

- `algorithm`: k-means、DBSCAN、hierarchical など
- `cluster_count`: 必要な場合のみ指定
- `distance_metric`
- `scale_features`

出力:

- `_cluster_id`
- `_cluster_size`
- `_distance_to_centroid`
- `_is_noise`
- `_is_small_cluster`

評価:

- silhouette score
- cluster size distribution
- noise ratio
- small cluster count
- 代表行

### 5.6 ノイズ除去

目的:

- 学習や分析を阻害する行・列を検出し、除外候補として提示する
- 除去前後で分析品質が改善するか確認する

必要な列:

- `feature_columns`
- 任意の `label_column`
- 任意の `id_column`

主な設定:

- `rules`: 欠損過多、定数列、低分散列、重複行、外れ値、孤立クラスタ
- `apply_mode`: preview、manual apply、自動適用
- `max_removal_ratio`

出力:

- `_noise_score`
- `_is_noise_candidate`
- `_noise_reason`
- `_proposed_action`
- `_applied_action`

評価:

- 除去候補数
- 除去後の行数 / 列数
- 除去前後の missing rate
- 除去前後のモデル指標またはクラスタ指標

## 6. UI 方針

### 6.1 用途選択

`Workflow` 画面で、最初に用途を選ぶ。`Prepare` は用途選択ではなく、学習前のデータ準備に限定する。

- Classification
- Prediction
- Anomaly
- Recommendation
- Clustering
- Noise Reduction

用途を選んだ後、列設定パネルを用途別に切り替える。

### 6.2 列設定

全用途で同じ `Label Column` / `Feature Columns` UI を使い回さない。

- Classification: categorical label + features
- Prediction: numeric target + features
- Anomaly: features + optional known anomaly label
- Recommendation: user + item + rating / interaction
- Clustering: features
- Noise Reduction: features + optional label

### 6.3 結果表示

結果表示は用途ごとに切り替える。

- Classification: metrics、holdout rows、confusion matrix
- Prediction: metrics、holdout rows、residual plot
- Anomaly: anomaly ranking、score distribution、上位異常行
- Recommendation: top-k recommendations、coverage、bias
- Clustering: cluster map、cluster table、代表行
- Noise Reduction: 除去候補、理由、before / after

## 7. API / データモデル

既存の分析 `jobs` に用途別処理を混ぜ込むより、モデルワークフロー用の API を追加する。

推奨する新しい領域:

- `apps/api/app/services/ml/preprocessing.py`
- `apps/api/app/services/ml/workflows/prediction.py`
- `apps/api/app/services/ml/workflows/anomaly_detection.py`
- `apps/api/app/services/ml/workflows/recommendation.py`
- `apps/api/app/services/ml/workflows/clustering.py`
- `apps/api/app/services/ml/workflows/noise_reduction.py`
- `apps/api/app/routers/model_workflows.py`

現在の実装 API:

- `POST /api/model-workflows/run`
- `GET /api/model-workflows/{workflow_id}`
- `GET /api/model-workflows/{workflow_id}/rows`
- `GET /api/model-workflows/{workflow_id}/metrics`
- `GET /api/model-workflows/{workflow_id}/export.xlsx`
- `GET /api/model-workflows/{workflow_id}/artifact.zip`

現在の実装 schema:

- `ModelWorkflowRequest`
- `UseCaseType`
- `ModelWorkflowResponse`
- `WorkflowMetrics`
- `WorkflowRowsResponse`

用途別の詳細設定は、現時点では専用 config schema ではなく `ModelWorkflowRequest.params` に集約している。
ただし UI では用途に応じて表示項目を切り替えるため、ユーザーが関係ない設定を直接触る必要はない。

`ModelWorkflowRequest` の基本形:

```json
{
  "workbook_id": "uuid",
  "sheet_name": "Data",
  "source_job_id": "prepare-job-id",
  "use_case": "classification",
  "mapping": {},
  "algorithm": "random_forest",
  "params": {}
}
```

## 8. 保存成果物

現在の実装では `storage/results/<workflow_id>/` に以下を保存する。

- `request.json`
- `metrics.json`
- `rows.csv`
- `rows.xlsx`
- `export.xlsx`
- 予測モデル生成では `model_artifact.zip`

用途別の保存物:

- Classification: `model.joblib`、`preprocessing.joblib`、`feature_columns.json`、`target_schema.json`、`training_config.json`、`metrics.json`、`predictions.xlsx`
- Prediction: `model.joblib`、`preprocessing.joblib`、`feature_columns.json`、`target_schema.json`、`training_config.json`、`metrics.json`、`predictions.xlsx`
- Anomaly: detector、score distribution、threshold
- Recommendation: recommender artifact、top-k 結果
- Clustering: cluster labels、centroids または representative rows
- Noise Reduction: rule set、除去候補、適用履歴

## 9. 実装フェーズ

### Phase 0: 用途選択と schema

目的:

- `use_case` を API と UI の中心に置く

追加内容:

- `UseCaseType`
- 用途別 config schema
- 用途別 mapping schema
- UI の用途選択

完了条件:

- 分類以外の用途を UI と API で選べる
- 不要な列設定が表示されない

### Phase 1: 共通前処理

目的:

- 用途ごとの処理から共通前処理を切り出す

追加内容:

- 欠損処理
- 数値 / カテゴリ列の分離
- encode / scale
- fit / transform 分離
- metadata 保存

完了条件:

- Prediction の train / test で leakage が起きない
- Unsupervised 系でも同じ前処理を使える

### Phase 2: Prediction

目的:

- ユーザー指定 split で予測モデルを学習・評価する

追加内容:

- classification
- regression
- holdout metrics
- prediction rows
- model artifact 保存

完了条件:

- 任意件数の train / test で評価できる

### Phase 3: Anomaly Detection / Clustering / Noise Reduction

目的:

- ラベルなしで動く主要用途を追加する

追加内容:

- 異常スコア
- クラスタ ID
- ノイズ候補
- before / after 指標

完了条件:

- ラベルがないデータでも有用な結果を返せる

### Phase 4: Recommendation

目的:

- user / item interaction を使った推薦結果を出す

追加内容:

- mapping UI
- top-k 推薦
- recommendation metrics
- coverage / bias 表示

完了条件:

- user / item / interaction の表から推薦候補を生成できる

### Phase 5: UI 統合

目的:

- 用途別の結果表示を 1 つの体験としてまとめる

追加内容:

- 用途選択
- 用途別設定パネル
- 用途別 metrics
- 結果テーブル
- エクスポート

完了条件:

- ユーザーが用途を選び、設定し、実行し、結果を確認できる

### Phase 6: テスト

目的:

- 用途別 workflow が壊れないことを確認する

追加内容:

- Classification の split / metrics テスト
- Prediction の regression split / metrics テスト
- Anomaly の score / threshold テスト
- Clustering の cluster label テスト
- Noise Reduction の適用前後テスト
- Recommendation の top-k テスト
- API 経路テスト

完了条件:

- 各 use case の代表データで smoke test が通る

## 10. 検証方針

最低限、以下のサンプルデータを用意する。

- Classification 用: カテゴリ label と features があるデータ
- Prediction 用: 数値 target と features があるデータ
- Anomaly 用: 明らかな外れ行を含むデータ
- Recommendation 用: user / item / interaction があるデータ
- Clustering 用: 複数クラスタ構造を持つデータ
- Noise Reduction 用: 欠損、重複、外れ値、低分散列を含むデータ

検証では次を確認する。

- 選択した use case に合う UI だけが出る
- 不足している列設定に対して明確な validation が出る
- 結果列が用途ごとに正しく付与される
- metrics が用途ごとに妥当である
- 成果物が保存・再取得・エクスポートできる
- 既存の分析レビュー機能を壊さない

## 11. リスク

- すべての用途を一度に実装しようとして UI と API が肥大化する
- 用途ごとの mapping validation が甘く、実行時エラーになる
- unsupervised 系の評価指標を精度のように誤解させる
- Recommendation はデータ形式のばらつきが大きく、最初から高機能化しすぎる
- ノイズ除去の自動適用がデータを壊す
- 既存の分類分析と新しい model workflow の責務が混ざる

## 12. 完了条件

この計画が完了したと言える条件は次の通り。

- 用途を `classification` / `prediction` / `anomaly_detection` / `recommendation` / `clustering` / `noise_reduction` から選べる
- 用途ごとに必要な列設定と config が切り替わる
- 各用途で結果行と metrics を返せる
- 成果物を保存・再取得できる
- 外部レビュー可能な形式へ結果を出力できる
- 既存の分析レビュー機能と共存できる

## 13. 関連計画

Prepare 結果の妥当性レビュー、改善提案、再実行比較は [分析レビュー実装計画](./analysis-review-implementation-plan.md) で扱う。
本計画は、ユーザーが用途を選択してモデル処理を実行し、その結果と成果物を確認・保存するための計画である。
