# Current Capabilities

このファイルは `tools/docs_sync_check.py` で生成する。手で直さない。
実装を変えたら `python tools/docs_sync_check.py --write` で更新する。

## Viewer API

| Method | Path | Handler | Summary |
| --- | --- | --- | --- |
| `GET` | `/` | `root` | ビューア HTML を返す (APIキー注入 or fallback)。 |
| `GET` | `/api/agent-roster` | `get_agent_roster` | MVP-003: guide / partner などの抽象role stateを返す。 |
| `POST` | `/api/agent-roster/select` | `select_agent_roster_role` | MVP-003: active roleを選択する。 |
| `GET` | `/api/assessment-lab` | `get_assessment_lab` | MVP-005: assessment / benchmark category stateを返す。 |
| `POST` | `/api/assessment-lab/evaluate` | `evaluate_assessment_category` | MVP-005: benchmark categoryを公開安全な範囲で評価する。 |
| `GET` | `/api/data/{run_id}/{file}` | `get_data_file` | データファイルを配信する (§21.3)。 |
| `GET` | `/api/governance-fde` | `get_governance_fde` | MVP-006: governance layerとFDE packet stateを返す。 |
| `POST` | `/api/governance-fde/decide` | `decide_governance_fde` | MVP-006: FDE decision packetを公開安全な範囲で評価する。 |
| `GET` | `/api/health` | `health` | ヘルスチェック (§21.4)。 |
| `GET` | `/api/intake-lifecycle` | `get_intake_lifecycle` | MVP-008: intake / worldbuilding / lifecycle guard stateを返す。 |
| `POST` | `/api/intake-lifecycle/draft` | `draft_intake_lifecycle` | MVP-008: 追加依頼を外部writeなしのdraft candidateとして評価する。 |
| `GET` | `/api/labels` | `get_labels` | 日本語ラベルマップを返す (WO-010 §5.3 / §19.3.1)。 |
| `GET` | `/api/motif-arcs` | `get_motif_arcs` | MVP-004: public-safe motif arc packを返す。 |
| `POST` | `/api/motif-arcs/evaluate` | `evaluate_motif_arc` | MVP-004: motif arc のArchetype / World guaranteeを確認する。 |
| `GET` | `/api/operator-mode` | `get_operator_mode` | MVP-001: operator viewpoint state を返す。runtime-onlyで永続化しない。 |
| `POST` | `/api/operator-mode/entry` | `enter_operator_mode` | MVP-001: 選択agentのinspection viewpointへ入る。 |
| `POST` | `/api/operator-mode/return` | `return_operator_mode` | MVP-001: replay viewpointへ戻る。 |
| `GET` | `/api/repo-skill-mesh` | `get_repo_skill_mesh` | MVP-007: repo-as-skill / distributed ops guard stateを返す。 |
| `POST` | `/api/repo-skill-mesh/evaluate` | `evaluate_repo_skill_mesh` | MVP-007: skill call / distributed ops planを公開安全な範囲で評価する。 |
| `GET` | `/api/runs` | `list_runs` | 利用可能な run 一覧を返す (§21.2)。 |
| `POST` | `/api/runs` | `create_run` | UI から新しい sample simulation run を作る。 |
| `GET` | `/api/settings` | `get_settings` | ビューア設定状態を返す。API キー値は返さない。 |
| `POST` | `/api/settings` | `update_settings` | UI から process-local な設定を更新する。 |
| `GET` | `/api/world-bridge` | `get_world_bridge` | MVP-002: 三層 world bridge state を返す。runtime-onlyで永続化しない。 |
| `POST` | `/api/world-bridge/transition` | `transition_world_bridge` | MVP-002: physical / simulated / liminal のlayer移動を行う。 |

## Data File Allowlist

生成元: `tools/urban_viewer_server.py` の `ALLOWED_FILES` / `AGENT_PROFILES_RE`。

| File | Mode |
| --- | --- |
| `activity_plans.jsonl` | exact |
| `agent_profiles_N100.json` | exact |
| `agent_states.jsonl` | exact |
| `aois.geojson` | exact |
| `interaction_events.jsonl` | exact |
| `matrix_events.jsonl` | exact |
| `metrics.json` | exact |
| `poi_visit_records.jsonl` | exact |
| `pois.geojson` | exact |
| `relationships.jsonl` | exact |
| `roadnet.geojson` | exact |
| `summary.json` | exact |
| `^agent_profiles_N\d+\.json$` | regex |

## Runtime Settings

`POST /api/settings` は process-local 更新のみ行う。`.env`、OS keychain、Secret Manager には保存しない。

