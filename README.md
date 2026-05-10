# TabuLens

TabuLens は、Excel / CSV の表形式データを取り込み、列マッピング、データクレンジング、特徴量抽出、分類・予測、異常検知、クラスタリング、レコメンド、ノイズ除去、AI レビューを一つの画面で確認するためのデータ分析支援アプリです。

現在の実装は大きく 2 系統に分かれています。

- `Prepare`: 学習前のクレンジング、特徴量重要度、不要カラム候補、OpenAI / Azure OpenAI による前処理レビューと改善提案を扱う。
- `Workflow`: Prepare 済みデータを入力にして、分類、予測モデル生成、異常検知、レコメンド、クラスタリング、ノイズ除去を用途別に実行する。

## 主な機能

- Excel / CSV インポート
  - `.xlsx` と `.csv` に対応。
  - Excel は複数シートを扱える。
  - 各シートの `row_count`、列型、欠損数、全行データ、先頭プレビューを返す。
- Excel ライクな表表示
  - AG Grid Community を使い、列ソート、横スクロール、ページング付きで表示する。
  - インポート直後の表示はプレビューではなく、取得済み行数に基づいて扱う。
- Mapping Settings
  - `ID Column`、`Label Column`、`Features` を画面左側で指定する。
  - Feature はチップをクリックして有効 / 無効を切り替える。
  - Label に選んだ列は特徴量から自動的に除外する。
- Prepare
  - 欠損処理、正規化、外れ値除去、特徴量重要度の計算。
  - 学習前に不要カラム候補、リーク疑い、欠損・外れ値の影響を確認する。
  - OpenAI / Azure OpenAI で前処理結果をレビューし、改善提案を生成する。
  - 提案は Apply / Discard でき、適用済み・破棄済みの提案は解決済み履歴として保持し、同じ提案を再表示しない。
- Workflow
  - 用途を `classification` / `prediction` / `anomaly_detection` / `recommendation` / `clustering` / `noise_reduction` から選択できる。
  - 用途ごとに必要な列、アルゴリズム、評価指標、出力列を切り替える。
  - Prepare 完了後にだけ実行でき、処理済みデータを入力にして学習・検証する。
  - 実行結果は右側の Workflow パネルと表データに反映する。
  - 結果とメトリクスを `.xlsx` としてエクスポートできる。
  - 分類Workflowでは境界グラフを表示できる。
  - 学習済みモデル、モデル pipeline、設定、評価指標、予測結果を `model_artifact.zip` としてダウンロードできる。

## 対応ワークフロー

| Use Case | 目的 | 主な入力 | 主な出力 |
| --- | --- | --- | --- |
| `classification` | 教師あり学習でカテゴリラベルを分類し、学習 / 検証分割で精度を確認する | `label_column`, `feature_columns` | `_split_role`, `_predicted_class`, `_prediction_confidence`, `_is_correct`, `_error_flag` |
| `prediction` | 教師あり学習で数値ターゲットを予測し、残差や誤差を確認する | `label_column`, `feature_columns` | `_split_role`, `_predicted_value`, `_actual_value`, `_residual`, `_absolute_error`, `_error_flag` |
| `anomaly_detection` | 通常パターンから外れる行を検出する | `feature_columns` | `_anomaly_score`, `_is_anomaly`, `_anomaly_rank`, `_anomaly_reason` |
| `recommendation` | ユーザーや対象物に対して推薦候補を出す | `user_id_column`, `item_id_column`, optional `rating_column` | `_recommended_item_id`, `_recommendation_score`, `_rank`, `_recommendation_reason` |
| `clustering` | ラベルなしデータをグループ化する | `feature_columns` | `_cluster_id`, `_cluster_size`, `_distance_to_centroid`, `_is_noise` |
| `noise_reduction` | ノイズ候補行を検出し、必要に応じて除外した結果を作る | `feature_columns` | `_noise_score`, `_is_noise_candidate`, `_noise_reason`, `_applied_action` |

## アーキテクチャ

```txt
tabulens/
├── apps/
│   ├── api/          # FastAPI backend
│   └── web/          # React + TypeScript frontend
├── docs/             # 設計・実装計画
├── storage/
│   ├── uploads/      # アップロードされた xlsx / csv
│   └── results/      # 分析・ワークフロー結果
└── README.md
```

### Backend

- FastAPI
- Pandas
- Scikit-learn
- Openpyxl
- Pydantic
- ファイルベースのアップロード / 結果保存

### Frontend

- React 19
- TypeScript
- Vite
- AG Grid Community
- TanStack Query
- Tailwind CSS
- Radix UI primitives
- Lucide icons

## セットアップ

### 前提

- Python 3.10+
- Node.js
- pnpm

### Backend

