# TabuLens (タビュレンズ)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![React: 18+](https://img.shields.io/badge/React-18+-61DAFB?logo=react&logoColor=white)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

**TabuLens** は、Excelデータに含まれる大量の数値を自動で分析・分類し、機械学習による「飛び地（外れ値）」の検出とAIによるレビュー支援を行う、高度なデータ分析・クレンジング支援プラットフォームです。

## 🌟 主な機能

-   **Excelインテリジェント・インポート**: 複数シートに対応し、列の型推論や欠損値の統計を自動算出。
-   **高度な分類エンジン**: RandomForest / SVM 等のアルゴリズムを用い、データの分類と予測スコアを算出。
-   **飛び地（孤立クラスタ）検出**: PCAによる次元圧縮とDBSCANを組み合わせ、既存のカテゴリから外れた「異常値」や「新カテゴリ候補」を特定。
-   **AI レビュー・アシスタント**: Azure OpenAI (GPT) を活用し、検出された飛び地に対する「判断理由」や「推奨アクション」を日本語で生成。
-   **Excelライクな操作感**: AG Grid Community を採用。1万行を超えるデータもサクサク操作し、Web上でそのままレビュー・修正が可能。
-   **シームレスなエクスポート**: 分析結果、AIのコメント、人間による判断を統合した `.xlsx` ファイルをサーバーサイドで生成。

## 🏗 アーキテクチャ

本プロジェクトは、フロントエンドとバックエンドが分離されたモダンなモノレポ構成です。

-   **Frontend**: React, TypeScript, Vite, AG Grid Community, TanStack Query, Tailwind CSS
-   **Backend**: FastAPI, Python, Pandas, Scikit-learn, Openpyxl, Azure OpenAI
-   **Storage**: ファイルベースのジョブ管理・結果保存

## 🚀 クイックスタート

### バックエンドの起動

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

### フロントエンドの起動

```bash
cd apps/web
pnpm install
pnpm dev
```

## 📂 ディレクトリ構成

```txt
tabulens/
├── apps/
│   ├── api/          # FastAPI バックエンド (Python)
│   └── web/          # React フロントエンド (TypeScript)
├── docs/             # ドキュメント類
├── storage/          # アップロードファイル・分析結果の永続化
└── plan.md           # プロジェクト詳細計画書
```

## ⚖️ ライセンス方針

本プロジェクトは **AG Grid Community** 版の機能を最大限に活用するように設計されています。
Enterprise版の機能（Excel Export, Row Grouping等）に依存せず、Excelの生成などはバックエンドの Python (openpyxl) で処理することで、ライセンスコストを抑えつつ高度なUXを提供します。

---

© 2026 y.noguchi