| Env Var | Settings Field | Note |
| --- | --- | --- |
| `GOOGLE_MAPS_API_KEY` | `maps.api_key` | Google Maps JS API key。GET /api/settings は実値を返さず present/absent のみ返す。 |
| `GOOGLE_MAPS_MAP_ID` | `maps.map_id` | Google Maps Map ID。DEMO_MAP_ID は UI へ実値表示しない。 |
| `DATA_SOURCE` | `data.source` | 現在の実装済み値は local のみ。 |
| `DATA_DIR` | `data.root` | run directory を探すローカル data root。 |
| `LLM_PROVIDER` | `llm.provider` | rule / local / vertex。 |
| `LLM_MODEL` | `llm.model` | local / cloud provider の model identifier。 |
| `LLM_BASE_URL` | `llm.base_url` | local OpenAI-compatible endpoint。 |
| `LLM_MODEL_DIR` | `llm.model_dir` | local model path fallback。 |
| `GOOGLE_CLOUD_PROJECT` | `cloud.google_cloud_project` | Vertex AI 利用時の Google Cloud project。 |

## Supported Data Sources

| Value | Status |
| --- | --- |
| `local` | implemented |

## Simulation CLI: `run`

| Flag | Default | Help |
| --- | --- | --- |
| `--activity-plans` | `` | activity_plans.jsonl のパス (任意 / WO-015 optional input) |
| `--agents` | `100` | --sample 生成時のエージェント数 (既定 100) |
| `--aois` | `` | aois.geojson のパス (任意 / summary 件数のみ) |
| `--llm` | `rule` | LLM プロバイダ (既定 rule=RuleBasedProvider / local=OpenAI-compatible local endpoint / vertex=VertexGeminiProvider)。vertex 時は GOOGLE_CLOUD_PROJECT 環境変数と ADC 認証が必要 (spec §17.5)。local 時は LLM_BASE_URL / LLM_MODEL を参照する。 |
| `--matrix-agent-id` | `` | takeover 対象の既存 agent id (未指定時は最小 id) |
| `--matrix-evidence-ref` | `matrix_events.jsonl` | world_transition の evidence ref (既定 matrix_events.jsonl) |
| `--matrix-evidence-type` | `matrix_event` | world_transition の evidence type (既定 matrix_event) |
| `--matrix-gate-action` | `public_pr` | human_gate の対象 action (既定 public_pr) |
| `--matrix-gate-reason` | `operator_agent_human_gate` | human_gate の理由 (既定 operator_agent_human_gate) |
| `--matrix-gate-status` | `requires_human` | human_gate の状態 (既定 requires_human) |
| `--matrix-guide-layer` | `real` | guide_agent が説明する world layer (既定 real) |
| `--matrix-guide-tick` | `` | guide_agent heartbeat を出力する tick (未指定時は出力しない) |
| `--matrix-human-gate-tick` | `` | operator_agent human_gate を出力する tick (未指定時は出力しない) |
| `--matrix-mode` | `False` | MATRIXモードを有効化し、任意出力 matrix_events.jsonl を生成する。既定 off では既存 replay と同じく出力しない。 |
| `--matrix-role` | `sentinel_mvp` | MATRIXモードの public alias (既定 sentinel_mvp) |
| `--matrix-source-layer` | `real` | world_transition の source layer (既定 real) |
| `--matrix-swarm-heartbeat-interval-ticks` | `1` | sentinel_swarm heartbeat の期待間隔 tick 数 (既定 1) |
| `--matrix-swarm-heartbeat-tick` | `` | sentinel_swarm heartbeat を出力する tick (未指定時は出力しない) |
| `--matrix-swarm-orphan-tolerance` | `0` | sentinel_swarm の orphan 許容数 (既定 0) |
| `--matrix-swarm-stale-after-ticks` | `3` | sentinel_swarm を stale とみなす heartbeat 欠落 tick 数 (既定 3) |
| `--matrix-swarm-stale-tick` | `` | sentinel_swarm stale_report を出力する tick (未指定時は出力しない) |
| `--matrix-target-layer` | `virtual` | world_transition の target layer (既定 virtual) |
| `--matrix-transition-tick` | `` | world_transition を出力する tick (未指定時は出力しない) |
| `--matrix-trigger-id` | `assume_sentinel` | MATRIXモードの内部 trigger id (既定 assume_sentinel) |
| `--matrix-ttl-ticks` | `1` | takeover を保持する tick 数 (既定 1) |
| `--no-summaries` | `False` | interaction summary の生成をスキップする (#1 会話オプション)。off 時 interaction_events の summary は空文字になる。--llm と独立に制御できる。既定はサマリ生成あり (on)。 |
| `--out` | `` | 出力ディレクトリ (末尾が run_id) |
| `--pois` | `` | pois.geojson のパス (--sample 無しで必須) |
| `--profiles` | `` | agent_profiles_*.json のパス (--sample 無しで必須) |
| `--roadnet` | `` | roadnet.geojson のパス (任意 / summary 件数のみ) |
| `--sample` | `False` | 静的データを内部生成してから simulate する |
| `--sample-pois` | `300` | --sample 生成時の POI 数 (既定 300) |
| `--seed` | `42` | 乱数 seed (既定 42) |
| `--ticks` | `24` | シミュレーション tick 数 (既定 24) |

## Drift Gate

CI は `python tools/docs_sync_check.py --check` を実行する。
このファイルが実装から再生成した内容と一致しない場合、PR は docs drift として失敗する。