API はフロントエンドの既定設定に合わせて `http://localhost:18273/api` で起動する想定です。

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 18273
```

### OpenAI / Azure OpenAI 設定

AI レビューは Azure OpenAI 設定がある場合に利用します。設定がない場合はルールベースの fallback を返します。

このリポジトリでは、次の順で `.env` を探します。

1. `apps/api/.env`
2. 起動時のカレントディレクトリの `.env`
3. `../composia-ui/.env`

必要なキー:

```bash
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_DEPLOYMENT_NAME=...
AZURE_OPENAI_API_VERSION=...
```

`../composia-ui/.env` の設定を使う場合でも動作します。リポジトリ内で明示したい場合は `apps/api/.env` にコピーしてください。

### Frontend

フロントエンドは `http://localhost:29384` で起動します。

```bash
cd apps/web
pnpm install
pnpm dev
```

API の URL を変える場合は、フロントエンド起動時に `VITE_API_BASE_URL` を指定してください。

```bash
VITE_API_BASE_URL=http://localhost:18273/api pnpm dev
```

## 基本的な使い方

1. 右上のアップロードボタンから `.xlsx` または `.csv` を取り込む。
2. 左上のシート選択で対象シートを選ぶ。
3. 左側の Mapping Settings で `ID Column`、`Label Column`、`Features` を指定する。
4. 学習前のクレンジング、特徴量選択、AI レビューを行う場合は `Prepare` を押す。
5. Prepare が完了したら `Workflow` を押す。
6. Workflow で分類、予測、異常検知、レコメンド、クラスタリング、ノイズ除去の用途を選んで実行する。
7. 結果は表、Prepare Review パネル、Workflow パネル、エクスポートファイルで確認する。

## API 概要

### Workbooks

| Method | Path | 内容 |
| --- | --- | --- |
| `POST` | `/api/workbooks/upload` | `.xlsx` / `.csv` をアップロードする |
| `GET` | `/api/workbooks/{workbook_id}` | 保存済み workbook を取得する |
| `GET` | `/api/workbooks/{workbook_id}/sheets/{sheet_name}/preview` | 先頭 10 行のプレビューを取得する |

### Prepare Jobs

| Method | Path | 内容 |
| --- | --- | --- |
| `POST` | `/api/jobs/run` | 学習前処理ジョブを実行する |
| `GET` | `/api/jobs/{job_id}` | ジョブ概要を取得する |
| `GET` | `/api/jobs/{job_id}/rows` | 前処理結果行を取得する |
| `GET` | `/api/jobs/{job_id}/review-summary` | AI レビュー用サマリを取得する |
| `GET` | `/api/jobs/{job_id}/review` | AI レビュー結果を取得する |
| `POST` | `/api/jobs/{job_id}/review` | AI レビューを再実行する |
| `GET` | `/api/jobs/{job_id}/proposals` | 改善提案一覧を取得する |
| `POST` | `/api/jobs/{job_id}/proposals/{proposal_id}/apply` | 改善提案を適用して再分析する |
| `POST` | `/api/jobs/{job_id}/proposals/{proposal_id}/discard` | 改善提案を破棄する |
| `POST` | `/api/jobs/{job_id}/rerun` | 複数提案を指定して再分析する |
| `GET` | `/api/jobs/{job_id}/compare` | 適用前後の比較を取得する |
| `GET` | `/api/jobs/{job_id}/boundary` | 分類境界グラフ用データを取得する |
| `GET` | `/api/jobs/{job_id}/export.xlsx` | 分析結果を `.xlsx` で取得する |

### Model Workflows

| Method | Path | 内容 |
| --- | --- | --- |
| `POST` | `/api/model-workflows/run` | 用途別ワークフローを実行する |
| `GET` | `/api/model-workflows/{workflow_id}` | ワークフロー結果を取得する |
| `GET` | `/api/model-workflows/{workflow_id}/rows` | 結果行を取得する |
| `GET` | `/api/model-workflows/{workflow_id}/metrics` | 評価指標を取得する |
| `GET` | `/api/model-workflows/{workflow_id}/export.xlsx` | 結果とメトリクスを `.xlsx` で取得する |
| `GET` | `/api/model-workflows/{workflow_id}/artifact.zip` | 学習済みモデル成果物を `.zip` で取得する |

## 開発用コマンド

### Backend 構文チェック

```bash
python3 -m py_compile \
  apps/api/app/models/schemas.py \
  apps/api/app/services/ml/model_factory.py \
  apps/api/app/services/ml/model_workflows.py \
  apps/api/app/routers/model_workflows.py \
  apps/api/app/services/workbook_loader.py \
  apps/api/app/services/ml/classifier.py \
  apps/api/app/main.py
```

### Frontend ビルド

```bash
pnpm --dir apps/web build
```

## 関連ドキュメント

- [モデルワークフロー実装計画](docs/model-workflow-implementation-plan.md)
- [分析レビュー実装計画](docs/analysis-review-implementation-plan.md)
- [学習後レビュー実装計画](docs/model-review-implementation-plan.md)

## ライセンス方針

AG Grid は Community 版を前提にしています。Enterprise 版の Excel Export には依存せず、Excel ファイル生成はバックエンドの Python / Openpyxl で行います。

© 2026 y.noguchi
