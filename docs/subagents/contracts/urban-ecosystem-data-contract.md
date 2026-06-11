# Urban Ecosystem Data Contract

status: accepted
version: 0.7.2
owner: manager
updated: 2026-06-12

## Purpose

都市型AIエージェント人工生態系アプリの公開データ接点を固定する。データローダー、合成データ生成、ルールベースシミュレーション、リプレイビューア、Cloud Run デプロイの各 work order は、この contract に従う。

本 contract は `docs/ai-ecosystem-tool-spec.md` の **正本 (source of truth)** であり、spec の §6 データモデル / §9 行動ルール語彙 / §13.1 データ検証はこの contract を参照する。spec と差異が生じた場合は本 contract を優先する。

## File Names

| File | Direction | Required in MVP | Description |
| --- | --- | --- | --- |
| `pois.geojson` | input | yes | POI point features (FeatureCollection)。 |
| `aois.geojson` | input | no | AOI polygon features。 |
| `roadnet.geojson` | input | no | Road LineString features (MVP は表示専用)。 |
| `agent_profiles_N100.json` | input | yes | Agent profile list。 |
| `activity_plans.jsonl` | input | no | Optional activity chain plans。存在する場合のみ schedule-driven destination selection に使う。 |
| `agent_states.jsonl` | output/input | yes | Tick 単位の agent 状態。リプレイ一次ソース (tick を持つ唯一のファイル)。 |
| `poi_visit_records.jsonl` | output/input | no | 訪問履歴 (詳細パネル補助表示)。 |
| `interaction_events.jsonl` | output | yes | 会話・出会い・別れ・喧嘩などの社会イベント。 |
| `relationships.jsonl` | output | no | 関係性スナップショット (任意 / §Relationship Snapshot)。 |
| `matrix_events.jsonl` | output/input | no | MATRIXモードの role takeover / world transition イベント (任意 / §MATRIX Mode Event JSONL)。 |
| `summary.json` | output | yes | run の件数と集計指標。 |
| `metrics.json` | output | yes | Individual / Scenario / Society Simulation 評価指標。 |

## Common Rules

- 全タイムスタンプはシミュレーション内の `day` と `time` で表す (実世界時刻ではない)。
- `time` は `HH:MM:SS`。MVP では秒は常に `00`。
- `tick` は 0 始まりの非負整数。`tick`↔`time` の変換は §Time and Tick。
- ID は 1 run 内で安定。命名規約は §Naming Conventions。
- JSONL は 1 行 1 JSON オブジェクト。
- reader は未知の任意フィールドを可能な限り保持する。
- 座標の持ち方は 2 系統ある。§Coordinate Systems を厳守し、混在させない。

## Coordinate Systems

座標は用途で 2 系統に分かれる。**両者を混在させない。**

1. **GeoJSON (POI / AOI / Road)**: `geometry.coordinates` に RFC 7946 準拠の `[lon, lat]` 順で持つ。`lat`/`lon` を properties に重複させない。
2. **Flat JSON (AgentProfile.initial_position / AgentState / VisitRecord)**: `lat` と `lon` の個別キーで持つ。

共通: WGS84。`lat ∈ [-90, 90]`、`lon ∈ [-180, 180]`。

## Naming Conventions

| エンティティ | id 形式 | 例 |
| --- | --- | --- |
| POI | 文字列 `poi_<n>` (予約値 `initial_position` を除く) | `poi_001`, `poi_home_001`, `poi_work_001` |
| AOI | 文字列 `aoi_<n>` | `aoi_001` |
| Road | 文字列 `road_<n>` | `road_001` |
| Agent | **integer** (0 始まり連番を推奨) | `26` |

`category` は `"<group>-<sub>"` 形式のハイフン区切り (スペースを入れない)。例: `amenity-cafe`, `shop-convenience`。spec §9.4 の目的地選択は `category` の部分一致でマッチする。

## Time and Tick

