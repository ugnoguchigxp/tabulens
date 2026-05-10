# TabuLens プロダクト価値改善計画

この文書は、TabuLens を「Excel / CSV の表形式データで ML が効きそうかを短時間で判断するローカル解析ツール」として強化するための実装計画である。

既存の `Prepare` / `Explore` / `Workflow` 主導線は維持する。  
方向性は、AutoML SaaS と正面から競うことではなく、ローカルに置いた表データに対して、次の判断を速く・説明可能にすることである。

- この target は学習対象として妥当か
- 選んだ feature に使える信号があるか
- baseline より ML モデルを使う意味があるか
- 今は Workflow に進むべきか、Mapping / Prepare に戻るべきか
- データを外部 SaaS に送らずローカルで確認できるか

## 1. 現状評価

TabuLens は MVP として次の価値をすでに持っている。

- `.xlsx` / `.csv` の取り込み
- 複数シートの読み取り
- AG Grid ベースの表編集
- `ID Column` / `Label Column` / `Features` の mapping
- 欠損処理、正規化、外れ値除去、特徴量重要度表示
- `data_profile` / `target_feasibility` / `model_sweep` / `evaluation`
- 分類、回帰、異常検知、クラスタリングの Workflow
- 結果行と指標の表示
- Excel export
- 分類境界グラフ

一方で、プロダクト価値を伸ばすうえで次の弱点がある。

- `Explore` の結果が、まだ「次に何をすべきか」という意思決定に直結しきっていない
- upload response が全行を含むため、大きい CSV / Excel で UI・通信・メモリが破綻しやすい
- README では Review 廃止済みだが、backend には旧 Review / Proposal 系の実装が残っている
- ローカル実行・プライバシー・feasibility check という価値が UI / README / export に十分出ていない

## 2. ゴール

### 2.1 プロダクトゴール

ユーザーが Excel / CSV をアップロードしてから数分以内に、次のいずれかを判断できる状態にする。

- `Workflow に進める`
- `feature を見直す`
- `target / label を見直す`
- `行数またはデータ品質が不足している`
- `ML より baseline / ルールで十分そう`

### 2.2 技術ゴール

- 大きいファイルでも初期表示と探索評価が破綻しない
- API response は用途別に軽量化する
- 旧 Review / Proposal 系の残骸を整理し、現行主導線とコード構造を一致させる
- テストで主要判定ロジックと API 境界を保護する

## 3. 非目的

この計画では次を目指さない。

- 本格 AutoML platform 化
- モデル registry / deployment / monitoring
- 長期実験管理
- LLM review を主導線に戻すこと
- Review Panel / Review Modal の復活
- model artifact のダウンロード導線復活
- SaaS 化やユーザー管理

## 4. Phase 1: Explore を意思決定パネルにする

### 4.1 目的

`Explore` を指標一覧ではなく、次に取るべき操作を示す判断パネルにする。

既存の詳細計画は `docs/exploration-evaluation-implementation-plan.md` にある。  
この Phase では、その上に UI と API の意思決定表現を追加する。

### 4.2 API 変更

対象ファイル:

- `apps/api/app/models/schemas.py`
- `apps/api/app/services/exploration.py`
- `apps/api/tests/test_explorations.py`

`ExplorationEvaluation` に次を追加する。

```python
class ExplorationDecision(BaseModel):
    primary_message: str
    recommended_path: Literal[
        "run_workflow",
        "adjust_features",
        "change_target",
        "collect_more_data",
        "inspect_data_quality",
        "use_baseline"
    ]
    primary_blocker: Optional[str] = None
```

`ExplorationNextAction` に次を追加する。

```python
class ExplorationNextAction(BaseModel):
    action: ...
    reason: str
    priority: ...
    affected_columns: list[str] = Field(default_factory=list)
```

`build_exploration_evaluation` では、既存の `overall_verdict` をもとに `decision` を組み立てる。

- `usable_signal` -> `run_workflow`
- `needs_better_features` -> `adjust_features`
- `needs_better_target` -> `change_target`
- `not_enough_data` -> `collect_more_data`
- `try_more` + `overfit_risk` -> `inspect_data_quality`
- `no_model_beats_baseline` -> `use_baseline` または `adjust_features`

### 4.3 リスク列の明示

