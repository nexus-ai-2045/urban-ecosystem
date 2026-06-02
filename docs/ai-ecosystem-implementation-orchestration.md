# AIエージェント人工生態系アプリ 実装オーケストレーション

## 目的

`docs/ai-ecosystem-tool-spec.md` を実装へ移すための作業分解、依存関係、担当ロール、受け入れゲートを定義する。

実装は「常に動くものを保つ」方針で進める。最初はリプレイ可能な地図ビューアを優先し、Cloud Run デプロイで一気通貫を成立させ、LLM社会行動 (Vertex AI / Gemini) は後段で差し込む。

## 正本

- アプリ仕様: `docs/ai-ecosystem-tool-spec.md`
- データ契約: `docs/subagents/contracts/urban-ecosystem-data-contract.md`
- サブエージェント運用: `docs/subagents/operating-model.md`
- Human gates: `docs/subagents/human-gates.md`

## 全体方針

1. データ契約を先に固定する。
2. LLMなしで動くデータローダー、サンプル生成、Google Mapsビューアを先に作る。
3. リプレイと最小シミュレーションを分ける。
4. Cloud Run へデプロイし、公開URLで「100体1日リプレイ」を成立させる。
5. LLM Provider (Vertex AI / Gemini) は後段で差し替え可能にする。
6. 実験結果や生成ログは `experiments/results/` に置き、原則コミットしない。

## Workstreams

| Stream | Role | Goal | Depends on | Output |
| --- | --- | --- | --- | --- |
| S0 Contract | manager | データ契約と作業順を固定する。 | none | data contract, orchestration doc |
| S1 Data Loader | developer + test-agent | GeoJSON/JSON/JSONLを検証・正規化する。 | S0 | `environments/urban_2d/data_loader.py`, tests |
| S2 Sample Data | developer | 100 agent/POI/AOI/Road の静的合成データを作る (挙動ログは S4)。 | S1 contract | `tools/generate_urban_sample.py` |
| S3 Replay Viewer | developer + test-agent | Google Maps上でサンプルをリプレイする。 | S0, S2 | `tools/urban_viewer/`, `app/main.py` |
| S4 Rule Simulation | developer + test-agent | ルールベースで状態/訪問/交流ログを生成する。 | S1, S2 | `environments/urban_2d/simulation.py`, CLI |
| S5 Cloud Run Deploy | devops + quality-gate | アプリをコンテナ化しCloud Runへデプロイする。 | S3, S4 | `Dockerfile`, `cloudbuild.yaml`, deploy doc |
| S6 LLM Social Agents | scenario-designer + developer | 行動決定、会話、関係性更新を Vertex AI / Gemini 化する。 | S4 | `app/llm_provider.py`, prompts |
| S7 Quality Gate | quality-gate | 依存方向、テスト、互換性、生成物混入を確認する。 | each stream | review notes |

## 推奨実装順

1. S1 Data Loader
2. S2 Sample Data
3. S3 Replay Viewer
4. S4 Rule Simulation
5. S5 Cloud Run Deploy

S5 (Cloud Run Deploy) は S3 (ビューア) と S4 (シミュレーション) が動いてから着手する。第一成果物 = S1〜S5 を通した「Cloud Run 上の100体1日リプレイ」。S6 LLM Social Agents は S5 完了後の後段マイルストーン。

## Architecture Guardrails

- urban-ecosystem は単独デプロイ可能なアプリとして構成する (Cloud Run Service)。
- 内部依存は `app -> environments/urban_2d` (環境固有モデル)。月面系の `tools/scenarios/core` 階層には依存しない。
- 都市固有のモデルは `environments/urban_2d/` に置く。
- `core/` は原則変更しない。必要になったら human gate G1/G4。
- `materials/` は変更しない。
- LLM後段は Vertex AI / Gemini を `app/llm_provider.py` 抽象越しに使う。直接呼び出し禁止、既存wrapper方針に従う。
- `GOOGLE_MAPS_API_KEY` / Vertex 用 SA は Secret Manager / Workload Identity 経由。コード・ログ・イメージに焼かない。
- Google Maps JavaScript APIは課金有効化が必要なため、CI/テストではAPIキーなしのフォールバック地図を使う。
- 大きな生成物 (大規模 `agent_states.jsonl` など) はイメージに含めず GCS へ。実験出力はコミットしない。

## Adopted External Building Blocks

