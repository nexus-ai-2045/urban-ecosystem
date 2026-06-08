# Current Capabilities

このファイルは `tools/docs_sync_check.py` で生成する。手で直さない。
実装を変えたら `python tools/docs_sync_check.py --write` で更新する。

## Viewer API

| Method | Path | Handler | Summary |
| --- | --- | --- | --- |
| `GET` | `/` | `root` | ビューア HTML を返す (APIキー注入 or fallback)。 |
| `GET` | `/api/data/{run_id}/{file}` | `get_data_file` | データファイルを配信する (§21.3)。 |
| `GET` | `/api/health` | `health` | ヘルスチェック (§21.4)。 |
| `GET` | `/api/labels` | `get_labels` | 日本語ラベルマップを返す (WO-010 §5.3 / §19.3.1)。 |
| `GET` | `/api/operator-mode` | `get_operator_mode` | MVP-001: operator viewpoint state を返す。runtime-onlyで永続化しない。 |
| `POST` | `/api/operator-mode/entry` | `enter_operator_mode` | MVP-001: 選択agentのinspection viewpointへ入る。 |
| `POST` | `/api/operator-mode/return` | `return_operator_mode` | MVP-001: replay viewpointへ戻る。 |
| `GET` | `/api/runs` | `list_runs` | 利用可能な run 一覧を返す (§21.2)。 |
| `POST` | `/api/runs` | `create_run` | UI から新しい sample simulation run を作る。 |
| `GET` | `/api/settings` | `get_settings` | ビューア設定状態を返す。API キー値は返さない。 |
| `POST` | `/api/settings` | `update_settings` | UI から process-local な設定を更新する。 |

## Data File Allowlist

生成元: `tools/urban_viewer_server.py` の `ALLOWED_FILES` / `AGENT_PROFILES_RE`。

| File | Mode |
| --- | --- |
| `activity_plans.jsonl` | exact |
| `agent_profiles_N100.json` | exact |
| `agent_states.jsonl` | exact |
| `aois.geojson` | exact |
| `interaction_events.jsonl` | exact |
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
