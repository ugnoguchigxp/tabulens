# TabuLens

TabuLens は、Excel / CSV の表形式データを使って「このデータで ML が効きそうか」を短時間で当たり付けするローカル解析ツールです。  
主目的は **ML feasibility check** であり、本格的な AutoML platform やモデル運用基盤ではありません。
データはローカル実行を前提とし、`Explore` で判断、`Workflow` で詳細検証を行います。
MVP の主導線は `Prepare`・`Explore`・`Workflow` の 3 つです。

- `Prepare`: クレンジングと特徴量重要度の可視化
- `Explore`: Data Profile / Target Feasibility / Quick Model Sweep / Exploration Evaluation
- `Workflow`: 分類・回帰・異常検知・クラスタリングの実行

## 現在の方針

- Review パネル / Review モーダルは廃止済み
- モデルファイルのダウンロード導線は廃止済み
- 特徴量重要度は表示のみで、自動 feature drop はしない
- 低重要度列の削除は UI からの手動操作で行う

## 主な機能

- Excel / CSV インポート
  - `.xlsx` と `.csv` をサポート
  - `.xlsx` は複数シート対応
  - 各シートの列型、欠損数、全行、プレビューを取得
- グリッド編集
  - AG Grid ベースで閲覧・編集
  - 行追加 / 行削除 / 列追加 / 列削除 / セルクリア
  - `=...` 形式の数式入力（計算結果表示 + raw formula 保持）
  - `Recalc` による volatile 関数の明示再計算
- Mapping Settings
  - `ID Column` / `Label Column` / `Features` を指定
  - Label に指定した列は特徴量から自動除外
- Prepare
  - 欠損処理、正規化、外れ値除去
  - 特徴量重要度の算出（自動ドロップなし）
- Feature Insights からの手動 drop
  - 重要度 20% 以下の列に `Drop column` ボタンを表示
  - 実データ列と特徴量マッピングの双方から除外
- Explore
  - `data_profile`
  - `target_feasibility`
  - `model_sweep`
  - `evaluation`（signal / viability / verdict / risk flags / next actions）
- Workflow
  - `classification` / `prediction` / `anomaly_detection` / `clustering`
  - 実行結果と指標を右パネル表示
  - `.xlsx` エクスポート
  - `PREDICT()` 用の推論 API（workflow artifact 利用）
- Boundary Graph
  - 分類ワークフローで表示可能
- Charts
  - 計算結果の numeric 列から line / bar / scatter を表示

## 対応ワークフロー

| Use Case | 目的 | 主な入力 | 主な出力 |
| --- | --- | --- | --- |
| `classification` | カテゴリラベル分類 | `label_column`, `feature_columns` | `_split_role`, `_predicted_class`, `_prediction_confidence`, `_is_correct`, `_error_flag` |
| `prediction` | 数値ターゲット予測 | `label_column`, `feature_columns` | `_split_role`, `_predicted_value`, `_actual_value`, `_residual`, `_absolute_error`, `_error_flag` |
| `anomaly_detection` | 異常行の検出 | `feature_columns` | `_anomaly_score`, `_is_anomaly`, `_anomaly_rank`, `_anomaly_reason` |
| `clustering` | ラベルなしデータのクラスタ分割 | `feature_columns` | `_cluster_id`, `_cluster_size`, `_distance_to_centroid`, `_is_noise` |

## リポジトリ構成

```txt
tabulens/
├── apps/
│   ├── api/          # FastAPI backend
│   └── web/          # React + TypeScript frontend
├── docs/
├── storage/
│   ├── uploads/
│   └── results/
└── README.md
```

## 技術スタック

### Backend

- FastAPI
- Pandas
- scikit-learn
- Openpyxl
- Pydantic

### Frontend

- React 19
- TypeScript
- Vite
- AG Grid Community
- TanStack Query
- Tailwind CSS
- Radix UI

## セットアップ

### 前提

- Python 3.10+
- Node.js 18+
- pnpm

### クイックスタート

ルートディレクトリで以下のコマンドを実行するだけで、フロントエンドのビルドからサーバーの起動まで一括で行われます。

