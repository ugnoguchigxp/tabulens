# TabuLens 計算エンジン実装計画

この文書は、TabuLens に XLSX ライクなセル計算を追加するための実装計画である。

前提は次の通り。

- TabuLens 本体は MIT ライセンスを維持する
- GPL 系の計算エンジンは採用しない
- Excel / Office 365 の完全再実装は目指さない
- ただし、セル同士の参照計算がない状態は XLSX ライクとは呼べない
- `PREDICT()` は初期リリースから扱う
- グラフ表示は計算エンジンと分離し、Recharts 等の MIT ライブラリで実装する

## 1. レビュー結果

前回の実装案では、`Formula.js + 自前 parser / dependency graph / evaluator` を前提にしていた。
この方向は MIT 制約を守れる一方で、初期実装の負荷が大きすぎる。

改善後の方針は次の通り。

- Excel 数式の字句解析・構文解析・基本評価は、MIT 候補の既存 OSS を使う
- TabuLens 側で自作するのは、workbook state、依存グラフの保持、差分再計算、非同期 `PREDICT()`、AG Grid 統合に限定する
- `Formula.js` は関数単体の実装として有用だが、依存関係解析や async custom function まで含めるなら `fast-formula-parser` を先に検証する
- ただし `fast-formula-parser` は古いので、採用前に依存ライセンス・保守状況・TypeScript 型の扱いを短期 spike で確認する

参考:

- Formula.js は Microsoft Excel 関数の JavaScript 実装で、Node/browser で利用できる。README 上でも `SUM([1, 2, 3])` のような関数呼び出しを示している。
  https://github.com/formulajs/formulajs
- `fast-formula-parser` は MIT ライセンスで、Excel formula の parse/evaluate、dependency parse、custom async functions を README に示している。
  https://github.com/LesterLyu/fast-formula-parser
- Recharts は React + D3 ベースのチャートライブラリで、MIT ライセンス。
  https://github.com/recharts/recharts

## 2. 採用判断

### 2.1 第一候補: TypeScript port / modernize

`fast-formula-parser` を参考にしつつ、TabuLens 向けの TypeScript 実装として取り込む。

採用理由:

- MIT license と明記されている
- Excel formula の parser / evaluator を持つ
- `DepParser` による依存関係解析がある
- `parseAsync` と custom async function があり、`PREDICT()` と相性が良い
- `onCell` / `onRange` hook により、TabuLens の grid state から値を供給できる
- JavaScript 実装なので、TypeScript port の現実性が高い
- テスト資産を MIT 条件のもとで流用できる可能性がある

懸念:

- 最新 release が古い
- そのまま依存すると TypeScript 体験と保守性に不安が残る
- 対応外構文がある
- 依存 package のライセンス監査が必要
- コードを翻訳・改変する場合は派生物として MIT 表示を保持する必要がある

実測した規模:

- core implementation: 約 8,701 行
- grammar / dependency parser: 約 1,937 行
- formula functions: 約 5,420 行
- SSF/date-format 周辺: 約 1,346 行
- test code: 約 92,638 行
- うち `test/formulas.txt`: 約 89,244 行

評価:

- フル rewrite ではなく、parser / dependency parser / minimal functions を段階 port するなら現実的
- 全 Excel 関数を初期 port するのは過大
- まず TabuLens の v0 / v1.x 関数だけを port し、既存テスト corpus から該当ケースを抽出する
- 複数シート、検索/参照、文字列、日付、volatile 関数は XLSX ライク体験の核として初期ロードマップに含める
- 高度な distribution / engineering / financial 関数は初期対象外にする

### 2.2 第二候補: 直接依存

`fast-formula-parser` を npm dependency として使う。

採用条件:

- Phase 0 spike で型・bundle・依存ライセンス・実行時挙動に問題がない
- 自前 port より速度を優先する

懸念:

- 古い dependency をプロダクト中核に置くことになる
- patch や拡張を upstream に依存しづらい
- `PREDICT()` や TabuLens 独自 error handling を入れるほど adapter が厚くなる

### 2.3 第三候補

`Formula.js + 自前 parser`

採用条件:

- `fast-formula-parser` の依存・型・実行時挙動が不適合だった場合
- v0 の一時 POC として対応関数を限定し、簡易 grammar から始める場合

懸念:

- 参照解析、範囲展開、演算子優先順位、エラー伝播を自前実装する必要がある
- `PREDICT()` の async 評価と dependency graph の統合を全て自前で持つことになる
- 複数シート、検索/参照、文字列、日付、volatile まで考えると、最終的な工数は TypeScript port より大きくなりやすい

