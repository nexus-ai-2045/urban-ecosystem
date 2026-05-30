# Urban Ecosystem Data Contract

status: accepted
version: 0.3.0
owner: manager
updated: 2026-05-30

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
| `agent_states.jsonl` | output/input | yes | Tick 単位の agent 状態。リプレイ一次ソース (tick を持つ唯一のファイル)。 |
| `poi_visit_records.jsonl` | output/input | no | 訪問履歴 (詳細パネル補助表示)。 |
| `interaction_events.jsonl` | output | yes | 会話・出会い・別れ・喧嘩などの社会イベント。 |
| `relationships.jsonl` | output | no | 関係性スナップショット (任意 / §Relationship Snapshot)。 |
| `summary.json` | output | yes | run の件数と集計指標。 |

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
| VisitRecord.`action` | `visit` | MVP は `visit` のみ。 |
| InteractionEvent.`type` | `meeting`, `conversation`, `conflict`, `farewell` | 出会い / 会話 / 喧嘩 / 別れ (spec §9.8)。 |
| relationship `state` | `rival`, `stranger`, `acquaintance`, `friend`, `close_friend` | score しきい値で算出 (spec §9.9)。 |
| Agent `role` | `office_worker`, `student`, `other` (既定) | profile に role が無い場合は `other` 扱い。将来 role 追加可。 |

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
  "relationship_delta": { "from": "acquaintance", "to": "friend" }
}
```

Required: `tick`, `day`, `time`, `type` (§Enumerations), `agent_ids` (既存 agent / 要素数 >= 2 / 重複なし / `[min_id, max_id]` 昇順正規化), `summary` (string)。
Optional: `location_poi_id` (既存 POI id), `relationship_delta` (`{from, to}` / 各値は relationship state / state 不変でも `from == to` で出力可)。

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

**決定論との関係**: 再現性検証 (spec §13.3.2) は `agent_states.jsonl` / `poi_visit_records.jsonl` / `interaction_events.jsonl` の 3 ファイルの byte 一致を対象とする。`summary.json` は `started_at` 等の実行時刻を含むため byte 一致対象から除外する。

## Change Log

- 0.1.0: Initial MVP contract for data loader, viewer, simulation, and replay.
- 0.2.0: spec 改訂 (Google Cloud Run + Google Maps + Vertex AI/Gemini, Groq/STT 全除去) に追従。§Coordinate Systems / §Naming Conventions / §Time and Tick / §Enumerations / §Relationship Snapshot を新設。POI/AOI/Road を GeoJSON Feature 構造へ統一し `geometry_type` プロパティを廃止。例の `poi_id` を `cafe_123`→`poi_123`、`category` を `"amenity - cafe"`→`amenity-cafe` に修正。`summary.json` に `seed` を追加し決定論対象外を明記。`relationships.jsonl` を File Names に追加。Purpose から動画要件抽出への言及を削除。
- 0.3.0 (WO-006): §Agent Profile に optional 拡張フィールドを追加。`surname` / `given` (姓名分割 / `name == surname + given` 保証) / `occupation` (職業詳細) / `personality` (性格傾向) / `hobbies` (趣味リスト) / `day_pattern` (行動傾向 / `"morning"` | `"night"` | `"balanced"`)。後方互換: 全フィールドは optional で既存 simulation / viewer / replay は影響なし。`generate_urban_sample.py` は WO-006 から新フィールドを生成する (rng 消費 Step 10-13)。これは WO-007 (苗字キャラ表示) / WO-008 (LLM 行動決定) の共通土台。