```bash
pnpm install
pnpm start
```

起動後、 [http://localhost:8000](http://localhost:8000) にアクセスしてください。

> [!NOTE]
> このコマンドは自動的に Python の仮想環境（`.venv`）を作成し、必要なパッケージをインストールします。

### 個別に起動する場合（開発用）

フロントエンドのホットリロードなどが必要な場合は、個別に起動することも可能です。

**Backend:**
```bash
cd apps/api
# 初回のみ: python3 -m venv .venv && source .venv/bin/activate && pip install -e .
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd apps/web
pnpm install
pnpm dev
```

## 基本的な使い方

1. `.xlsx` / `.csv` をアップロード
2. 対象シートを選択
3. Mapping（ID / Label / Features）を設定
4. `Prepare` を実行して前処理と重要度確認
5. 必要なら Feature Insights から低重要度列を手動 `Drop column`
6. `Explore` で探索評価を確認
7. `Workflow` を実行して詳細結果を確認

## API 概要

### Workbooks

| Method | Path | 内容 |
| --- | --- | --- |
| `POST` | `/api/workbooks/upload` | `.xlsx` / `.csv` のアップロード |
| `GET` | `/api/workbooks/{workbook_id}` | workbook 取得 |
| `GET` | `/api/workbooks/{workbook_id}/sheets/{sheet_name}/preview` | 先頭 10 行プレビュー |
| `GET` | `/api/workbooks/{workbook_id}/sheets/{sheet_name}/rows?offset=0&limit=100` | 行ページ取得 |
| `GET` | `/api/workbooks/{workbook_id}/sheets/{sheet_name}/profile` | シート統計取得 |
| `GET` | `/api/workbooks/{workbook_id}/formulas` | workbook 内 formula metadata 取得 |

### Prepare Jobs

| Method | Path | 内容 |
| --- | --- | --- |
| `POST` | `/api/jobs/run` | Prepare 実行 |
| `GET` | `/api/jobs/{job_id}` | Job ステータスと metadata |
| `GET` | `/api/jobs/{job_id}/rows` | Prepare 結果行 |
| `GET` | `/api/jobs/{job_id}/boundary` | 分類境界グラフ用データ |
| `GET` | `/api/jobs/{job_id}/export.xlsx` | Prepare 結果エクスポート |

### Model Workflows

| Method | Path | 内容 |
| --- | --- | --- |
| `POST` | `/api/model-workflows/run` | Workflow 実行 |
| `GET` | `/api/model-workflows/{workflow_id}` | Workflow 全体結果 |
| `GET` | `/api/model-workflows/{workflow_id}/rows` | 結果行 |
| `GET` | `/api/model-workflows/{workflow_id}/metrics` | 指標 |
| `GET` | `/api/model-workflows/{workflow_id}/boundary` | 分類境界グラフ用データ |
| `POST` | `/api/model-workflows/{workflow_id}/predict` | workflow artifact で推論 |
| `GET` | `/api/model-workflows/{workflow_id}/export.xlsx` | Workflow エクスポート |

### Explorations

| Method | Path | 内容 |
| --- | --- | --- |
| `POST` | `/api/explorations/run` | `data_profile` / `target_feasibility` / `model_sweep` / `evaluation` を返す |

## 開発コマンド

### Backend

```bash
cd apps/api
.venv/bin/python -m pytest -q
```

### Frontend

```bash
cd apps/web
pnpm lint
pnpm test -- --run
pnpm build
```

## 関連ドキュメント

- [探索評価機能 実装計画](docs/exploration-evaluation-implementation-plan.md)
- [Calc Engine 実装計画](docs/calc-engine-implementation-plan.md)
- [対応数式一覧](docs/supported-formulas.md)

## 数式メタデータ方針

- `.xlsx` upload 時に formula metadata（`sheet_name`, `address`, `formula`, `cached_value`）を保存
- Prepare / Workflow の export には `formulas` sheet を同梱
- 表示値と formula は別責務として保持し、formula 追跡は `formulas` sheet で行う

## ライセンス

AG Grid は Community 版を利用。Excel 出力は backend 側で生成。  
© 2026 y.noguchi