### 2.4 不採用

`HyperFormula`

理由:

- MIT ではない
- GPLv3 / commercial licensing のため、MIT 固定の TabuLens には合わない

## 3. 対応スコープ

### 3.1 v0: Calc engine baseline

まずセル同士の計算が成立する最小土台を作る。

- 同一シートのセル参照: `A1`
- 同一シートの範囲参照: `A1:B10`
- 四則演算: `+`, `-`, `*`, `/`
- 比較: `=`, `<>`, `>`, `>=`, `<`, `<=`
- 基本関数:
  - `SUM`
  - `AVERAGE`
  - `MIN`
  - `MAX`
  - `COUNT`
  - `IF`
  - `AND`
  - `OR`
  - `NOT`
  - `ROUND`
  - `ABS`
  - `PREDICT`

### 3.2 v1: 複数シート

複数シートは初期ロードマップに含める。
単一シートだけでは XLSX 的な workbook 操作に届かないため、dependency graph の key は最初から sheet を含める。

対応する参照:

- `Sheet2!A1`
- `Sheet2!A1:B10`
- `'Sales 2025'!B2`
- `'Sales 2025'!A1:D10`

設計方針:

- 内部 cell key は `sheetName + rowIndex + colId` で一意にする
- 同一シート参照も内部では active sheet を補完して保持する
- sheet rename 時は formula 文字列と dependency graph を更新する
- sheet delete 時は参照元を `#REF!` にする
- cross-sheet cycle は通常の cycle と同じく `#CIRC!` にする

### 3.3 v1.1: 検索/参照関数

検索/参照は実務利用頻度が高いため、基本関数の直後に対応する。

初期対応:

- `INDEX`
- `MATCH`
- `VLOOKUP`
- `XLOOKUP`

後続候補:

- `HLOOKUP`
- `CHOOSE`
- `OFFSET`

方針:

- まず exact match を優先する
- approximate match は互換仕様とテストが固まってから入れる
- 範囲 shape、戻り index、未検出時の error を明示的に検証する
- 誤計算より `#VALUE!`, `#REF!`, `#NAME?`, `#UNSUPPORTED` を優先する

### 3.4 v1.2: 文字列・日付互換

文字列と日付は XLSX からの移行で破綻しやすいため、初期互換性の対象に含める。
ここは「似ている挙動」ではなく、Excel 互換のテストで検証する。

文字列関数:

- `CONCAT`
- `LEFT`
- `RIGHT`
- `MID`
- `LEN`
- `TRIM`
- `UPPER`
- `LOWER`
- `SUBSTITUTE`
- `TEXT`

日付関数:

- `DATE`
- `DATEVALUE`
- `YEAR`
- `MONTH`
- `DAY`
- `DATEDIF`
- `EDATE`
- `EOMONTH`
- `NETWORKDAYS`
- `TODAY`
- `NOW`

方針:

- 内部表現は JavaScript `Date` そのものではなく Excel serial date を基本にする
- `TEXT` は Excel 互換を最終目標にし、先に対応 format と未対応 format を明示する
- 曖昧な date parse は locale 推測で誤変換せず `#VALUE!` にする
- fast-formula-parser の `ssf` 周辺は、日付/表示互換の中核候補として移植範囲を評価する

### 3.5 v1.3: Volatile 関数

volatile 関数は実装する。ただし、再計算タイミングを明確に制御し、無限再計算や UI の揺れを避ける。

初期対応:

- `NOW`
- `TODAY`
- `RAND`
- `RANDBETWEEN`

再計算ポリシー:

- workbook open
- cell edit
- 明示的な Recalculate 操作

初期版では interval timer による自動再計算は行わない。

設計方針:

- formula metadata に `volatile: true` を持たせる
- manual recalc 時は volatile cell とその dependents を再評価する
- `RAND` / `RANDBETWEEN` は同一 recalc batch 内で値を安定させる
- `NOW` / `TODAY` は recalc batch の開始時刻を基準にする

### 3.6 v2 以降

次は後続バージョンで扱う。

- 外部 workbook 参照
- array formula
- spill range
- structured table reference
- named range
- iterative calculation
- financial functions
- engineering functions
- advanced statistical functions

### 3.7 エラー表現

TabuLens 内部では文字列ではなく enum で保持し、表示時に Excel 風の文字列へ変換する。