| Area | Use | Notes |
| --- | --- | --- |
| Map loading | Google Maps JavaScript API `importLibrary()` | 公式の動的ライブラリ読込。 |
| GeoJSON rendering | Google Maps Data layer | POI/AOI/road レイヤー。 |
| Agent markers | Advanced Markers | id/色付きHTML/CSSマーカー。Map ID 必須。 |
| Marker clustering | `@googlemaps/markerclusterer` | MVP任意、大規模で必須。 |
| Reference code | `googlemaps/js-samples` | Maps JS実装参考。 |
| Web framework | FastAPI + uvicorn | Cloud Run Service の常駐web。 |
| Runtime platform | Cloud Run (Service / Job) | Service=web常駐、Job=大規模sim事前生成。 |
| Object storage | Cloud Storage | 大規模リプレイJSONLの置き場 (スケール時)。 |
| LLM (後段) | Vertex AI / Gemini | 行動決定/会話/関係性更新の LLM 化。MVPはルールベースのみ。 |

## Parallelization Rules

- S1とS3は同時に始めない。S3は contract だけでモック実装可能だが、S1の型が固まってからの方が手戻りが少ない。
- S2とS3は contract 固定後に並列可。書き込み先が重ならない。
- S3とS4は `agent_states.jsonl` の contract に従えば並列可。
- S5 (Cloud Run Deploy) は S3/S4 完了後の単独ストリーム。
- Contract変更が必要になった場合は `urban-ecosystem-data-contract.md` のversionを上げてから進める (semver: §Versioning)。互換破壊は Human Gate G1。

## Human Gates

| Gate | Trigger | Decision |
| --- | --- | --- |
| G0 | 各work order開始前 | 範囲、変更可能ファイル、終了条件を確認する。 |
| G1 | 都市モデルやデータ契約を変える時 | データ/モデル前提の変更を承認する (contract MAJOR 変更含む)。 |
| G2 | 長時間・高コストLLM実験前 | 外部API利用量と実験範囲を承認する。 |
| G3 | 創発行動の解釈時 | 観測結果の主張を人間が判断する。 |
| G4 | main統合、PR、正式ロードマップ反映、Cloud Run 本番デプロイ | 統合・本番反映判断を人間が行う。 |

## First Batch Work Orders

### WO-URBAN-001 Data Loader

- owner: developer
- support: test-agent, quality-gate
- allowed paths:
  - `environments/urban_2d/`
  - `tests/environments/test_urban_data_loader.py`
- acceptance:
  - POI/AOI/Road/Profile/JSONLを読み込める。
  - invalid inputのエラーが人間に読める。
  - contract testが通る。

### WO-URBAN-002 Sample Data Generator

> scope (2026-05-29 CEO 確定 / spec §19 準拠): **静的入力データのみ**を生成する。
> 挙動ログ (agent_states.jsonl / poi_visit_records.jsonl / interaction_events.jsonl) は
> WO-URBAN-004 Rule Simulation の責務 (§13.3 シミュレーション検証 = WO-004)。

- owner: developer
- support: test-agent
- allowed paths:
  - `tools/generate_urban_sample.py`
  - `tests/tools/test_generate_urban_sample.py`
- acceptance:
  - 100 agents、300 POIs、10 AOIs、~299 roads を生成 (summary.ticks 既定 24)。
  - 出力は pois.geojson / aois.geojson / roadnet.geojson / agent_profiles_N100.json / summary.json の静的 5 ファイル。
  - 生成物が data-contract の Field Types and Constraints と spec §13.1 検証を全て通過する。
  - summary.json の counts が実生成数 (agents/pois/aois/roads/interactions/ticks) と一致。
  - POI カテゴリ分布が §19.3.1 と一致し、全座標が §19.2 bbox 内に収まる。
  - 全 poi_id/agent_id 参照が解決可能 (dangling 参照ゼロ)。
  - `--seed` 固定で静的 4 ファイル (pois/aois/roadnet/agent_profiles) がバイト一致で再現 (summary.json は started_at を含むため対象外)。

### WO-URBAN-003 Replay Viewer

- owner: developer
- support: test-agent, quality-gate
- allowed paths:
  - `tools/urban_viewer/`
  - `app/main.py`
  - `tests/app/test_main.py`
- acceptance:
  - FastAPI サーバーでGoogle Mapsビューが開く。
  - `GOOGLE_MAPS_API_KEY` がない場合はフォールバック地図でテストできる。
  - POI/AOI/道路はGoogle Maps Data layerで表示する。
  - エージェントはAdvanced Markerで表示する。
  - MarkerClustererを後付け可能な構造にする。
  - POI/AOI/道路/エージェントを表示できる。
  - 再生、停止、時刻スライダー、エージェント詳細が動く。
  - リプレイ一次ソースは `agent_states.jsonl` (tick を持つ唯一のファイル)。

### WO-URBAN-004 Rule Simulation

- owner: developer
- support: scenario-designer, test-agent
- allowed paths:
  - `environments/urban_2d/`
  - `tools/urban_simulation_cli.py`
  - `tests/environments/test_urban_simulation.py`
