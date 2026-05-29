# Subagent Operating Model

## Purpose

Lunar Agents の開発・実験を、複数の専門サブエージェントで分担する。対象はソフトウェア実装だけではない。国際探査シナリオの分析、地理モデル、環境モデル、物理モデル、制度・インフラモデル、実験実行、結果レビューまでを同じ運用仕様で扱う。

この運用モデルは Codex と Claude Code の共通仕様である。どちらのツールで実行しても、同じ role、work order、human gate に従う。

## Architecture Constraints

- 依存方向は `tools -> scenarios -> environments -> core` に固定する。
- `core/` は月面固有概念を持たない。
- 月面固有の地理・環境・物理モデルは `environments/lunar_2d/` と `scenarios/` に置く。
- `materials/` は参照専用で変更しない。
- 実験結果は `experiments/results/` に置き、原則コミットしない。
- LLM プロンプトには定量情報を渡し、「危険」「安全」「豊富」などの判断語はできるだけ渡さない。

## Role Groups

### Management

| Role | Main responsibility |
|---|---|
| `manager` | 作業分解、依存管理、human gate 管理、最終統合判断の補助 |
| `quality-gate` | 依存方向、変更範囲、互換性、未コミット混入、テスト結果の確認 |

### Scenario and Model Design

| Role | Main responsibility |
|---|---|
| `international-scenario-analyst` | JAXA、Artemis、ILRS、ESA、ISRO、ISECG などの国際探査シナリオを実験軸へ翻訳 |
| `scenario-designer` | 実験仮説、scenario YAML、config、sweep plan、評価指標を設計 |
| `geography-modeler` | 月南極の静的地理モデルを検討・更新 |
| `environment-modeler` | フレア、日照、通信途絶など時間変化する環境モデルを検討・更新 |
| `physics-modeler` | バッテリー、移動コスト、発電、熱、通信、運搬などの簡易物理モデルを検討・更新 |
| `policy-infra-modeler` | 安全区域、データ共有、通信・電力インフラ、相互運用性を検討・更新 |
| `model-validation-agent` | モデルの前提、数値範囲、ログ/指標との整合を確認 |

### Implementation and Experimentation

| Role | Main responsibility |
|---|---|
| `developer` | 指定された所有範囲で実装する |
| `test-agent` | 単体・統合・回帰テストを追加し、Ollama なし検証を維持する |
| `experiment-runner` | batch、短時間 run、承認済み PDCA、実験成果物生成を担当する |
| `experiment-reviewer` | diagnostics、failure modes、report、次 sweep 案を作成する |
| `mid-run-monitor` | 実行中の長時間 run の部分ログを Step N 毎に分析し、早期診断・早期中断シグナルを返す（2026-05-03 追加） |
| `code-fix-agent` | 失敗テストとソースを読み、修正パッチを返す（`tools/code_agent.py` 経由、2026-05-03 追加） |

## Model Layers

モデル検討は以下の三層を分けて扱う。

| Layer | Meaning | Typical fields |
|---|---|---|
| Geography model | 静的な地形・空間条件 | `terrain_type`, `slope_deg`, `roughness`, `illumination_fraction`, `water_potential`, `shelter`, `passable` |
| Environment model | 時間変化する外乱 | solar flare, communication blackout, illumination window, event warning |
| Physics model | 状態遷移の計算則 | battery cost, base recharge, movement cost multiplier, sample mass, communication range |

制度・インフラモデルは Phase 1.7 以降で加える横断層として扱う。安全区域、データ共有ポリシー、通信・電力インフラ、相互運用性は、地理・環境・物理に直接混ぜず、scenario/config で明示する。

## Workflow

1. `manager` が work order を作成する。
2. 必要に応じて `international-scenario-analyst`、`geography-modeler`、`environment-modeler`、`physics-modeler`、`policy-infra-modeler` がモデル提案を作る。
3. モデル前提が変わる場合は human gate G1 に進む。
4. `scenario-designer` が scenario/config/plan と評価指標を整理する。
5. `developer` と `test-agent` が指定された所有範囲で実装・検証する。
6. `quality-gate` が依存方向、変更範囲、既存互換性、テスト結果を確認する。
7. `experiment-runner` が承認済み範囲で実験を回す。
8. `experiment-reviewer` が診断と次 sweep 案を作る。
9. 重要結果は human gate G3 で人間がレビューし、次の方針を決める。

## Work Isolation

- 複数エージェントが同時に実装する場合は branch または git worktree を分ける。
- 1 work order は変更可能ファイルを明示する。
- 互いに同じファイルを編集する work order は同時実行しない。
- 既存の未コミット memo、PDF、画像、実験結果は明示がない限り触れない。