`DataProfileColumn.warning_flags` から、feature mapping に含まれる risky columns を抽出する。

追加する補助関数:

```python
def _columns_for_warning(profile: DataProfile, mapping: ColumnMapping, warning: str) -> list[str]:
    ...
```

利用例:

- `likely_identifier_features` -> affected columns に likely_identifier な feature を入れる
- `high_missing_rate_features` -> affected columns に high_missing_rate な feature を入れる
- `low_variance_features` -> affected columns に low_variance な feature を入れる

### 4.4 UI 変更

対象ファイル:

- `apps/web/src/components/exploration-panel.tsx`
- `apps/web/src/App.tsx`

`ExplorationPanel` の最上部に Decision Summary を追加する。

表示内容:

- 結論 badge
- 推奨パス
- primary blocker
- confidence
- 次のアクション
- affected columns

UI の優先順位:

1. 結論
2. 次に触るべき場所
3. リスク列
4. model sweep の詳細

### 4.5 受け入れ条件

- `Explore` 後に、ユーザーが `Prepare` / `Mapping` / `Workflow` のどれに進むべきか分かる
- `exclude_risky_columns` に対象列名が出る
- `not_enough_rows`、`label_column_missing`、`no_model_beats_baseline`、`overfit_risk` のテストがある
- backend / frontend の既存テストが通る

## 5. Phase 2: 大きいファイルに耐える Workbook API にする

### 5.1 目的

アップロード時に全行を返す設計をやめ、初期表示・行取得・分析実行を分離する。

現状の `SheetInfo.rows` は便利だが、大きいファイルで response が肥大化する。  
MVP の実用性を上げるには、preview と paged rows を分ける必要がある。

### 5.2 API 変更

対象ファイル:

- `apps/api/app/models/schemas.py`
- `apps/api/app/routers/workbooks.py`
- `apps/api/tests/test_workbooks.py`

`SheetInfo` は全行を返さない方向へ寄せる。

```python
class SheetInfo(BaseModel):
    name: str
    row_count: int
    columns: list[ColumnInfo]
    preview_rows: list[dict]
```

新規 schema:

```python
class SheetRowsResponse(BaseModel):
    workbook_id: str
    sheet_name: str
    offset: int
    limit: int
    row_count: int
    rows: list[dict]
```

新規 API:

```txt
GET /api/workbooks/{workbook_id}/sheets/{sheet_name}/rows?offset=0&limit=100
GET /api/workbooks/{workbook_id}/sheets/{sheet_name}/profile
```

`rows` API は backend で対象 workbook を読み、`offset` / `limit` で返す。

### 5.3 Frontend 変更

対象ファイル:

- `apps/web/src/lib/api-client.ts`
- `apps/web/src/hooks/use-tabulens.ts`
- `apps/web/src/App.tsx`
- `apps/web/src/lib/api-client.test.ts`

追加する client:

```ts
getWorkbookRows(workbookId: string, sheetName: string, offset = 0, limit = 100)
```

初期表示は upload response の `preview_rows` を使う。  
全行を必要とする `Prepare` / `Explore` / `Workflow` は、これまで通り backend の保存ファイル全体を読むため、分析処理の意味は変えない。

### 5.4 受け入れ条件

- upload response が全行を含まない
- 10万行 CSV でも upload response は preview と metadata のみ
- 初期表示は即時に出る
- rows API は `offset` / `limit` の境界値をテストする
- 既存の `Prepare` / `Explore` / `Workflow` は workbook 全体に対して動く

## 6. Phase 3: 旧 Review / Proposal 系を整理する

### 6.1 目的

README の方針とコード構造を一致させる。

README では Review パネル / Review モーダルは廃止済みであり、model artifact download も廃止済みである。  
しかし backend には旧 Review / Proposal 系の schema / service / LLM helper が残っている。

### 6.2 調査対象

対象ファイル:

- `apps/api/app/services/analysis_review.py`
- `apps/api/app/services/ml/model_review.py`
- `apps/api/app/services/llm/nano_explainer.py`
- `apps/api/app/models/schemas.py`
- `apps/api/app/services/job_store.py`
- `apps/api/tests/test_analysis_review.py`
- `apps/api/tests/test_model_review.py`
- `apps/api/tests/test_nano_explainer.py`

