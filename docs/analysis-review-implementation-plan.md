# TabuLens 分析レビュー 実装計画

この文書は、現在の TabuLens 実装を起点にした、分析レビュー機能の実装計画である。  
現在の方針は、特定の分類アルゴリズムや説明生成に閉じず、**分析結果の妥当性レビュー → 改善提案 → 安全な再適用 → 再分析比較** を中核に置く。

## 1. 目的

TabuLens は、表形式データを取り込み、分類・回帰・クラスタリングなどの分析結果をレビューするためのアプリケーションである。  
本計画の目的は、単に「結果を出す」ことではなく、次の問いに答えられる実装にすること。

- この分析は、入力データの特徴をうまく捉えているか
- 分類・予測・クラスタリングなどの結果は妥当か
- 飛び地・外れ値・欠損・特徴量の選び方など、何が阻害要因になっているか
- 何を変えれば改善するか
- その改善を安全に適用した場合、結果は本当に良くなるか

## 2. 現状実装

現在のコードベースでは、最低限の導線は存在している。

- 表形式ファイルのアップロード
- シート一覧と列プレビューの取得
- 分析ジョブ実行
- 結果行の取得
- 分析結果のエクスポート
- バックエンド側での正規化、分類、飛び地検出
- LLM 連携のための環境設定

現在の主な API は以下。

- `POST /api/workbooks/upload`
- `GET /api/workbooks/{workbook_id}`
- `GET /api/workbooks/{workbook_id}/sheets/{sheet_name}/preview`
- `POST /api/jobs/run`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/rows`
- `GET /api/jobs/{job_id}/export.xlsx`

## 3. 設計原則

### 3.1 LLM の役割

LLM は数値処理の主担当にしない。  
LLM の役割は、分析結果を見て次を判断することに限定する。現在の実装では OpenAI / Azure OpenAI を利用するが、設計上は LLM provider を差し替えられる前提にする。

- 分類結果が妥当か
- 飛び地や外れ値が学習を阻害しているか
- 特徴量の選び方に問題がないか
- 何を改善候補にすべきか
- その改善候補を自動適用してよいか

### 3.2 バックエンド分析処理の役割

バックエンド分析処理は deterministic な処理を担当する。現在の実装では Python がこの責務を持つ。

- 欠損処理
- 正規化
- 分類・回帰・クラスタリング
- 次元圧縮 / 密度ベース検出
- 特徴量重要度
- 改善案の適用
- 再分析
- before / after 比較

### 3.3 安全性

- LLM に生データ全量は渡さない
- 自動適用は安全なものだけに限定する
- 危険な操作は必ずユーザー確認を挟む
- 改善案は必ず再分析して検証する

## 4. 目標ワークフロー

1. 表形式ファイルをアップロードする
2. シートと列を確認する
3. 特徴量・ラベル・除外列を設定する
4. 分析を実行する
5. 結果をレビュー用サマリに変換する
6. LLM が分析妥当性と阻害要因を判定する
7. 改善提案を生成する
8. 安全な提案だけを適用する
9. 再分析して before / after を比較する
10. 必要なら人間が最終判断する
11. 分析結果をエクスポートする

## 5. 機能方針

### 5.1 レビュー対象

LLM に見せるのは、行単位の生データではなく集約済みサマリに限定する。

含める情報の候補:

- 行数
- 特徴量数
- ラベル列名
- 欠損率
- 外れ値率
- 各クラスの件数
- 特徴量重要度
- 予測確信度の分布
- 飛び地クラスタ数
- 小規模クラスタ数
- 代表サンプル数件

### 5.2 レビュー出力

LLM の出力は自然文だけにしない。機械可読 JSON を返す。

推奨フィールド:

- `assessment`
- `confidence`
- `blocking_factors`
- `recommended_actions`
- `safe_to_apply`
- `reason`

### 5.3 改善提案

提案対象は次のようなもの。

- 飛び地クラスタの除外
- 外れ値行の除外
- 欠損処理の変更
- 特徴量の除外
- 特徴量しきい値の変更
- 正規化方式の変更
- モデル切り替え
- ラベル定義の見直し

### 5.4 自動適用

自動適用してよいのは、再現性が高く、影響範囲が読めるものだけ。

自動適用候補:

- 定数列の除外
- 空列の除外
- 低分散列の除外
- 明らかな重複列の除外

要承認候補:

- 飛び地クラスタの除外
- 外れ値行の削除
- 特徴量セットの変更
- ラベル列の再定義

## 6. 実装フェーズ

### Phase 0: レビュー用サマリ基盤

目的:

- 分析結果を LLM 向け JSON に変換する
- サマリは短く、安定した構造にする

追加内容:

- `analysis_summary` 生成関数
- 予測確信度の集計
- 欠損率 / 外れ値率 / 飛び地率の集計
- 代表行サンプリング

完了条件:

- 1 回の分析からレビュー用サマリ JSON を生成できる
- サマリは全件データに依存しない

### Phase 1: LLM レビュー API

目的:

- サマリを LLM に渡してレビュー判定を返す

追加内容:

- `POST /api/jobs/{job_id}/review`
- レビュー結果の JSON スキーマ
- LLM 呼び出しラッパー

完了条件:

- 分析結果に対して `keep / disable / review_manually / needs_more_data` のような判定が返る
- LLM が利用できない場合はフォールバック動作になる

### Phase 2: 改善提案の適用エンジン

目的:

- LLM の提案をバックエンド側で安全に適用する

追加内容:

- 提案種別ごとの適用ロジック
- 変更前後の差分記録
- 適用候補の承認フラグ

完了条件:

- 1 つ以上の改善提案を適用できる
- 適用履歴が残る

### Phase 3: 再分析と比較

目的:

- 改善提案が実際に良かったかを比較する

追加内容:

- `before` / `after` の比較情報
- 精度、確信度、飛び地数、外れ値数の比較
- 採用 / 不採用の判定

完了条件:

- 改善前後の差分が見える
- 悪化した場合にロールバックできる

### Phase 4: レビュー UI

目的:

- 人間がレビュー内容と改善提案を理解し、操作できるようにする

追加内容:

- 分析レビューサマリ表示
- LLM 判定表示
- 改善提案一覧
- 適用ボタン
- 再分析結果表示
- before / after 比較表示

完了条件:

- 1 画面で「見て、判断して、適用して、比較する」流れが完結する

### Phase 5: 永続化と監査

目的:

- 後から検証できるようにする

追加内容:

- レビュー結果の保存
- 改善提案の保存
- 適用済み・破棄済み提案を `resolved` 履歴として保存し、同じ提案を active list に再表示しない
- 再分析結果の保存

完了条件:

- どの提案をいつ誰が適用したか追跡できる

### Phase 6: テストと品質保証

目的:

- レビュー/改善ループが壊れないことを確認する

追加内容:

- サマリ生成テスト
- LLM 出力の JSON 契約テスト
- 改善提案適用テスト
- 再分析比較テスト
- API 経路テスト

完了条件:

- 代表ワークブックで end-to-end のスモークが通る

## 7. API 設計

現状の API に加えて、次を追加する。

### 7.1 Review

- `GET /api/jobs/{job_id}/review-summary`
- `POST /api/jobs/{job_id}/review`
- `GET /api/jobs/{job_id}/review`

### 7.2 Proposals

- `POST /api/jobs/{job_id}/proposals`
- `POST /api/jobs/{job_id}/proposals/{proposal_id}/apply`
- `POST /api/jobs/{job_id}/proposals/{proposal_id}/discard`

### 7.3 Re-run

- `POST /api/jobs/{job_id}/rerun`
- `GET /api/jobs/{job_id}/compare`

### 7.4 Export

既存の `GET /api/jobs/{job_id}/export.xlsx` を継続使用する。

## 8. データ列設計

結果テーブルには、元データに加えてレビュー・改善のための列を持たせる。

現状または追加候補:

- `_row_id`
- `_predicted_class`
- `_prediction_confidence`
- `_cluster_id`
- `_is_island`
- `_is_outlier`
- `_nearest_major_class`
- `_review_priority`
- `_nano_decision`
- `_nano_reason`
- `_nano_recommended_action`
- `_human_decision`
- `_human_note`

今後の改善候補:

- `_review_assessment`
- `_proposed_action`
- `_applied_action`
- `_before_after_delta`

## 9. LLM 入出力契約

### 9.1 入力

LLM には次のような要約を渡す。

```json
{
  "job_id": "uuid",
  "row_count": 12000,
  "feature_count": 18,
  "label_column": "label",
  "class_distribution": [
    { "class": "A", "count": 8000 },
    { "class": "B", "count": 2000 }
  ],
  "missing_rate": 0.08,
  "outlier_rate": 0.03,
  "island_clusters": [
    { "cluster_id": "cluster_3", "size": 12, "review_priority": 92 }
  ],
  "feature_importance_top": [
    { "feature": "pressure", "score": 0.31 },
    { "feature": "temperature", "score": 0.24 }
  ],
  "prediction_confidence": {
    "mean": 0.74,
    "p10": 0.48,
    "p90": 0.93
  }
}
```

### 9.2 出力

```json
{
  "assessment": "needs_improvement",
  "confidence": 0.78,
  "blocking_factors": [
    "外れ値が多く分類境界を歪めている",
    "特徴量の一部がノイズになっている"
  ],
  "recommended_actions": [
    {
      "action": "remove_outliers",
      "target": "cluster_3",
      "safe_to_apply": false
    }
  ],
  "reason": "..."
}
```

## 10. 環境設定

LLM 設定はアプリケーション固有の環境設定を正とする。現在の実装では `apps/api/.env` に Azure OpenAI の設定を置く。

現在の Azure OpenAI 実装で必要なキー:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT_NAME`
- `AZURE_OPENAI_API_VERSION`