- acceptance:
  - LLMなしで100 agents、24 tick以上を完走する。
  - `agent_states.jsonl`、`poi_visit_records.jsonl`、`interaction_events.jsonl` を出力する。
  - 同一 seed で出力が byte 一致する (決定論)。
  - relationship 遷移が spec §9.9 の隣接遷移で説明可能。
  - replay viewerが出力を読める。

### WO-URBAN-005 Cloud Run Deploy

- owner: devops
- support: developer, quality-gate
- depends on: WO-URBAN-003 (Replay Viewer), WO-URBAN-004 (Rule Simulation)
- allowed paths:
  - `Dockerfile`
  - `cloudbuild.yaml`
  - `requirements.txt`
  - `app/main.py`, `app/config.py`, `app/data_access.py`
  - `docs/deploy.md`
  - `tests/app/test_main.py`
- acceptance:
  - `docker build` がローカルで成功し、GPU/メディア処理依存を含まない。
  - コンテナ起動後 `GET /api/health` が 200 を返す。
  - `GET /` が地図ビューアHTMLを返し、`GOOGLE_MAPS_API_KEY` 未設定時は fallback 地図に自動切替する。
  - `GET /api/data/{run_id}/{file}` が同梱サンプルの GeoJSON/JSONL を返す。
  - Maps APIキーは Secret Manager 経由でのみ注入され、イメージ・git・ログに平文で含まれない。
  - ランタイム SA が最小権限 (Secret Accessor + 必要時 Storage/Vertex のみ) で構成されている。
  - `gcloud run deploy --source .` でデプロイ手順が `docs/deploy.md` に再現可能な形で記載されている。
  - Cloud Run Service と Job の使い分け方針が spec §17.1 と一致している。
  - 既存 `water_exploration` / `south_pole_survival_survey` を壊さない (urban は独立デプロイ単位)。

## Urban Realism Batch (2026-05-29 CEO)

spec の realism 要件 (CEO 7+1 件) のうち Phase 1 完了分を除く残りを 5 つの WO に分解する。開発・検証の既定エージェント数は **10 体** とする (CEO 確定 2026-05-29 / コスト・速度優先)。生成・シミュレーション・LLM run は `--agents 10` で回す。

| WO | 要件 | owner | depends_on | human gate | 系統 |
| --- | --- | --- | --- | --- | --- |
| WO-URBAN-006 Rich Profile | #3 姓名分割 + 職業/性格/趣味/1日傾向 | developer | — | G1 (contract) | A 起点 |
| WO-URBAN-007 Surname Display | #2 苗字キャラ表示 | developer | 006 | G4 | A |
| WO-URBAN-008 Behavior+Relationship LLM | §10.2 行動決定本体 + 関係理由文 | developer | 006 | G2 (LLM) | A |
| WO-URBAN-009 Road-following Movement | #8 道路追従 (建物 footprint なし) | developer | — | G1 (移動モデル) | B 独立 |
| WO-URBAN-010 Human-readable Labels | 汎用ラベル日本語化 | developer | — | G4 | 独立/軽量 |

推奨実装順:

- ライン A (LLM/表示): WO-006 → (WO-007 ∥ WO-008) → WO-010
- ライン B (移動/独立): WO-009 を A と並列
- WO-006 が WO-007 / WO-008 の共通土台 (surname/given と profile context)。最初に閉じる。
- WO-009 と WO-010 は他 WO と書き込みパスが重ならないため並列可。

Human gate 要点:

- WO-006: profile スキーマ拡張 = data-contract MINOR 改訂 → G1。
- WO-008: Vertex Gemini の利用 → G2 (利用量・実験範囲)。
- WO-009: 移動モデル変更で決定論出力が変わる → G1。

Phase 1 完了済み (本バッチ対象外): viewer ラベル平易化 / 会話要約 LLM 化 / 実店名・擬似苗字 / POI 実名。

## Definition of Done

- 仕様書とデータ契約に反映済み。
- 対応するテストがある。
- `python -m pytest tests/ -v -p no:cacheprovider` または対象範囲のpytestが通る。
- フロント E2E がフォールバック地図で通る。
- 生成物 (実験出力・コンテナイメージ) がコミット対象に混入していない。
- 既存 `water_exploration` と `south_pole_survival_survey` の後方互換を壊していない。

## Current Recommendation

第一成果物 (WO-URBAN-001〜005 を通した「100 体 1 日リプレイ」) は達成済み。

次の着手は Urban Realism Batch の `WO-URBAN-006 Rich Profile` から始める。理由は、姓名分割と profile context が WO-007 (苗字表示) と WO-008 (行動決定 LLM 本体) の共通土台になるため。WO-009 (道路追従) と WO-010 (ラベル日本語化) は書き込みパスが重ならないので並列可。開発・検証は 10 体で回す (CEO 確定 2026-05-29)。