まず、現行 router / frontend から参照されているかを確認する。

```bash
rg -n "analysis_review|model_review|nano_explainer|ReviewResult|ModelReviewResult|proposal" apps/api apps/web
```

### 6.3 整理方針

現行主導線から呼ばれていないものは削除する。  
ただし、判定ロジックとして有用なものは `Explore Evaluation` へ移す。

移植候補:

- train/test gap 判断
- class imbalance 判断
- low confidence 判断
- sample error 抽出
- label quality warning
- collect more data warning

削除候補:

- proposal の Apply / Discard / Rerun
- Review artifact 保存
- Azure OpenAI review call
- safe_to_promote
- model artifact download に紐づく metadata

### 6.4 受け入れ条件

- README の現方針と backend の公開 surface が一致する
- `Review Panel` / `Review Modal` / `proposal apply` に関する未使用コードが残らない
- 旧テスト削除後も backend tests が通る
- `Explore Evaluation` のテストで、移植した判断ロジックが保護されている

## 7. Phase 4: ローカル・プライバシー価値を明文化する

### 7.1 目的

TabuLens の勝ち筋を明確にする。

競合する本格 AutoML / no-code ML / Excel AI 機能は、モデル運用、クラウド連携、チーム共有に強い。  
TabuLens は、次の価値に絞る。

- ローカルで動く
- CSV / Excel を外部 SaaS に送らず確認できる
- 本番モデルではなく、ML feasibility を短時間で判断する
- 判断根拠を表データと一緒に見られる

### 7.2 README 変更

対象ファイル:

- `README.md`

冒頭に次を明記する。

- TabuLens はローカル解析ツールである
- 主目的は ML feasibility check である
- AutoML platform ではない
- 外部 LLM / SaaS 連携は主導線ではない
- `Explore` が判断、`Workflow` が詳細実行を担当する

### 7.3 UI 変更

対象ファイル:

- `apps/web/src/App.tsx`

未アップロード状態の空画面を、単なる `No Workbook Loaded` から価値が伝わる表示に変える。

表示例:

```txt
Upload a local workbook to check whether it contains usable ML signal.
```

ただし、説明過多にはしない。  
操作の主導線は upload button のままにする。

### 7.4 Export 変更

対象ファイル:

- `apps/api/app/routers/model_workflows.py`
- `apps/api/app/routers/jobs.py`
- `apps/api/tests/test_model_workflows_router.py`

Workflow export に `evaluation` sheet を追加する。

含める項目:

- verdict
- signal strength
- model viability
- confidence
- risk flags
- next actions
- model sweep summary

`Workflow` 実行時点で最新 `Explore` 結果がない場合は、export に含めないか、metadata に `evaluation_not_available` を明示する。

### 7.5 受け入れ条件

- 初見ユーザーが README と初期画面だけで、TabuLens の用途を理解できる
- export を見れば、なぜその判断になったか追える
- 外部 SaaS / LLM に送る前提の表現が主導線から消える

## 8. 推奨実装順

1. Phase 1: `Explore` の意思決定強化
2. Phase 2: Workbook API の軽量化と rows paging
3. Phase 3: 旧 Review / Proposal 系の削除または吸収
4. Phase 4: README / UI / export に価値を反映

この順番にする理由は、最初に中核価値を強化し、その後に実用データへの耐性を上げ、最後にコード構造と訴求を揃えるためである。

## 9. 検証コマンド

各 Phase の完了時に次を実行する。

```bash
cd apps/api
.venv/bin/python -m pytest -q
```

```bash
cd apps/web
pnpm test -- --run
pnpm lint
pnpm build
```

Phase 2 以降では、追加で大きめの CSV を使った手動確認を行う。

確認観点:

- upload response が肥大化しない
- 初期表示が preview だけで成立する
- paged rows API が期待通り返る
- `Prepare` / `Explore` / `Workflow` は全体データで動く

## 10. 完了定義

この計画は、次の状態になったら完了とする。

- `Explore` が明確な判断と次アクションを返す
- 大きい workbook でも初期表示が破綻しない
- 旧 Review / Proposal 系が現行主導線から消えている
- README / UI / export がローカル feasibility checker として一貫している
- backend / frontend のテスト、lint、build が通る
