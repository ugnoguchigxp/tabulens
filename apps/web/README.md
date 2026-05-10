# TabuLens Web

TabuLens の React / TypeScript フロントエンドです。

## 起動

```bash
pnpm install
pnpm dev
```

既定の起動 URL は `http://localhost:29384` です。

## API 接続

既定では `http://localhost:18273/api` に接続します。

API の URL を変更する場合は `VITE_API_BASE_URL` を指定します。

```bash
VITE_API_BASE_URL=http://localhost:18273/api pnpm dev
```

## 主な画面機能

- `.xlsx` / `.csv` のアップロード
- シート選択
- AG Grid による表表示
- Mapping Settings での ID / Label / Feature 指定
- `Prepare` によるクレンジング、特徴量選択、AI レビュー、改善提案
- `Workflow` による classification / prediction / anomaly detection / recommendation / clustering / noise reduction 実行
- Prepare 済みデータを使った Workflow 学習
- 予測モデル artifact のダウンロード
- Prepare 結果と Workflow 結果の表示切り替え

## 開発コマンド

```bash
pnpm build
pnpm lint
pnpm preview
```