## Automation Boundary

エージェントが自動で進めてよいもの:

- 承認済み範囲内のパラメータ sweep
- 短時間 run
- diagnostics と report の生成
- テスト追加と回帰検証
- 次の work order や sweep の草案作成

人間承認なしで進めないもの:

- 新しい phase や主要シナリオの採用
- 地理・環境・物理・制度モデルの前提変更
- `core/` の設計変更
- 長時間または高コストの実験
- 重要結果の正式解釈
- merge、push、PR 作成などの統合操作

## Concurrency Patterns（2026-05-03 追加）

長時間 run（duration=100、12 agents 規模で 80〜100 分）における待ち時間を削減するため、以下の並列パターンを採用してよい。

### Mid-run analysis pattern

実行中の `state.jsonl` / `memory_reasoning.jsonl` / `messages.jsonl` はリアルタイムで書き込まれるため、`mid-run-monitor` が部分データを読んで分析できる。

- Step N（例: N=20）時点で部分ログを Claude API に渡し、構造的問題を診断する
- 予測される最終指標から判断して、最終結果を待つ価値が無い場合は **G3 を待たずに run を中断** してよい（中断は人間判断ではなく自動化の範囲とする。ただし「結果の解釈」は引き続き G3）
- 1回の run 中に最大 3 回まで mid-run analysis を起動できる

### Dev PDCA pattern

`tools/dev_pdca.py` を介して、実装・テスト・レビューを自動サイクルで回す。

- `code-fix-agent` が失敗テストを読んでパッチを返す
- `test-agent` が pytest を実行する
- `code-fix-agent` が diff をレビューする
- グリーンになるまでループ（最大 `max_cycles`）

このパターンは `developer` の所有範囲内で動かす。所有範囲外（`core/`, `materials/` 等）の修正が必要な場合は通常の human gate に戻す。

### 並列起動可能な作業

以下は同時に走らせてよい:

- 長時間 run の実行と、その部分ログを読む `mid-run-monitor`
- 互いに依存しない複数の `developer` work order（変更可能ファイルが重ならない場合）
- 実験の `experiment-runner` と、過去結果を読む `experiment-reviewer`

並列起動の禁止条件は §Work Isolation を参照。

### Interdependent parallel pattern（2026-05-03 追加）

依存はあるが、同時に長時間の実装スレッドを走らせたいとき（例: 一方が新しい指標を生成し、他方がそれを消費する UI/レポートを書く）に使う。狙いは **マージ直前に型・スキーマがずれて齟齬が出る** ことを防ぐこと。

採用する道具:

1. **Interface contract** — `docs/subagents/contracts/<id>.md`
   依存しあう work order の **公開接点（関数シグネチャ、データクラス、JSONL 行形式、CLI フラグ）** を 1 ファイルに固定する。実装開始前に owner 全員が `status: accepted` で同意する。実装中の調整は contract の変更で行い、口頭・チャットで進めない。
2. **Active work ledger** — `docs/subagents/active-work.md`
   現在進行中の work order 一覧。新しい work order を切る前と、依存 work order を読む前に **必ず読む**。同じ `allowed_write_paths` または `contracts` を `active` で重ねない。
3. **Contract test** — `tests/contracts/test_<slug>_contract.py`
   contract のシグネチャ・スキーマ・不変条件を実装に対して assert する薄いテスト。両 owner の実装が contract に従っていれば green、ずれた瞬間に red で検出する。

work order 側では `work-order-template.yaml` の `contracts.consumes` / `contracts.produces` と `depends_on.work_orders` を埋めて、**どの contract のどの version を前提にしているか** を明示する。consumes 側の contract が version を上げた場合、消費側の work order は再確認するまで merge しない。

起動順序:

1. `manager` または依頼元が contract を `draft` で作る（公開接点だけ書く）。
2. 依存しあう work order の owner 全員が contract を読み、`accepted` に上げる（human gate G1 が必要なモデル前提変更を含む場合は人間承認も）。
3. 各 owner は別ブランチ／worktree で並列に実装する。`tests/contracts/` の contract test を最初に走らせる。
4. 途中で接点を変えたい場合は contract の version を上げ、change log に書き、影響を受ける owner 全員が再 accept してから実装を進める。
5. 最後に通常の `quality-gate` と human gate G4 で統合する。

禁止条件:

- contract が `draft` のまま実装を進める
- ledger に登録せずに並列で着手する
- 依存先 contract を勝手に書き換える（必ず両 owner の合意 + version bump）