```ts
type FormulaErrorCode =
  | 'REF'
  | 'VALUE'
  | 'DIV0'
  | 'NAME'
  | 'CIRC'
  | 'PENDING'
  | 'UNSUPPORTED'
  | 'PREDICT_ERR'
```

表示:

- `#REF!`
- `#VALUE!`
- `#DIV/0!`
- `#NAME?`
- `#CIRC!`
- `#PENDING`
- `#UNSUPPORTED`
- `#PREDICT_ERR`

## 4. アーキテクチャ

### 4.1 配置

`apps/web/src/calc-engine/` を追加する。

```txt
apps/web/src/calc-engine/
├── types.ts
├── address.ts
├── workbook-state.ts
├── parser-adapter.ts
├── dependency-graph.ts
├── evaluator.ts
├── recalc.ts
├── formatter.ts
├── functions/
│   ├── predict.ts
│   ├── lookup.ts
│   ├── text.ts
│   ├── date.ts
│   └── volatile.ts
└── index.ts
```

役割:

- `types.ts`: cell, formula, dependency, error の型
- `address.ts`: `A1` と `{ rowIndex, colIndex }` の相互変換
- `workbook-state.ts`: raw input / computed value / formula metadata の保持
- `parser-adapter.ts`: `fast-formula-parser` を直接アプリに漏らさない adapter
- `dependency-graph.ts`: formula cell 間の graph と循環検出
- `evaluator.ts`: sync/async formula evaluation
- `recalc.ts`: changed cell 起点の差分再計算
- `formatter.ts`: Excel serial date と `TEXT()` 用の表示変換
- `functions/*`: `PREDICT()`, lookup/reference, text/date, volatile functions

### 4.2 状態モデル

AG Grid の `rowData` だけに formula を保存しない。
表示値と入力値を分離する。

```ts
type CellAddress = {
  sheetName: string
  rowIndex: number
  colId: string
}

type CellState = {
  address: CellAddress
  raw: unknown
  formula?: string
  value: unknown
  error?: FormulaErrorCode
  dependencies: string[]
  dependents: string[]
  pending: boolean
}
```

方針:

- ユーザー入力が `=` で始まる場合は `formula` として保持する
- AG Grid に渡す値は `value` または error display
- formula bar 追加までは、tooltip で `formula` を確認できるようにする
- export 時は表示値と formula metadata を別シートに出せるようにする

## 5. PREDICT 関数

### 5.1 式の形

初期対応:

```txt
=PREDICT(A2:D2)
=PREDICT("latest", A2:D2)
```

将来対応:

```txt
=PREDICT("workflow_id", A2:D2)
=PREDICT("model_alias", A2:D2, {"threshold":0.7})
```

### 5.2 実行方式

`PREDICT()` は非同期関数として扱う。

表示状態:

- 実行開始: `#PENDING`
- 成功: 推論値
- 失敗: `#PREDICT_ERR`

キャッシュ:

- key: `workflow_id + feature_values_hash`
- TTL: 初期は session 中のみ
- 同一入力の連続編集で backend を叩きすぎない

### 5.3 Backend API

既存の Workflow は結果行を保存するが、学習済み model artifact は永続化していない。
`PREDICT()` を本当に初期搭載するには、まず推論可能な workflow artifact を保存する必要がある。

追加 API:

```txt
POST /api/model-workflows/{workflow_id}/predict
```

request:

```json
{
  "columns": ["f1", "f2", "f3"],
  "rows": [
    [1.2, 0.8, "A"]
  ]
}
```

response:

```json
{
  "workflow_id": "wf-123",
  "predictions": [
    {
      "value": "class_a",
      "confidence": 0.82
    }
  ]
}
```

Backend 実装:

- `run_model_workflow` の `model_artifacts` を `joblib` で保存する
- `workflow_state` に `model_artifact_path` を追加する
- predict endpoint で model/preprocessor/feature_columns を復元する
- feature columns の不足・型不一致は 400 で返す

## 6. 実装 Phase

### Phase 0: TypeScript port feasibility

目的: `fast-formula-parser` をそのまま依存するか、TypeScript port するかを 1-2 日で判断し、v0 / v1.x の移植範囲を確定する。

作業:

- `apps/web` に `fast-formula-parser` を一時導入
- `SUM(A1:B2)` を `onCell` / `onRange` で評価
- `Sheet2!A1` と `'Sales 2025'!A1:B10` の parse / dependency parse を確認する
- `DepParser` で `A1:B2` の依存セルを取得
- `parseAsync` で dummy `PREDICT()` を評価
- TypeScript build を通す
- license checker で依存ライセンスを確認
- core files を TypeScript 化した場合の import boundary を確認する
- v0 / v1.x 対応関数を抽出した場合の対象ファイルを確定する
- lookup/reference, text, date, volatile の既存テスト抽出量を確認する

完了条件:

- parser/evaluator/dependency parse/async custom function が動く
- 複数シート参照の token / AST / dependency 表現を把握できている
- MIT 互換である
- bundle size と型の問題が許容範囲
- TypeScript port の対象範囲が 2-3 週間以内に収まる

失敗時:

- `Formula.js + 小さい自前 parser` に切り替える

判断基準:

- 直接依存: 1-2 日で統合できるが、保守性は低い
- TypeScript port: 2-3 週間程度の初期投資が必要だが、長期保守と `PREDICT()` 統合に強い
- 完全自作: v0 のみなら可能だが、Excel formula 互換の拡張で詰まりやすい

推奨:

TabuLens では TypeScript port を第一候補にする。
ただし、最初から全関数を移植しない。parser / dependency parser / evaluator skeleton / v0-v1.3 関数だけを移植し、残りの関数は `#UNSUPPORTED` にする。

### Phase 1: Formula cell state

対象:

- `apps/web/src/calc-engine/types.ts`
- `apps/web/src/calc-engine/address.ts`
- `apps/web/src/calc-engine/workbook-state.ts`
- `apps/web/src/hooks/use-grid-editor.ts`

作業:

- raw input と computed value を分離する
- `=...` 入力を formula として保存する
- `A1` address と AG Grid column id を対応させる
- workbook / sheet / cell の state 境界を分ける
- 表示値を `rowData` に戻す adapter を作る

完了条件:

- `=1+2` を入力すると `3` が表示される
- raw formula は失われない
- sheet を持つ `CellAddress` で単一シートも扱える
- 既存の行/列追加/削除が壊れない

### Phase 2: Dependency graph and recalc

対象:

- `dependency-graph.ts`
- `parser-adapter.ts`
- `recalc.ts`

作業:

- formula cell の依存セルを抽出する
- dependents を逆引きできるようにする
- dependency key を `sheetName + cellAddress` に統一する
- 変更セルから影響範囲だけ再計算する
- 循環参照を検出する

完了条件:

- `A1=1`, `B1=A1+1`, `C1=B1+1` が連鎖再計算される
- `Sheet1!A1` の変更で `Sheet2!B1=Sheet1!A1+1` が再計算される
- `A1=B1`, `B1=A1` が `#CIRC!` になる
- `Sheet1!A1=Sheet2!B1`, `Sheet2!B1=Sheet1!A1` が `#CIRC!` になる
- 変更していない無関係 cell は再計算されない

### Phase 3: Supported functions and compatibility tiers

対象:

- `evaluator.ts`
- `parser-adapter.ts`
- `calc-engine/*.test.ts`
- `docs/supported-formulas.md`

作業:

- v0 / v1 / v1.1 / v1.2 / v1.3 の対応関数を固定する
- 対応外関数は `#UNSUPPORTED` にする
- Excel 互換と違う挙動は `docs/supported-formulas.md` に明記する
- `fast-formula-parser` の formula tests から対象関数に該当するものを抽出する
- lookup/reference, text, date, volatile の port 検証テストを分ける
- 抽出したテストには original MIT license / attribution を残す

完了条件:

- `SUM`, `AVERAGE`, `MIN`, `MAX`, `COUNT`, `IF`, `AND`, `OR`, `NOT`, `ROUND`, `ABS` のテストがある
- `INDEX`, `MATCH`, `VLOOKUP`, `XLOOKUP` の基本テストがある
- `CONCAT`, `LEFT`, `RIGHT`, `MID`, `LEN`, `TRIM`, `TEXT` の基本テストがある
- `DATE`, `DATEVALUE`, `YEAR`, `MONTH`, `DAY`, `EDATE`, `EOMONTH`, `NETWORKDAYS` の基本テストがある
- `NOW`, `TODAY`, `RAND`, `RANDBETWEEN` の recalc policy テストがある
- エラー伝播のテストがある

### Phase 4: Multi-sheet workbook state

対象:

- `workbook-state.ts`
- `address.ts`
- `dependency-graph.ts`
- `parser-adapter.ts`
- `apps/web/src/hooks/use-grid-editor.ts`

