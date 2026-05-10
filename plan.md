以下は、**AG Grid Community / React / FastAPI / Python ML** を前提にしたプロジェクト計画書です。
方針は **AG Grid Enterprise に依存しない**、つまり `ag-grid-enterprise` を入れず、Excel import/export は Python 側で処理する設計です。

---

# プロジェクト計画書

## Excel分類・飛び地レビュー支援Webアプリ

## 1. 目的

Excelシートに含まれる大量の数値データを取り込み、正規化・機械学習分類・飛び地検出を行い、その結果をExcelライクなWeb UIで確認・修正・レビューできるアプリケーションを開発する。

主な目的は以下。

```txt
1. Excelファイルをアップロードする
2. 数値列を0〜1に正規化する
3. SVM / RandomForest 等で分類する
4. 飛び地・孤立クラスタ・外れ値候補を検出する
5. gpt-5.4-nano で判断コメント・推奨アクションを生成する
6. AG Grid Community で結果をExcelライクにレビューする
7. 最終結果を xlsx として出力する
```

---

## 2. ライセンス方針

### 2.1 使用するAG Grid範囲

本プロジェクトでは、AG Grid の **Community 版のみ**を使用する。

使用予定パッケージ:

```json
{
  "dependencies": {
    "ag-grid-community": "...",
    "ag-grid-react": "..."
  }
}
```

`ag-grid-community` は npm 上で MIT ライセンスとされ、Sorting、Filtering、Pagination、Editing、Custom Components、Theming などの core features を含むと説明されています。([npm][1])
`ag-grid-react` も React Data Grid 向けの Community パッケージとして、MIT の `ag-grid-community` を前提に提供されています。([npm][2])

### 2.2 使用しないもの

以下は使用しない。

```txt
ag-grid-enterprise
Excel Export Module
Range Selection Module
Row Grouping
Pivoting
Aggregation UI
Server-Side Row Model
Integrated Charts
Master / Detail
Advanced Filter
```

AG Grid は Community と Enterprise に分かれており、Enterprise には Row Grouping、Aggregation、Pivoting、Master/Detail、Server-side Row Model、Exporting、Integrated Charting などが含まれると説明されています。([npm.io][3])

### 2.3 Excel export の回避方針

AG Grid の Excel Export は Enterprise 機能です。公式ドキュメントでも Excel Export ページは Enterprise 機能として扱われ、Enterprise 版ではコンテキストメニューからExcel Exportを提供すると説明されています。([AG Grid][4])

そのため、本プロジェクトでは以下の設計にする。

```txt
AG Grid Community:
  画面表示
  ソート
  フィルタ
  セル編集
  CSV的なレビュー操作

FastAPI / openpyxl:
  Excel import
  Excel export
  result.xlsx 生成
```

---

## 3. 推奨技術スタック

## 3.1 フロントエンド

```txt
React + TypeScript
Vite または TanStack Start
AG Grid Community
TanStack Query
Zod
React Hook Form
```

### 推奨

MVPでは **Vite + React + TypeScript** を推奨。

理由:

```txt
SSR不要
Pythonバックエンドと役割分離しやすい
構成が軽い
AG Gridとの相性が良い
分析アプリとして十分
```

TanStack Start は、BFFや認証・サーバー関数を使いたくなった段階で検討する。

---

## 3.2 バックエンド

```txt
FastAPI
pandas
openpyxl
scikit-learn
pydantic
numpy
joblib
```

主な役割:

```txt
Excel読み込み
シート・列情報の抽出
欠損値処理
数値列の検出
MinMax正規化
SVM / RandomForest分類
飛び地検出
gpt-5.4-nano連携
result.xlsx生成
```

---

## 3.3 LLM

```txt
Azure OpenAI gpt-5.4-nano
```

役割:

```txt
飛び地クラスタの説明
外れ値候補の判断理由
レビュー優先度の提案
次に確認すべき項目の提案
Excel結果列に入れるコメント生成
```

LLMには数値処理そのものを任せない。
数値計算・分類・クラスタリングは Python 側で行い、nano は **判断コメント生成・レビュー補助**に限定する。

---

# 4. 全体アーキテクチャ

```txt
Browser
  |
  | Excel upload / settings / review
  v
React + AG Grid Community
  |
  | REST API
  v
FastAPI
  |
  | pandas / openpyxl
  | scikit-learn
  | Azure OpenAI gpt-5.4-nano
  v
Result files
  - result.json
  - result.xlsx
  - model.joblib
  - analysis_report.json
```

---

# 5. ディレクトリ構成