`../composia-ui/.env` は移行用の参照先としては残せるが、TabuLens 側の標準は `apps/api/.env` に寄せる。将来 LLM provider を変える場合は、設定キーを provider ごとに分離する。

## 11. リスク

- LLM が判断を誤る可能性がある
- 改善提案をそのまま適用すると精度が悪化する可能性がある
- クラスタ検出はデータ分布に依存する
- LLM 呼び出しの遅延や失敗が UX を阻害する可能性がある
- ローカル保存のままだとジョブ再起動時に履歴が失われる

## 12. 完了条件

この実装計画が完了したと見なせる条件は次の通り。

- 分析結果のレビュー用サマリが生成できる
- LLM が分析の妥当性を判定できる
- LLM の改善提案をバックエンドが安全に適用できる
- 改善前後の比較ができる
- UI からレビューと改善適用ができる
- エクスポート結果にレビュー内容を反映できる
- 代表データで end-to-end の動作確認が通る

## 13. 実装順

実装は次の順で進める。

1. レビュー用サマリ生成
2. LLM レビュー API
3. 改善提案の適用エンジン
4. 再分析と比較
5. レビュー UI
6. 永続化と監査
7. テストとスモーク

## 14. 関連計画

予測モデル、異常検知、レコメンド、クラスタリング、ノイズ除去などの用途選択型モデル処理は [モデルワークフロー実装計画](./model-workflow-implementation-plan.md) で扱う。  
本計画は、既存データに対する分析結果の妥当性レビューと改善ループに責務を限定する。