作業:

- sheet list / active sheet / sheet-scoped row data を保持する
- `Sheet2!A1` と quoted sheet name を address parser に入れる
- sheet rename 時に formula 文字列と dependency graph を更新する
- sheet delete 時に参照元を `#REF!` にする
- AG Grid の表示 state と workbook state の同期境界を定義する

完了条件:

- 複数シートを持つ workbook state を作成できる
- cross-sheet formula が評価・再計算される
- sheet rename/delete の挙動がテストされている

### Phase 5: PREDICT backend

対象:

- `apps/api/app/services/ml/model_workflows.py`
- `apps/api/app/routers/model_workflows.py`
- `apps/api/tests/test_model_workflows_router.py`

作業:

- workflow 実行時に `model_artifacts` を保存する
- predict endpoint を追加する
- classification / regression の戻り値を標準化する
- artifact がない workflow では 404 または 409 を返す

完了条件:

- workflow 実行後に `/predict` が推論値を返す
- artifact 不在時のエラーが明確
- feature columns 不一致のテストがある

### Phase 6: PREDICT frontend

対象:

- `apps/web/src/calc-engine/functions/predict.ts`
- `apps/web/src/lib/api-client.ts`
- `apps/web/src/App.tsx`

作業:

- `PREDICT()` を async custom function として登録する
- active workflow id を calc context に渡す
- `#PENDING` 表示と結果キャッシュを実装する
- backend error を `#PREDICT_ERR` に変換する

完了条件:

- `=PREDICT(A2:D2)` が推論結果を表示する
- 同じ入力で backend request が重複しない
- workflow 未実行時は `#PREDICT_ERR` または明確な UI state になる

### Phase 7: Lookup/reference functions

対象:

- `evaluator.ts`
- `functions/lookup.ts`
- `calc-engine/*.test.ts`

作業:

- `INDEX`, `MATCH`, `VLOOKUP`, `XLOOKUP` を実装する
- exact match を先に安定させる
- 範囲 shape と out-of-range を `#VALUE!` / `#REF!` に変換する
- cross-sheet range を lookup 対象にできるようにする

完了条件:

- 同一シートと複数シートの lookup が動く
- 未検出、範囲不正、列 index 不正のエラーがテストされている
- approximate match は未対応なら `#UNSUPPORTED` として明示される

### Phase 8: Text/date compatibility

対象:

- `functions/text.ts`
- `functions/date.ts`
- `formatter.ts`
- `calc-engine/*.test.ts`

作業:

- text functions の Excel 互換 subset を実装する
- Excel serial date を内部表現として定義する
- `DATE`, `DATEVALUE`, date extraction, month end/weekdays 系を実装する
- `TEXT` の format subset を決める
- ambiguous date parse を `#VALUE!` にする

完了条件:

- 文字列関数の基本互換テストがある
- Excel serial date と表示変換のテストがある
- 日付関数が raw JavaScript `Date` 依存で揺れない

### Phase 9: Volatile recalc policy

対象:

- `recalc.ts`
- `evaluator.ts`
- `functions/volatile.ts`
- `calc-engine/*.test.ts`

作業:

- formula metadata に `volatile` flag を追加する
- `NOW`, `TODAY`, `RAND`, `RANDBETWEEN` を実装する
- workbook open / cell edit / manual recalc の trigger を定義する
- recalc batch context を作り、batch 内の時刻と乱数評価を安定させる
- initial version では interval timer を入れない

完了条件:

- manual recalc で volatile cell と dependents が再評価される
- 同一 recalc batch 内で `TODAY` / `NOW` の基準時刻が一致する
- `RAND` / `RANDBETWEEN` の dependents が同一 batch の結果を読む

### Phase 10: XLSX import/export

対象:

- `apps/api/app/routers/workbooks.py`
- `apps/api/app/routers/jobs.py`
- `apps/api/app/routers/model_workflows.py`

作業:

- import 時に formula 文字列を保持する方法を決める
- `openpyxl` で formula cell を読み、raw formula と cached value を分離する
- 複数シートの formula metadata を維持する
- Excel serial date と TabuLens 表示値の対応を維持する
- export に `formulas` sheet を追加する
- 表示値 export と formula preservation の方針を README に書く

完了条件:

- formula cell を含む xlsx を upload して formula metadata が残る
- 複数シート参照を含む xlsx の metadata が残る
- export で表示値と formula の対応を追える