```txt
excel-classifier/
  apps/
    web/
      package.json
      vite.config.ts
      src/
        main.tsx
        App.tsx
        routes/
          HomePage.tsx
          JobPage.tsx
        components/
          UploadDropzone.tsx
          WorkbookPreview.tsx
          ColumnMappingPanel.tsx
          AnalysisSettingsPanel.tsx
          ResultGrid.tsx
          IslandReviewPanel.tsx
          ExportButton.tsx
        features/
          workbook/
            api.ts
            hooks.ts
            types.ts
          analysis/
            api.ts
            hooks.ts
            types.ts
          review/
            api.ts
            hooks.ts
            types.ts
        lib/
          apiClient.ts
          zodSchemas.ts

    api/
      pyproject.toml
      app/
        main.py
        routers/
          workbooks.py
          jobs.py
          rows.py
          reviews.py
          export.py
        models/
          schemas.py
        services/
          excel/
            loader.py
            writer.py
            schema_infer.py
          ml/
            preprocess.py
            classifier.py
            island_detector.py
            metrics.py
          llm/
            nano_explainer.py
          storage/
            file_store.py
        jobs/
          runner.py

  storage/
    uploads/
    jobs/
    results/

  docs/
    license-policy.md
    architecture.md
    api-spec.md
```

---

# 6. 主要機能

## 6.1 Excelアップロード

### 入力

```txt
.xlsx
.xlsm は当面対象外
複数シート対応
```

### 処理

```txt
1. ファイル保存
2. workbook_id 発行
3. シート一覧取得
4. 各シートの列名・型・サンプル行を返す
```

### API

```txt
POST /workbooks/upload
```

### レスポンス例

```json
{
  "workbook_id": "wb_123",
  "sheets": [
    {
      "name": "Sheet1",
      "row_count": 12000,
      "columns": [
        {
          "name": "temperature",
          "inferred_type": "number",
          "missing_count": 12
        },
        {
          "name": "pressure",
          "inferred_type": "number",
          "missing_count": 0
        },
        {
          "name": "label",
          "inferred_type": "category",
          "missing_count": 0
        }
      ],
      "preview_rows": []
    }
  ]
}
```

---

## 6.2 カラムマッピング

ユーザーが以下を指定する。

```txt
対象シート
特徴量列
ラベル列
除外列
ID列
レビュー対象列
```

画面では、数値列候補を自動選択し、ユーザーが修正できるようにする。

---

## 6.3 正規化

### 方針

初期実装は MinMaxScaler。

```txt
各特徴量列を0〜1に変換
元の値は保持
正規化値は内部処理用
必要なら result.xlsx に normalized_ 列として出力
```

### 欠損値

初期方針:

```txt
数値列:
  median補完

カテゴリ列:
  mode補完または除外

欠損率が高い列:
  警告表示
```

---

## 6.4 分類

初期対応モデル:

```txt
RandomForestClassifier
SVC
LinearSVC
```

MVPでは **RandomForestClassifierを主軸**にする。

理由:

```txt
特徴量重要度を出しやすい
SVMより説明しやすい
スケーリングに比較的強い
分類結果の解釈がしやすい
```

SVMは比較用として追加。

---

## 6.5 飛び地検出

### 方針

SVM / RandomForest の分類結果とは別に、特徴量空間上で孤立領域を検出する。

初期実装:

```txt
PCAで2次元または3次元に圧縮
DBSCANで小クラスタ・孤立点を検出
各クラスタのサイズ・代表特徴量・近傍クラスを計算
```

### 出力列

```txt
cluster_id
is_island
is_outlier
nearest_major_class
distance_to_nearest_cluster
review_priority
```

---

## 6.6 gpt-5.4-nano による説明生成

### 入力

nanoには生データ全体を渡さず、飛び地単位に集約した情報だけ渡す。

```json
{
  "cluster_id": "island_07",
  "size": 18,
  "predicted_class": "B",
  "nearby_major_class": "A",
  "top_feature_differences": [
    {
      "feature": "pressure",
      "cluster_mean": 0.91,
      "global_mean": 0.42
    },
    {
      "feature": "temperature",
      "cluster_mean": 0.18,
      "global_mean": 0.51
    }
  ],
  "examples": [
    {
      "row_id": 182,
      "values": {
        "pressure": 0.94,
        "temperature": 0.16
      }
    }
  ]
}
```

### 出力

```json
{
  "decision": "new_subclass_candidate",
  "confidence": 0.74,
  "reason": "高pressure・低temperatureの一貫した小クラスタで、主要クラスAとは異なる傾向があります。",
  "recommended_action": "別カテゴリ候補として人間レビュー対象にしてください。",
  "next_checks": [
    "元Excelの該当行に入力ミスがないか確認",
    "pressure列の外れ値分布を確認",
    "同条件の過去データと比較"
  ]
}
```

### 判断カテゴリ

```txt
keep_as_class
merge_with_nearest_cluster
new_subclass_candidate
likely_outlier
review_manually
exclude_from_training
needs_more_data
```

---