- `TICK_MINUTES = 5` (1 tick = 5 分)。
- 1 日は `08:00:00` 開始。`tick = 0` が `08:00:00`。
- 変換式: `minutes = 8*60 + tick * TICK_MINUTES`。`time = HH:MM:00` (HH = minutes // 60, MM = minutes % 60)。
- 1 日 = 08:00〜24:00 で最大 192 tick。MVP の受け入れは 24 tick 以上 (= 2 時間分) で可。
- `day` は 0 始まり。`day` が増える場合も `time` は当日の時刻 (08:00 起点) を表す。
- `(day, time)` は `tick` から導出され、矛盾してはならない (検証対象)。

## Enumerations

固定語彙。未知値は reader が warning として人間可読に列挙する (即エラーにはしない)。

| フィールド | 許容値 | 備考 |
| --- | --- | --- |
| AgentState.`status` | `moving`, `arrived`, `staying` | 内部状態機械 (idle/moving/at_poi) の出力写像。idle・滞在中→`staying`、移動中→`moving`、到達した tick→`arrived` (spec §9.2)。 |
| AgentState.`action` / VisitRecord.`reason` | `commute`, `work`, `study`, `lunch`, `errand`, `social`, `go_home`, `wander`, `no_target` | spec §9.3 の reason 列と一致。 |
| Activity.`kind` | `home`, `work`, `study`, `lunch`, `errand`, `social`, `go_home`, `wander` | `activity_plans.jsonl` 専用。未知値は schedule の意味が曖昧になるため ValidationError。`home` は出力 action/reason では `go_home` へ写像する。 |
| VisitRecord.`action` | `visit` | MVP は `visit` のみ。 |
| InteractionEvent.`type` | `meeting`, `conversation`, `conflict`, `farewell` | 出会い / 会話 / 喧嘩 / 別れ (spec §9.8)。 |
| relationship `state` | `rival`, `stranger`, `acquaintance`, `friend`, `close_friend` | score しきい値で算出 (spec §9.9)。 |
| Agent `role` | `office_worker`, `student`, `other` (既定) | profile に role が無い場合は `other` 扱い。将来 role 追加可。 |
| MatrixEvent.`type` | `takeover_start`, `takeover_end`, `world_transition`, `heartbeat`, `stale_report`, `human_gate` | MATRIXモード専用。MATRIXモード off の既存 run では出力しない。 |
| MatrixEvent.`matrix_role` | `sentinel_mvp`, `bridge_agent`, `guide_agent`, `operator_agent`, `sentinel_swarm` | 公開実装 alias。保護されたキャラクター名は使わない。 |
| MatrixEvent.`world_layer` / `source_layer` / `target_layer` | `real`, `virtual`, `liminal` | Three Worlds の最小 triad。 |
| MatrixEvent.`evidence_type` | `replay_state`, `matrix_event`, `human_gate`, `derived_metric` | world transition の根拠種別。外部秘密や保護表現は入れない。 |
| MatrixEvent.`gate_action` | `public_pr`, `git_push`, `cloud_run_deploy`, `external_api`, `secret_access`, `cost_spend` | `operator_agent` human gate の対象 action。 |
| MatrixEvent.`gate_status` | `requires_human`, `approved`, `rejected` | MVP は `requires_human` を出力し、実行はしない。 |
| MatrixEvent.`swarm_status` | `alive`, `stale` | `sentinel_swarm` の heartbeat / stale self-report 状態。 |

## POI Feature

GeoJSON `FeatureCollection`。各 feature は Point geometry。

```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [139.0, 35.0] },
  "properties": { "id": "poi_001", "category": "amenity-cafe", "name": "Cafe Example", "source": "synthetic" }
}
```

Required properties: `id` (string `poi_*`), `category` (`<group>-<sub>`)。
Optional properties: `name`, `source`。

## AOI Feature

GeoJSON `FeatureCollection`。各 feature は Polygon または MultiPolygon geometry。`geometry.type` と重複する `geometry_type` プロパティは持たない。

```json
{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [[[139.0, 35.0], [139.1, 35.0], [139.1, 35.1], [139.0, 35.0]]] },
  "properties": { "id": "aoi_001", "name": "Shibuya Area", "category": "district" }
}
```

Required: `id` (string `aoi_*`)。Optional: `name`, `category`。

## Road Feature

GeoJSON `FeatureCollection`。各 feature は LineString または MultiLineString geometry。

```json
{
  "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [[139.0, 35.0], [139.001, 35.001]] },
  "properties": { "id": "road_001", "length_m": 128.4, "walkable": true }
}
```

Required: `id` (string `road_*`)。Optional: `length_m` (number >= 0), `walkable` (boolean / default true)。

## Agent Profile

```json
{
  "id": 26,
  "name": "井上翔",
  "surname": "井上",
  "given": "翔",
  "age": 30,
  "gender": "male",
  "occupation": "エンジニア",
  "personality": "几帳面",
  "hobbies": ["プログラミング", "ゲーム"],
  "day_pattern": "morning",
  "initial_position": { "lat": 35.0, "lon": 139.0 },
  "home_poi_id": "poi_home_001",
  "role": "office_worker",
  "social_networks": [61, 97, 99]
}
```

Required: `id` (integer), `name` (string), `initial_position` (`{lat, lon}`)。
Optional (既存): `age` (integer >= 0), `gender` (string), `description` (string), `home_poi_id` (既存 POI id), `work_or_school_poi_id` (既存 POI id), `role` (§Enumerations), `social_networks` (既存 agent id の配列 / 自己 id を含めない / 重複なし)。
Optional (WO-006 追加): `surname` (string / 日本語姓), `given` (string / 日本語名 / `name == surname + given` を保証), `occupation` (string / 職業詳細), `personality` (string / 性格傾向), `hobbies` (string の配列 / 1 件以上), `day_pattern` (`"morning"` | `"night"` | `"balanced"` / §9.3 時刻帯テーブルと矛盾しない行動傾向値)。

**後方互換**: WO-006 追加フィールドはすべて optional。既存の simulation / viewer / replay は未知フィールドを保持 (§Common Rules) するため、profile に追加フィールドが混在しても壊れない。

## Activity Plans JSONL (optional)

`activity_plans.jsonl` は optional input。存在しない場合、simulation は既存の rule-driven destination selection をそのまま使う。存在する場合は、該当 agent/day/time の active activity を §9.3 より先に評価する。

```json
{
  "agent_id": 26,
  "day": 0,
  "activities": [
    {
      "kind": "lunch",
      "start": "12:00:00",
      "end": "13:00:00",
      "category": "amenity-cafe"
    },
    {
      "kind": "work",
      "start": "13:00:00",
      "end": "18:00:00",
      "poi_id": "poi_work_001"
    }
  ]
}
```

Required row fields: `agent_id` (既存 agent), `day` (0 始まり非負整数), `activities` (array)。
Required activity fields: `kind` (§Enumerations), `start`, `end` (`HH:MM:SS`)。
Optional activity fields: `poi_id` (既存 POI id), `category` (`<group>-<sub>`)。

Validation:
- `(agent_id, day)` は 1 行だけ。
- 同一行内の activity time range は重複してはならない。
- `end` は `start` より後。
- `poi_id` は指定時のみ既存 POI id と照合する。
- reader は row/activity の未知フィールドを `extra` として保持する。

Destination mapping:
- `poi_id` 指定は固定目的地。
- `category` 指定は同 category の POI 候補を取り、既存の LLM category narrowing と最近傍選択へ委譲する。
- `home` は `go_home` action/reason に写像し、`home_poi_id` または初期位置最近傍へ解決する。
- `work` / `study` は `work_or_school_poi_id` または初期位置最近傍へ解決する。
- `lunch` / `errand` / `social` / `wander` / `go_home` で `poi_id` も `category` も無い場合は移動せず該当 action で滞在する。

## Agent State JSONL

```json
{
  "tick": 0,
  "day": 0,
  "time": "08:00:00",
  "agent_id": 26,
  "lat": 35.0,
  "lon": 139.0,
  "current_poi_id": "poi_001",
  "action": "commute",
  "target_poi_id": "poi_work_001",
  "status": "moving"
}
```

Required: `tick`, `day`, `time`, `agent_id` (既存 agent), `lat`, `lon`, `action` (§Enumerations), `status` (§Enumerations)。
Optional: `current_poi_id` (既存 POI id), `target_poi_id` (既存 POI id)。
Optional (0.4.2): `route_mode` (`"roadnet"` | `"linear_fallback"`)。移動中または到着 tick に、その移動が道路グラフ経路を使ったか、直線フォールバックへ戻ったかを示す。metrics の `route_fallback_rate` はこの値から再計算できる。

## Visit Record JSONL

```json
{
  "agent_id": 26,
  "day": 0,
  "time": "08:05:00",
  "poi_id": "poi_123",
  "action": "visit",
  "reason": "lunch",
  "lat": 35.0,
  "lon": 139.0
}
```

Required: `agent_id` (既存 agent), `day`, `time`, `action` (= `visit`), `lat`, `lon`。
Optional: `poi_id` (既存 POI id または予約値 `initial_position`), `reason` (§Enumerations)。

## Interaction Event JSONL

```json
{
  "tick": 42,
  "day": 0,
  "time": "11:30:00",
  "type": "conversation",
  "agent_ids": [26, 92],
  "location_poi_id": "poi_123",
  "summary": "Two agents talked about lunch plans.",
  "relationship_delta": { "from": "acquaintance", "to": "friend" },
  "relationship_reason": "カフェでの会話が二人の関係を深めた。"
}
```

Required: `tick`, `day`, `time`, `type` (§Enumerations), `agent_ids` (既存 agent / 要素数 >= 2 / 重複なし / `[min_id, max_id]` 昇順正規化), `summary` (string)。
Optional: `location_poi_id` (既存 POI id), `relationship_delta` (`{from, to}` / 各値は relationship state / state 不変でも `from == to` で出力可), `relationship_reason` (string / 関係変化の理由文 / LLM 生成またはテンプレ文 / `from != to` のときのみ出力し、空文字の場合は出力しない)。

同一 tick・同一正規化ペアの interaction は 1 件まで。1 tick あたりの総数は spec §9.8 の `MAX_INTERACTIONS_PER_TICK` で上限。

## Relationship Snapshot JSONL (optional)

`relationships.jsonl` を出力する場合の各行。リプレイで関係状態を復元するための任意スナップショット。

```json
{
  "tick": 42,
  "agent_ids": [26, 92],
  "score": 6,
  "state": "friend"
}
```

Required (出力する場合): `tick`, `agent_ids` (`[min_id, max_id]`), `score` (integer), `state` (§Enumerations)。

## MATRIX Mode Event JSONL (optional)

`matrix_events.jsonl` は MATRIXモードが有効な run だけが出力する任意イベントログである。MATRIXモードは既定 off であり、このファイルが無い既存 run は従来通り replay できる。

M1-001 で takeover event を固定し、M1-002/M1-003 で `sentinel_mvp` runtime MVP と viewer 表示を実装した。M2-001 では `bridge_agent` の world layer model を固定する。

```json
{
  "tick": 12,
  "day": 0,
  "time": "09:00:00",
  "type": "takeover_start",
  "agent_id": 26,
  "matrix_role": "sentinel_mvp",
  "ttl_ticks": 3,
  "trigger_id": "assume_sentinel",
  "reason": "MATRIXモードの最小 takeover smoke"
}
```

Required: `tick`, `day`, `time`, `type` (§Enumerations), `agent_id` (既存 agent), `matrix_role` (§Enumerations)。

Optional:

- `ttl_ticks` (integer >= 1): takeover が有効な最大 tick 数。`takeover_start` では指定を推奨する。
- `exit_reason` (`ttl_expired`, `manual_release`, `world_transition`, `simulation_end`, `error`): `takeover_end` の終了理由。M1-001 では自由文字列ではなくこの集合から選ぶ。
- `trigger_id` (string): `wake_matrix`, `enter_bridge`, `assume_sentinel` などのオリジナル trigger id。保護された短い台詞は保存しない。
- `source_layer`, `target_layer`, `world_layer` (§Enumerations): `world_transition` と heartbeat/stale 報告で使う。
- `transition_cost` (integer >= 0): layer 移動のコスト。MVP では実時間・課金・token 消費ではなく、replay 比較用の抽象コスト。
- `evidence_type` (§Enumerations): transition の根拠種別。
- `evidence_ref` (string): 根拠への短い参照。file path、event id、human gate id など。secret、個人情報、保護された台詞は入れない。
- `guide_summary` (string): `guide_agent` が rule-based fallback で生成する短い説明。LLM 生成を必須にしない。
- `candidate_transitions` (array): `guide_agent` が提示する候補。各要素は `source_layer`, `target_layer`, `transition_cost`, `evidence_types` を持つ。
- `gate_action` (§Enumerations): `operator_agent` が human gate へ送る高リスク action。
- `gate_status` (§Enumerations): gate 状態。MVP runtime は `requires_human` を出力する。
- `gate_reason` (string): gate 理由。secret、個人情報、外部認証情報は入れない。
- `swarm_status` (§Enumerations): `sentinel_swarm` の状態。heartbeat は `alive`、stale report は `stale` を使う。
- `heartbeat_interval_ticks` (integer >= 1): `sentinel_swarm` が期待する heartbeat 間隔。
- `stale_after_ticks` (integer >= 1): heartbeat 欠落を stale とみなす tick 数。MVP 既定は `3`。
- `orphan_tolerance` (integer >= 0): orphan sentinel の許容数。MVP 初期値は `0`。
- `last_heartbeat_tick` (integer >= 0): stale 判定で参照した最後の heartbeat tick。
- `missed_heartbeats` (integer >= 0): 最後の heartbeat から stale_report までの tick 差。
- `reason` (string): 人間可読な説明。LLM 生成を必須にしない。
- `exchange_cost_payload` (string or dict, optional): `world_transition` で消費した資源を人間可読に記録する。replay で後から集計・比較できる。例: `"cost_unit:1"`。`exchanged=true` の場合は必須。
- `exchanged` (bool, optional): この transition が等価変換として完了したことを示す。`true` の場合、逆方向の移動は元の状態を復元しない (逆 transition は別の新しい event として記録する)。
- `hierarchy_rank` (integer >= 0, optional): `oath_chain` motif (MP-003 / v0.7.1) が付与する命令権限の階層ランク。0 が最上位権限 (apex)。値が小さいほど高い権限を持ち、命令は低い rank 番号から高い rank 番号へ向かう。`takeover_start` で使用する。保護された名称・外部秘密・個人情報を含めない。
- `sworn_duty` (string, optional): `oath_chain` motif (MP-003 / v0.7.1) が付与するエージェントの宣言誓約を人間可読に記録する。「何ができ、何をしてはならないか」を一言で表す抽象説明。`takeover_start` で使用する。例: `"threat_containment"`。保護された名称・外部秘密・個人情報を含めない。
- `core_instability_level` (integer >= 0, optional): `unstable_city_core` motif (MP-004 / v0.7.2) が付与する都市中枢の抽象的な不安定度。0 = 安定基準値。値が大きいほど不安定化が進んでいることを示す。`stale_report` で使用する。保護された名称・外部秘密・個人情報を含めない。
- `stabilization_phase` (string, optional): `unstable_city_core` motif (MP-004 / v0.7.2) が付与する崩壊-回復循環のフェーズを人間可読に記録する。許容値: `precursor` / `collapse` / `intervention` / `recovery` / `stable`。`stale_report` で使用する。保護された名称・外部秘密・個人情報を含めない。

Rules:

- `takeover_start` は同じ `agent_id` に対して同一 tick で 1 件まで。
- `takeover_start` した takeover は、`ttl_ticks` 経過、`takeover_end`、または run 終了で必ず閉じる。
- 同一 seed・同一入力・RuleBasedProvider 経路では `matrix_events.jsonl` も byte 一致対象に含める。
- MATRIXモード off の場合、simulation は `matrix_events.jsonl` を出力しない。
- `matrix_role` と `trigger_id` に保護されたキャラクター名・引用を入れない。

### World Layer Model (`bridge_agent`)

`bridge_agent` は `real`、`virtual`、`liminal` の間を移動する抽象 role である。これは特定作品の人物コピーではなく、世界層をまたぐ能力を replay 可能な event として扱うための公開 alias である。

| layer | 意味 | entry events | exit layers | transition cost | evidence types |
| --- | --- | --- | --- | --- | --- |
| `real` | replay の観測状態。agent_states / visits / interactions が一次証拠になる層。 | `takeover_end`, `world_transition` | `virtual`, `liminal` | `virtual`: 1, `liminal`: 1 | `replay_state`, `matrix_event` |
| `virtual` | MATRIX event が agent に role / transition を重ねる層。 | `takeover_start`, `world_transition` | `real`, `liminal` | `real`: 1, `liminal`: 1 | `matrix_event`, `derived_metric` |
| `liminal` | real と virtual の間で human gate や不確実性を保持する層。 | `world_transition` | `real`, `virtual` | `real`: 2, `virtual`: 2 | `matrix_event`, `human_gate` |

Rules:

- `world_transition` は `matrix_role="bridge_agent"` を推奨する。
- `world_transition` は `source_layer` と `target_layer` を必ず持つ。両者は異なる値にする。
- `transition_cost` は `WORLD_LAYER_MODEL[source_layer].transition_cost[target_layer]` に一致させる。
- `evidence_type` は `WORLD_LAYER_MODEL[target_layer].evidence_types` のいずれかを使う。
- `liminal` から出る transition は cost 2 とし、human gate または明示的な matrix event を evidence として残す。
- world layer model は runtime side effect を持たない。既存 run、secret、外部 API、Cloud Run、GitHub push には影響しない。
- `exchanged=true` の `world_transition` は `exchange_cost_payload` を必ず持つ。`exchange_cost_payload` は消費した抽象コストを人間可読に表現し、保護された名称・外部秘密・個人情報を含めない。

### Oath Chain (`oath_chain`)

`oath_chain` は命令権限の階層構造と役割誓約を表す公開 alias である (MP-003 / v0.7.1)。`takeover_start` イベントにオプションフィールドとして付与する。

Rules:

- `hierarchy_rank` は 0 始まりの非負整数。0 が apex (最上位権限)。同一 rank が複数いる場合は協調関係を持つ。
- `sworn_duty` は人間可読な宣言文。保護されたキャラクター名・固有術語・外部秘密・個人情報を含めない。
- 両フィールドは optional。matrix_mode=False の既存 run には影響しない。
- `oath_chain` は runtime side effect を持たない。既存 run、secret、外部 API、Cloud Run、GitHub push には影響しない。
- `matrix_role`、`trigger_id`、`sworn_duty` には保護されたキャラクター名・引用を入れず、公開 alias と内部識別子だけを使う。

### Unstable City Core (`unstable_city_core`)

`unstable_city_core` は都市の中核 system が周期的に不安定化する構造を表す公開 alias である (MP-004 / v0.7.2)。`stale_report` イベントにオプションフィールドとして付与する。

Rules:

- `core_instability_level` は 0 始まりの非負整数。0 が安定基準値 (安定度最高)。値が大きいほど不安定化が進んでいることを示す。
- `stabilization_phase` は `precursor` / `collapse` / `intervention` / `recovery` / `stable` のいずれかを使う。未知値は reader が warning として人間可読に列挙する (即エラーにはしない)。
- 両フィールドは optional。matrix_mode=False の既存 run には影響しない。
- `unstable_city_core` は runtime side effect を持たない。既存 run、secret、外部 API、Cloud Run、GitHub push には影響しない。
- `matrix_role`、`trigger_id`、`stabilization_phase` には保護されたキャラクター名・引用を入れず、公開 alias と内部識別子だけを使う。

### Guide Agent Fallback (`guide_agent`)

`guide_agent` は現在 layer のルールと移動候補を説明する。MVP では LLM を必須にせず、`WORLD_LAYER_MODEL` だけから決定論的に `heartbeat` event を生成する。

Rules:

- `guide_agent` は `type="heartbeat"`、`matrix_role="guide_agent"` を使う。
- `guide_summary` は現在 layer と候補数を短く説明する。
- `candidate_transitions` は `WORLD_LAYER_MODEL[current_layer].exit_layers` から決定論的に生成する。
- `candidate_transitions[*].transition_cost` は `WORLD_LAYER_MODEL[source_layer].transition_cost[target_layer]` と一致する。
- `guide_agent` は提案だけを行い、secret、外部 API、Cloud Run、GitHub push、public PR 作成などの高リスク action を実行しない。
- LLM を将来使う場合も、RuleBasedProvider 経路では同一 seed・同一入力で byte 一致する fallback を維持する。

### Operator Human Gate (`operator_agent`)

`operator_agent` は高信頼 operator role だが、MVP では高リスク action を直接実行しない。実行が必要そうな場面を `human_gate` event として記録し、人間が明示承認するまで停止する。

Rules:

- `operator_agent` は `type="human_gate"`、`matrix_role="operator_agent"` を使う。
- `gate_status="requires_human"` は「実行していない」ことを意味する。
- `gate_action` は `public_pr`, `git_push`, `cloud_run_deploy`, `external_api`, `secret_access`, `cost_spend` のいずれかに限定する。
- `human_gate` event は secret、API key、認証 token、個人情報を保存しない。
- `approved` / `rejected` は将来の監査ログ用に予約する。MVP runtime は承認操作そのものを実行しない。
- `human_gate` は `world_layer="liminal"` を使い、real action と virtual plan の間で止める。

### Sentinel Swarm Heartbeat (`sentinel_swarm`)

`sentinel_swarm` は複数 monitor の協調を表す公開 alias である。MVP では実際の分散処理や外部監視を起動せず、heartbeat と stale self-report を replay 可能な MATRIX event として記録する。

Rules:

- `sentinel_swarm` は通常確認に `type="heartbeat"`、期限切れ自己申告に `type="stale_report"` を使う。
- heartbeat event は `swarm_status="alive"`、`heartbeat_interval_ticks`、`stale_after_ticks`、`orphan_tolerance` を持つ。
- stale_report event は `swarm_status="stale"`、`last_heartbeat_tick`、`missed_heartbeats`、`stale_after_ticks`、`orphan_tolerance` を持つ。
- stale threshold は heartbeat が `3` simulation tick 連続で欠落した状態とする。
- orphan tolerance の MVP 初期値は `0`。孤児 sentinel を許容しない前提で検証し、将来の分散実装で明示的に増やす。
- `sentinel_swarm` は secret、外部 API、GitHub push、Cloud Run deploy、production DB 操作を実行しない。
- `matrix_role`、`trigger_id`、`reason` には保護されたキャラクター名・引用を入れず、公開 alias と内部識別子だけを使う。

## Summary JSON

```json
{
  "run_id": "urban_demo",
  "seed": 42,
  "ticks": 24,
  "agents": 100,
  "pois": 300,
  "aois": 10,
  "roads": 500,
  "interactions": 12,
  "started_at": "2026-05-29T00:00:00Z"
}
```

Required: `run_id`, `seed`, `ticks`, `agents`, `pois`, `interactions`。Optional: `aois`, `roads`, `started_at`。

## Metrics JSON

`metrics.json` は replay 出力から再計算できる評価指標を持つ。arXiv 2412.03563 の Individual / Scenario / Society Simulation 分類を、現行 MVP の決定論ログに写像するための軽量ファイルである。LLM 行動決定や外部 API 呼び出しは含めない。

```json
{
  "schema_version": "social-simulation-metrics-v0.1",
  "run_id": "urban_demo",
  "seed": 42,
  "ticks": 24,
  "individual_simulation": {
    "agents_with_state_history": 100,
    "action_diversity": 7,
    "action_count_by_type": {"commute": 320},
    "profile_coverage": {
      "agents": 100,
      "with_role": 100,
      "with_social_networks": 100,
      "with_rich_profile": 100
    }
  },
  "scenario_simulation": {
    "interaction_count_by_type": {"conversation": 8},
    "relationship_delta_count": 8,
    "relationship_reason_count": 8,
    "co_presence_distribution": {"2": 4},
    "repeated_interaction_pairs": 1
  },
  "society_simulation": {
    "arrival_status_rate": 0.08,
    "arrival_rate": 0.22,
    "no_target_rate": 0.0,
    "trip_count_by_action": {"commute": 24, "lunch": 8},
    "route_mode_count": {"linear_fallback": 120, "roadnet": 360},
    "route_fallback_rate": 0.25,
    "poi_visit_entropy": 0.82,
    "unique_poi_visit_rate": 0.34,
    "social_network_density": 0.03
  }
}
```

Required: `schema_version`, `run_id`, `seed`, `ticks`, `individual_simulation`, `scenario_simulation`, `society_simulation`。

**決定論との関係**: 再現性検証 (spec §13.3.2) は `agent_states.jsonl` / `poi_visit_records.jsonl` / `interaction_events.jsonl` / `metrics.json` の byte 一致を対象とする。`summary.json` は `started_at` 等の実行時刻を含むため byte 一致対象から除外する。`relationship_reason` は RuleBasedProvider 経路では決定論的なテンプレ文が返るため byte 一致に寄与する。VertexGeminiProvider 経路では Gemini が生成する自然言語テキストとなり非決定論になる。

## Change Log

- 0.1.0: Initial MVP contract for data loader, viewer, simulation, and replay.
- 0.2.0: spec 改訂 (Google Cloud Run + Google Maps + Vertex AI/Gemini, Groq/STT 全除去) に追従。§Coordinate Systems / §Naming Conventions / §Time and Tick / §Enumerations / §Relationship Snapshot を新設。POI/AOI/Road を GeoJSON Feature 構造へ統一し `geometry_type` プロパティを廃止。例の `poi_id` を `cafe_123`→`poi_123`、`category` を `"amenity - cafe"`→`amenity-cafe` に修正。`summary.json` に `seed` を追加し決定論対象外を明記。`relationships.jsonl` を File Names に追加。Purpose から動画要件抽出への言及を削除。
- 0.3.0 (WO-006): §Agent Profile に optional 拡張フィールドを追加。`surname` / `given` (姓名分割 / `name == surname + given` 保証) / `occupation` (職業詳細) / `personality` (性格傾向) / `hobbies` (趣味リスト) / `day_pattern` (行動傾向 / `"morning"` | `"night"` | `"balanced"`)。後方互換: 全フィールドは optional で既存 simulation / viewer / replay は影響なし。`generate_urban_sample.py` は WO-006 から新フィールドを生成する (rng 消費 Step 10-13)。これは WO-007 (苗字キャラ表示) / WO-008 (LLM 行動決定) の共通土台。
- 0.4.0 (WO-012): §Interaction Event JSONL に `relationship_reason` を optional フィールドとして正式追加。WO-008 で simulation が emit 済み (`from != to` のときのみ出力、空文字は出力しない)。後方互換: optional かつ §Common Rules の「未知フィールド保持原則」により既存 reader への影響なし。RuleBasedProvider 経路では決定論テンプレ文 (byte 一致維持)、VertexGeminiProvider 経路では Gemini 生成の自然言語テキスト (非決定論) となる。
- 0.4.1 (WO-URBAN-017): `metrics.json` を required output として追加。Individual / Scenario / Society Simulation の三層評価を replay-derived metrics として出力し、`summary.json` と違って実行時刻を含めないため RuleBasedProvider 経路の byte 一致対象に含める。
- 0.4.2 (WO-URBAN-017 follow-up): AgentState optional `route_mode` を追加。`metrics.json` の Society Simulation に `arrival_rate` / `trip_count_by_action` / `route_mode_count` / `route_fallback_rate` を追加し、地域データ差し替え時の到着・移動・fallback 品質を replay-derived に比較できるようにした。
- 0.5.0 (WO-URBAN-015): `activity_plans.jsonl` を optional input として追加。plan が無い場合は既存 rule-driven simulation の byte 再現性を維持し、plan がある場合だけ active activity を destination selection に優先適用する。
- 0.6.0 (MATRIX M1-001): `matrix_events.jsonl` を optional output/input として追加。`takeover_start` / `takeover_end` / `world_transition` / `heartbeat` / `stale_report`、public alias (`sentinel_mvp` 等)、Three Worlds (`real` / `virtual` / `liminal`) を contract 化した。MATRIXモードは既定 off、保護された名前・引用は保存しない、RuleBasedProvider 経路では byte 一致対象とする。
- 0.6.1 (MATRIX M2-001): `bridge_agent` の World Layer Model を追加。`real` / `virtual` / `liminal` の entry events、exit layers、transition cost、evidence types を contract 化した。`transition_cost` / `evidence_type` / `evidence_ref` を `MatrixEvent` optional fields として追加した。
- 0.6.2 (MATRIX M3-001): `guide_agent` の RuleBased fallback を追加。`guide_summary` / `candidate_transitions` を `MatrixEvent` optional fields とし、`heartbeat` event で現在 layer の説明と transition 候補を出せるようにした。
- 0.6.3 (MATRIX M4-001): `operator_agent` の human gate を追加。`human_gate` event、`gate_action` / `gate_status` / `gate_reason` を contract 化し、MVP runtime では高リスク action を実行せず `requires_human` として記録する。
- 0.6.4 (MATRIX M5-001): `sentinel_swarm` の heartbeat / stale self-report を追加。`swarm_status`、`heartbeat_interval_ticks`、`stale_after_ticks`、`orphan_tolerance`、`last_heartbeat_tick`、`missed_heartbeats` を contract 化し、stale は 3 simulation tick 欠落、orphan tolerance は初期 `0` とした。
- 0.7.0 (MATRIX M9-002): `exchange_pair` motif packet (MP-002) の optional field を追加。`exchange_cost_payload` (string or dict) と `exchanged` (bool) を `MatrixEvent` の optional field として追加した。`world_transition` Rules に「`exchanged=true` の場合は `exchange_cost_payload` が必須」制約を明示した。後方互換: 両フィールドは optional で既存 run への影響なし。
- 0.7.1 (MATRIX M9-003): `oath_chain` motif packet (MP-003) の optional field を追加。`hierarchy_rank` (integer >= 0) と `sworn_duty` (string) を `MatrixEvent` の optional field として追加した。`takeover_start` に付与し、命令権限の階層と役割誓約を replay 可能な形で記録する。Oath Chain Rules 節を新設した。後方互換: 両フィールドは optional で既存 run への影響なし。
- 0.7.2 (MATRIX M9-004): `unstable_city_core` motif packet (MP-004) の optional field を追加。`core_instability_level` (integer >= 0) と `stabilization_phase` (string) を `MatrixEvent` の optional field として追加した。`stale_report` に付与し、都市中枢の不安定度と崩壊-回復フェーズを replay 可能な形で記録する。Unstable City Core Rules 節を新設した。後方互換: 両フィールドは optional で既存 run への影響なし。