### Phase 11: Charts

対象:

- `apps/web/src/components`
- `apps/web/src/lib/chart-utils.ts`

作業:

- Recharts を導入する
- 選択範囲または workflow result から chart dataset を生成する
- chart config は cell formula engine と分離する

完了条件:

- 選択した numeric column から line/bar/scatter の基本 chart を表示できる
- chart は calculation engine の再計算結果を読むだけで、計算責務を持たない

## 7. テスト計画

Frontend unit:

- address conversion
- parser adapter
- dependency extraction
- cycle detection
- sync recalc
- async recalc
- cross-sheet dependency recalc
- sheet rename/delete reference handling
- lookup/reference functions
- text functions
- Excel serial date functions
- volatile recalc batch behavior
- `PREDICT()` cache
- unsupported function

Backend unit:

- model artifact save/load
- predict endpoint success
- predict endpoint feature mismatch
- predict endpoint artifact missing

Integration:

- grid edit -> formula recalc
- sheet edit -> cross-sheet formula recalc
- workflow run -> `PREDICT()` formula
- lookup over imported xlsx-like ranges
- date/text formula import -> calculate -> export
- manual recalc -> volatile formula update
- formula result -> chart source
- xlsx import/export with formula metadata

## 8. 推奨コミット順

1. `docs: add calc engine implementation plan`
2. `spike: measure and verify fast-formula-parser port scope`
3. `feat(web): add formula engine package skeleton`
4. `feat(web): port parser and dependency parser for v0-v1 formulas`
5. `feat(web): add calc engine state and address utilities`
6. `feat(web): add dependency graph and recalc`
7. `feat(web): support multi-sheet formulas`
8. `feat(api): persist workflow model artifacts`
9. `feat(api): add workflow predict endpoint`
10. `feat(web): support PREDICT formula`
11. `feat(web): add lookup and reference formulas`
12. `feat(web): add text and date formula compatibility`
13. `feat(web): add volatile formula recalc policy`
14. `feat(api): preserve formula metadata in xlsx import/export`
15. `feat(web): add chart view from computed data`

## 9. 重要な判断ルール

- Excel 互換性より TabuLens の分析体験を優先する
- GPL は採用しない
- parser/evaluator の完全自作は最後の手段にする
- `PREDICT()` は最初から入れるが、非同期・キャッシュ・エラー表現を明確にする
- 複数シート、検索/参照、文字列、日付、volatile は初期ロードマップから外さない
- chart は計算エンジンに入れない
- unsupported は黙って誤計算せず、明示的に `#UNSUPPORTED` を返す

## 10. 最初に着手する作業

まず Phase 0 を実施する。

具体的には、`fast-formula-parser` を一時導入し、次を確認する。

- `SUM(A1:B2)` が grid state から評価できる
- `Sheet2!A1` と quoted sheet name の parse / dependency parse が確認できる
- `DepParser` で依存セルが取れる
- async custom `PREDICT()` が `parseAsync` で動く
- `pnpm lint`, `pnpm test -- --run`, `pnpm build` が通る
- v0 / v1.x 関数を TypeScript port したときの対象ファイルとテスト抽出量を確定する
- lookup/reference, text, date, volatile のテスト流用可否を確認する
- original MIT license / attribution の置き場所を決める

この spike が成功した場合、TypeScript port を `apps/web/src/calc-engine/vendor/fast-formula-core/` のような隔離された内部 package として進める。
失敗した場合だけ、`Formula.js + 小さい自前 parser` へ戻す。

## 11. ライセンス方針

`fast-formula-parser` は MIT なので、TabuLens の MIT 方針とは矛盾しない。
ただし、コードやテストを翻訳・改変して取り込む場合、次を必ず行う。

- original copyright notice を保持する
- original MIT license を `THIRD_PARTY_NOTICES.md` または同等の文書に記載する
- 移植したファイルの由来を明記する
- TabuLens 独自実装と ported code の境界をディレクトリで分ける
- 将来の関数追加時も、コピー/翻訳/独自実装の由来を追跡できるようにする

推奨ディレクトリ:

```txt
apps/web/src/calc-engine/
├── core/
├── tabulens/
├── vendor/
│   └── fast-formula-core/
└── THIRD_PARTY_NOTICES.md
```

`vendor/fast-formula-core/` は Excel formula parser/evaluator の port。
`tabulens/` は `PREDICT()`, workflow integration, grid state integration など TabuLens 独自の責務に限定する。