# 7. AG Grid Community で実現するUI

## 7.1 使用するCommunity機能

```txt
表表示
列定義
ソート
フィルタ
ページング
セル編集
列幅変更
列固定
カスタムセルレンダリング
行選択
条件付きセルスタイル
CSV export相当
```

AG Grid Community は Sorting、Filtering、Pagination、Editing、Custom Components、Theming などの core features を含むとされています。([npm][1])

---

## 7.2 使用しないEnterprise機能

```txt
Excel Export
Range Selection
Row Grouping
Pivoting
Aggregation UI
Integrated Charts
Server-Side Row Model
Master / Detail
```

これらは Enterprise に含まれる高度機能として扱われるため、MVPでは避ける。([npm.io][3])

---

## 7.3 UI画面

### Home

```txt
Excel upload
Workbook preview
Column mapping
Analysis settings
Run button
```

### Job Result

```txt
AG Grid result table
Island filter
Outlier filter
Review priority filter
Nano explanation side panel
Human decision editor
Export result.xlsx button
```

### Review View

```txt
飛び地だけ表示
クラスタ単位で要約表示
該当行一覧
nano判断コメント
人間の最終判断入力
```

---

# 8. データ列設計

結果テーブルには、元Excelの列に加えて以下を追加する。

```txt
_row_id
_predicted_class
_prediction_confidence
_cluster_id
_is_island
_is_outlier
_nearest_major_class
_review_priority
_nano_decision
_nano_reason
_nano_recommended_action
_human_decision
_human_note
```

---

# 9. API設計

## 9.1 Workbook

```txt
POST /workbooks/upload
GET /workbooks/{workbook_id}
GET /workbooks/{workbook_id}/sheets/{sheet_name}/preview
```

## 9.2 Analysis Job

```txt
POST /jobs
GET /jobs/{job_id}
GET /jobs/{job_id}/rows
GET /jobs/{job_id}/islands
```

## 9.3 Review

```txt
PATCH /jobs/{job_id}/rows/{row_id}/review
PATCH /jobs/{job_id}/islands/{cluster_id}/review
```

## 9.4 Export

```txt
GET /jobs/{job_id}/export.xlsx
```

Excel export はAG Gridではなく、FastAPI側で `openpyxl` により生成する。

---

# 10. フェーズ計画

## Phase 0: 技術検証

期間目安: 2〜3日

成果物:

```txt
React + AG Grid Community 表示
FastAPIでExcelアップロード
pandasでシート読み込み
AG Gridにpreview rows表示
```

完了条件:

```txt
.xlsx をアップロードできる
シート一覧と列一覧が取れる
1000行程度をAG Gridで表示できる
ag-grid-enterprise が依存に含まれていない
```

---

## Phase 1: MVP分析パイプライン

期間目安: 1週間

成果物:

```txt
Column mapping UI
MinMax正規化
RandomForest分類
SVM分類
基本的な評価指標
result rows API
```

完了条件:

```txt
ラベル列を指定して分類できる
予測結果列が追加される
AG Grid上で結果をフィルタ・ソートできる
```

---

## Phase 2: 飛び地検出

期間目安: 1週間

成果物:

```txt
PCA
DBSCAN
island cluster detection
review_priority算出
IslandReviewPanel
```

完了条件:

```txt
is_island = true で絞り込める
クラスタ単位で要約が見られる
人間が human_decision を編集できる
```

---

## Phase 3: nano説明生成

期間目安: 1週間

成果物:

```txt
Azure OpenAI gpt-5.4-nano連携
cluster summary prompt
structured JSON output
nano_decision / nano_reason / recommended_action 追加
```

完了条件:

```txt
飛び地クラスタごとに説明が生成される
結果テーブルに説明列が表示される
人間レビューの補助として使える
```

---

## Phase 4: Excel出力

期間目安: 3〜5日

成果物:

```txt
result.xlsx生成
元データ + 追加列の出力
レビュー結果の反映
簡易スタイル付与
```

完了条件:

```txt
AG Grid Enterprise Excel Exportを使わずにxlsx出力できる
出力ファイルをExcelで開ける
レビュー結果が保存される
```

---

## Phase 5: 品質改善

期間目安: 継続

候補:

```txt
ジョブ履歴
分析設定の保存
モデル比較
特徴量重要度表示
可視化
権限管理
監査ログ
大容量対応
```

---

# 11. 初期パッケージ

## Frontend

```bash
pnpm create vite apps/web --template react-ts
cd apps/web

pnpm add ag-grid-community ag-grid-react
pnpm add @tanstack/react-query zod react-hook-form
```

使用しない:

```bash
pnpm add ag-grid-enterprise
```

これは禁止。

## Backend

```bash
cd apps/api

pip install fastapi uvicorn pandas openpyxl scikit-learn pydantic numpy joblib
```

必要に応じて:

```bash
pip install python-multipart
pip install openai
```

---

# 12. AG Grid実装方針

## 12.1 最小ResultGrid

```tsx
import { AgGridReact } from 'ag-grid-react'
import type { ColDef } from 'ag-grid-community'

import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'

type ResultGridProps = {
  rows: unknown[]
  columns: ColDef[]
}

export function ResultGrid({ rows, columns }: ResultGridProps) {
  return (
    <div className="ag-theme-quartz" style={{ height: '70vh', width: '100%' }}>
      <AgGridReact
        rowData={rows}
        columnDefs={columns}
        defaultColDef={{
          sortable: true,
          filter: true,
          editable: true,
          resizable: true,
        }}
        rowSelection="multiple"
        pagination={true}
        paginationPageSize={100}
      />
    </div>
  )
}
```

## 12.2 Enterprise混入防止

禁止import:

```ts
import 'ag-grid-enterprise'
```

禁止dependency:

```json
{
  "dependencies": {
    "ag-grid-enterprise": "..."
  }
}
```

CIで以下をチェックする。

```bash
npm ls ag-grid-enterprise
```

または:

```bash
grep -R "ag-grid-enterprise" apps/web/src package.json
```

---

# 13. リスクと対策

## 13.1 Excelライク操作が足りない

### リスク

AG Grid Communityでは、Excel風の範囲選択やExcel Exportなどが制限される。

### 対策

```txt
MVPではセル編集・フィルタ・ソートに絞る
Excel出力はPython側で行う
範囲選択が必要なら自前実装または要件再評価
```

---

## 13.2 大容量データで重くなる

### リスク

全行をフロントに送るとブラウザが重くなる。

### 対策

```txt
初期はページング
1万行以上はサーバー側ページング風API
必要に応じて検索条件をFastAPI側へ渡す
```

ただし、AG Grid Enterprise の Server-Side Row Model は使わない。

---

## 13.3 nanoの判断が不安定

### リスク

LLM判断が毎回揺れる。

### 対策

```txt
出力カテゴリを固定
Structured JSONで返す
根拠となる統計値を必ず渡す
人間の最終判断欄を設ける
nano判断は補助扱いにする
```

---

## 13.4 SVM / RandomForestの誤分類

### リスク

データ前処理や特徴量選択により結果が大きく変わる。

### 対策

```txt
分類結果にconfidenceを付ける
評価指標を表示
モデル比較を可能にする
飛び地は最終判断にしない
```

---

# 14. MVPで作らないもの

```txt
AG Grid Enterprise機能
本格的なExcel数式エンジン
ピボットテーブル
共同編集
リアルタイム同期
高度な認証認可
モデル自動選択
AutoML
```

---

# 15. 成功条件

MVPの成功条件は以下。

```txt
Excelファイルをアップロードできる
シートと列を選択できる
RandomForest / SVMで分類できる
飛び地候補を検出できる
gpt-5.4-nanoで説明コメントを生成できる
AG Grid Communityで結果をレビューできる
人間が最終判断を編集できる
result.xlsxをPython側で出力できる
ag-grid-enterpriseを一切使わない
```

---

# 16. 推奨MVPスコープ

最初に作るべき最小スコープはこれです。

```txt
1. Excel upload
2. Sheet preview
3. Column mapping
4. RandomForest classification
5. DBSCAN island detection
6. AG Grid result table
7. Human decision column
8. result.xlsx export by openpyxl
```

その後に追加。

```txt
9. SVM support
10. gpt-5.4-nano explanations
11. review priority scoring
12. model comparison
```

---

# 17. 最終方針

本プロジェクトは、**AG Grid CommunityのMIT部分だけを利用する分析レビューWebアプリ**として進める。

設計上の重要ポイントは以下。

```txt
AG Grid Community:
  Excelライクな表示・編集・フィルタ・ソート

FastAPI / Python:
  Excel import/export
  正規化
  SVM / RandomForest
  飛び地検出
  nano連携

Azure OpenAI gpt-5.4-nano:
  判断コメント生成
  レビュー優先度補助
```

この分担により、AG Grid Enterprise のライセンス制約を避けながら、ExcelライクなWeb UIとML分類パイプラインを最短で実現できます。

[1]: https://www.npmjs.com/package/ag-grid-community?utm_source=chatgpt.com "ag-grid-community - npm"
[2]: https://www.npmjs.com/package/ag-grid-react?utm_source=chatgpt.com "ag-grid-react - npm"
[3]: https://npm.io/package/ag-grid-community?utm_source=chatgpt.com "Ag-grid-community NPM | npm.io"
[4]: https://www.ag-grid.com/javascript-data-grid/excel-export/?utm_source=chatgpt.com "JavaScript Grid: Excel Export | AG Grid"

