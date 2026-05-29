# AIエージェント人工生態系アプリ 仕様書

## 1. アプリ概要

このアプリは、都市地図上に多数のAIエージェントを配置し、各エージェントが時刻、プロフィール、周辺施設、道路網、記憶、社会関係に基づいて生活・移動・交流する様子をシミュレーション、記録、リプレイするためのツールです。

デモ動画では、渋谷周辺の地図にPOI、エリア、道路、人々を重ね、100人のエージェントが朝8時から5分ごとに行動を決め、会社、学校、飲み会、出会い、別れ、喧嘩のような社会的イベントを起こす様子が紹介されています。

本仕様書は、実装しやすいようにアプリ画面、データ構造、処理フロー、モジュール境界、MVP範囲を定義します。実行基盤は Google Cloud Run、地図は Google Maps JavaScript API、後段の LLM は Vertex AI / Gemini を前提とします。

## 2. 参照資料

- X投稿: `https://x.com/ka2aki86/status/2059112297797451949`
- 投稿日: 2026-05-26
- 動画長: 約126秒

上記は本アプリの着想元となったデモ紹介投稿です。本アプリは投稿で示された「都市上のAIエージェント生態系」というコンセプトを参照しますが、投稿動画そのものを取り込む機能は持ちません。

## 3. MVPスコープ

### 第一成果物 (最優先)

**「100体のエージェントが Day 0 を過ごす1日リプレイ」が Google Cloud Run 上で動く** ことを MVP の第一成果物とする。
合成データ生成 → ルールベース簡易シミュレーション → Cloud Run 配信のブラウザUIでリプレイ、までを一気通貫で動かす。

### MVPで作るもの

- GeoJSON/JSON/JSONLを読み込む都市データローダー。
- 100人規模のエージェントプロフィール読み込み。
- 合成 GeoJSON (POI/AOI/Road) とプロフィール・状態ログの生成スクリプト (seed 固定・再現可能)。
- Google Maps上でPOI、AOI、道路、エージェントを表示するブラウザUI。
- エージェントクリック時のプロフィール表示。
- Day/Timeと5分刻みのリプレイ。
- 訪問履歴 `poi_visit_records.jsonl` および `agent_states.jsonl` からの再生。
- ルールベースの最小シミュレーション (道路移動は直線補間)。
- Google Cloud Run 上での配信 (コンテナ化 + デプロイ)。
- Google Maps APIキー無しでも動くフォールバック地図 (CI/テスト主経路)。

### MVPで作らないもの

- 1万人以上のリアルタイムLLM推論。
- LLMによる行動決定 (MVPはルールベース固定。Vertex AI / Gemini 連携は後続マイルストーン)。
- 写実的な3D都市表示。
- 実在人物の再現。
- 現実世界の行動予測機能。
- 完全なSNS/メッセージアプリ連携。
- 動画/音声の取り込み・音声認識(STT)・動画からの仕様自動生成 (本アプリのスコープ外。将来機能としても扱わない)。

## 4. ユーザー体験

### 4.1 初期表示

ユーザーがアプリを開くと、地図ビューが表示されます。左側にデータ読込パネル、中央に地図、右側に凡例と選択中エージェントの詳細、下部に時刻コントロールを配置します。

```text
+----------------------+------------------------------+----------------------+
| データ読込 / レイヤー | 地図                          | 凡例 / 詳細           |
| - POI                | - 地図タイル                  | - POIカテゴリ         |
| - AOI                | - POI点                       | - Agents             |
| - Roadnet            | - AOI面                       | - 選択エージェント    |
| - Visit records      | - 道路線                      |                      |
| - Profiles           | - エージェントマーカー        |                      |
+----------------------+------------------------------+----------------------+
| Day: 0 Time: 08:00:00 | 再生 / 停止 / 速度 / 時刻スライダー                  |
+---------------------------------------------------------------------------+
```

### 4.2 主な操作

- Cloud Run 本番では同梱サンプル run を `/api/runs` から選択して読み込む。ローカル開発ではファイル選択でも読み込める。
- 読み込む主要データは `pois.geojson`、`aois.geojson`、`roadnet.geojson`、`agent_profiles_N100.json`、`poi_visit_records.jsonl`、`agent_states.jsonl`。
- ユーザーはPOI、AOI、道路、訪問履歴、エージェントの表示をON/OFFできる。
- ユーザーは再生ボタンでリプレイできる。
- ユーザーは時刻スライダーで任意のtickへ移動できる。
- ユーザーはエージェントをクリックしてプロフィール、現在地、行動、関係性を見る。

## 5. 画面仕様

### 5.1 地図ビュー

| 項目 | 仕様 |
| --- | --- |
| 地図背景 | Google Maps JavaScript APIを第一候補にする。開発・テスト用にAPIキーなしで動く簡易キャンバス/SVG背景フォールバックを持つ。 |
| POI表示 | カテゴリ別の点として表示。カテゴリごとに色分けする。 |
| AOI表示 | 半透明ポリゴンとして表示。 |
| 道路表示 | LineStringを線として表示。 |
| エージェント表示 | 番号付きマーカー。密集時はクラスタ表示を検討。 |
| 選択状態 | 選択中エージェントを強調表示する。 |

### 5.1.1 Google Maps利用方針

- MVPの本命地図エンジンは Google Maps JavaScript API とする。
- APIキーは Cloud Run 本番では Secret Manager 経由でサーバーに注入し、サーバーが生成するHTMLに埋め込む (フロントへは referrer 制限済みキーのみ露出)。
- ローカル開発では `.env` の `GOOGLE_MAPS_API_KEY` を使う。未設定時は fallback 地図に自動切替する。
- フロント露出キーは Google Cloud Console で HTTP referrer 制限 (本番カスタムドメイン + Cloud Run の `*.run.app`) と Maps JavaScript API のみへの API 制限をかける。
- `AdvancedMarkerElement` は Map ID 必須のため、`Map` 生成時に `mapId` を渡す。`GOOGLE_MAPS_MAP_ID` から読み、未設定時はフォールバック Map ID を使う (本番用 Map ID 自前発行は §16 未決)。
- Google Maps表示では、Googleの帰属表示や利用条件を壊さない。
- POIやagentなど独自データはGoogle Maps上のOverlay/Marker/Data layerとして重ねる。

### 5.1.2 採用するGoogle Maps関連部品

| 用途 | 採用候補 | ロード方式 | 使い方 |
| --- | --- | --- | --- |
| Maps JSロード | Google Maps JavaScript API bootstrap loader / `importLibrary()` | inline bootstrap loader | MVPではビルドなしで読み込む。将来npm化する場合は `@googlemaps/js-api-loader` を検討する。 |
| GeoJSON表示 | Google Maps Data layer | importLibrary("maps") | `pois.geojson`、`aois.geojson`、`roadnet.geojson` の読み込みとスタイル適用に使う。 |
| エージェント表示 | `AdvancedMarkerElement` | importLibrary("marker") | 番号付き、色付き、クリック可能な人物マーカーを作る。Map ID 必須。 |
| マーカー密集対策 | `@googlemaps/markerclusterer` | CDN (unpkg/jsdelivr) | 100体では任意、1,000体以上またはズームアウト時に使用する。 |
| 実装サンプル | `googlemaps/js-samples` | 参照のみ | 初期化、Data layer、marker clustering、Advanced Markerの実装参考にする。 |

MVPではフロントエンドのビルド工程を増やさず、素のHTML/CSS/JavaScript (ES module) で開始する。`@googlemaps/markerclusterer` は必要になった時点でCDNまたはnpm経由で導入する。

### 5.1.3 Maps JavaScript API ロードと描画フロー

1. ロード: HTML に Google 公式の inline bootstrap loader を1つだけ置く。
   app.js で `const { Map } = await google.maps.importLibrary("maps");`
   `const { AdvancedMarkerElement, PinElement } = await google.maps.importLibrary("marker");`
   の順に await 取得する。MVP ではバンドラを使わず ES module で読む。
2. Map 生成: `new Map(el, { center, zoom, mapId })`。
   - mapId は AdvancedMarkerElement の必須要件。`GOOGLE_MAPS_MAP_ID` 未設定時はフォールバック Map ID を使うが、本番は自前発行 (§16 未決)。
3. POI/AOI/Road: 各 GeoJSON を別々の `google.maps.Data` インスタンスに `data.addGeoJson(geojson)` で投入し、レイヤーごとに `setStyle()`。
   - POI: Point。category で色分け (style 関数で `properties.category` 参照)。
   - AOI: Polygon/MultiPolygon。fillOpacity 0.2 程度の半透明。
   - Road: LineString/MultiLineString。strokeWeight 1-2。
   - レイヤー ON/OFF は各 Data インスタンスに `setMap(map | null)`。
4. Agent: AdvancedMarkerElement で生成。PinElement で番号付きピン (`glyph = String(agent_id)`、role で色分け)。click で選択イベント発火。
5. 帰属表示: Google の attribution / ロゴ DOM を隠さない・重ねない。

### 5.1.4 位置更新とパフォーマンス方針

- agent marker は初回に1体1インスタンス生成し、tick 更新時は既存 marker の `.position` を再代入する (生成/破棄しない)。
- 再生ループは `setInterval` ではなく `requestAnimationFrame` ベースの時刻駆動にし、speed (1x/2x/5x) は「実時間あたり進める tick 数」で表現する。
- 100体規模では tick ごとの全 marker 位置更新で十分 (1 tick = 100 set)。
- tick 間の見た目の滑らかさは、隣接 tick 間の lat/lon を線形補間して描画フレーム単位で中間位置を入れる (道路移動も MVP は直線補間)。補間は表示専用で、状態の真値は tick 単位の `agent_states` を維持する。
- 1,000体スケール時 (Milestone 6):
  - markerclusterer を後付けし、ズームアウト時はクラスタ表示。
  - 画面外 (map bounds 外) の marker は更新スキップ (viewport culling)。
  - 補間を切る degrade モード (tick スナップ表示) を速度上限で自動適用。
- 性能受け入れ目安 [推測]: 100体 1x 再生で主要ブラウザ実測 30fps 以上を目標にし、下回る場合は補間オフに degrade する。

### 5.1.5 APIキー無し fallback 地図 (CI/テスト主経路)

- 目的: `GOOGLE_MAPS_API_KEY` 未設定 (CI / ローカル無課金) でも POI/AOI/Road/Agent を描画し、リプレイ操作をテストできるようにする。
- 描画先: `<canvas>` または `<svg>` 単一要素。タイル画像は使わない。
- 投影: 全データの lat/lon から bounds を計算し、線形変換で画面座標へ写す。
  - x = (lon - lonMin) / (lonMax - lonMin) * width
  - y = (latMax - lat) / (latMax - latMin) * height   (lat 上が小さい y)
  - MVP は等距離線形でよい (Web Mercator は採用しない / 渋谷規模で歪み許容)。
- レイヤー: POI=点, AOI=半透明多角形, Road=折れ線, Agent=番号付き円。ON/OFF は再描画時の描画スキップで実現。
- 操作: パン/ズームは MVP では任意 (固定 fit-to-bounds で可)。
- adapter 契約: `google_maps_adapter.js` と `fallback_map_adapter.js` は同一インターフェース (init / setLayer / upsertAgents / highlight / onAgentClick) を実装し、app.js はキー有無で adapter を差し替える。
- テスト方法:
  - jsdom + canvas モック、または Playwright headless で描画関数を呼び、投影座標が bounds 内に収まることと、agent 数 = 100 を assert。
  - tick を進めて特定 agent の画面座標が変化することを assert。

### 5.2 データ読込パネル

| 入力 | 必須 | 説明 |
| --- | --- | --- |
| `pois.geojson` | 必須 | 店舗、施設、ベンチなどのPOI。 |
| `aois.geojson` | 任意 | エリア、地区、ゾーンなどの面情報。 |
| `roadnet.geojson` | 任意 | 歩行経路や道路ネットワーク。 |
| `agent_profiles_N100.json` | 必須 | エージェントプロフィール。 |
| `poi_visit_records.jsonl` | 任意 | 訪問履歴。詳細パネルの補助表示に使う。 |
| `agent_states.jsonl` | 必須 | リプレイ一次ソース (tick を持つ唯一のファイル)。 |

読込後は、各ファイルの件数、検証結果、エラー件数を表示します。

### 5.3 凡例・詳細パネル

凡例にはPOIカテゴリ別件数、総POI数、総AOI数、エージェント数を表示します。

エージェント詳細には以下を表示します。

- ID
- 名前
- 年齢
- 性別
- プロフィール説明文
- 現在時刻
- 現在位置
- 現在または直近のPOI
- 現在の行動
- social network IDs
- 直近の会話またはイベント

### 5.4 時刻コントロール

| 操作 | 仕様 |
| --- | --- |
| 再生/停止 | リプレイ (`agent_states.jsonl`) を再生する。 |
| ステップ送り | 1 tick進める。MVPでは5分刻み。 |
| 速度変更 | 1x、2x、5x程度を選べる。 |
| 時刻スライダー | 全tickの範囲で移動できる。 |
| 表示 | `Day: 0 Time: 08:00:00` 形式。 |

### 5.5 フロント状態管理 (リプレイ)

app.js が単一の ViewerState を保持し、adapter は描画専用 (状態を持たない)。

ViewerState:

- data: { pois, aois, roads, profiles }  (ロード済み正規化データ)
- replay: {
    ticks: number[],          // 昇順 tick 一覧 (agent_states.jsonl 由来)
    tickIndex: number,        // 現在 tick の配列インデックス
    playing: boolean,
    speed: 1 | 2 | 5,
    statesByTick: Map<tick, AgentState[]>  // tick -> 全 agent 状態
  }
- selection: { agentId: number | null }

イベント -> 状態遷移:

- play/pause      -> replay.playing 切替
- step            -> tickIndex += 1 (上限で停止)
- slider seek     -> tickIndex = target
- speed change    -> replay.speed 更新
- agent click     -> selection.agentId 更新 -> 詳細パネル再描画 + highlight
- layer toggle    -> adapter.setLayer(name, on/off) (状態は UI 側 boolean)

描画は状態変更時に「現 tick の AgentState[] を adapter.upsertAgents に渡す」一方向データフロー。詳細パネルは selection.agentId と現 tick state から導出。

リプレイ一次ソースは `agent_states.jsonl` (tick を持つ唯一のファイル)。`poi_visit_records.jsonl` は詳細パネルの「直近 POI / 理由」補助表示に使う。

## 6. データモデル

> 本節はデータモデルの概観を示す。各フィールドの必須/任意・型・制約の**正本は `docs/subagents/contracts/urban-ecosystem-data-contract.md`** とする。spec との差異が生じた場合は data-contract を優先する (spec は data-contract `version >= 0.2` を参照する)。

> 座標は2系統ある。(1) GeoJSON (POI/AOI/Road) は geometry.coordinates `[lon, lat]` (RFC 7946)。(2) flat JSON (AgentProfile.initial_position / AgentState / VisitRecord) は `lat` と `lon` の個別キー。両者を混在させない。正本は data-contract §Field Types and Constraints。

### 6.1 POI

GeoJSON Feature (Point) で表現します。`lat`/`lon` は geometry.coordinates に一元化します。

```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [139.0, 35.0] },
  "properties": { "id": "poi_001", "category": "amenity-cafe", "name": "Cafe Example", "source": "synthetic" }
}
```

必須: `id`, `category`／任意: `name`, `source`。`coordinates` は `[lon, lat]` 順 (RFC 7946)。

### 6.2 AOI

GeoJSON Feature (Polygon/MultiPolygon) で表現します。geometry.type と二重になる `geometry_type` プロパティは持ちません。

```json
{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [[[139.0, 35.0], [139.1, 35.0], [139.1, 35.1], [139.0, 35.0]]] },
  "properties": { "id": "aoi_001", "name": "Shibuya Area", "category": "district" }
}
```

必須: `id`／任意: `name`, `category`。

### 6.3 Road Segment

GeoJSON Feature (LineString/MultiLineString) で表現します。

```json
{
  "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [[139.0, 35.0], [139.001, 35.001]] },
  "properties": { "id": "road_001", "length_m": 128.4, "walkable": true }
}
```

必須: `id`／任意: `length_m` (>=0), `walkable` (default true)。

### 6.4 Agent Profile

```json
{
  "id": 26,
  "name": "Mori Akira",
  "age": 35,
  "gender": "male",
  "description": "A local guide who leads tours and runs.",
  "initial_position": {
    "lat": 35.0,
    "lon": 139.0
  },
  "home_poi_id": "poi_home_001",
  "work_or_school_poi_id": "poi_work_001",
  "role": "office_worker",
  "social_networks": [61, 97, 99]
}
```

必須: `id` (integer), `name`, `initial_position`／任意: `age`, `gender`, `description`, `home_poi_id`, `work_or_school_poi_id`, `role`, `social_networks`。`social_networks` は既存 agent id 配列で、自己 id を含めない・重複なし。

### 6.5 Agent State

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

必須: `tick`, `day`, `time`, `agent_id`, `lat`, `lon`, `action`, `status`／任意: `current_poi_id`, `target_poi_id`。

### 6.6 Visit Record

```json
{
  "agent_id": 26,
  "day": 0,
  "time": "08:05:00",
  "poi_id": "poi_123",
  "action": "visit",
  "reason": "breakfast",
  "lat": 35.0,
  "lon": 139.0
}
```

必須: `agent_id`, `day`, `time`, `action`, `lat`, `lon`／任意: `poi_id` (既存 POI id または予約値 `initial_position`), `reason`。

### 6.7 Interaction Event

```json
{
  "tick": 42,
  "day": 0,
  "time": "11:30:00",
  "type": "conversation",
  "agent_ids": [26, 92],
  "location_poi_id": "poi_123",
  "summary": "Two agents talked about lunch plans.",
  "relationship_delta": {
    "from": "acquaintance",
    "to": "friend"
  }
}
```

必須: `tick`, `day`, `time`, `type`, `agent_ids` (len>=2 / 既存 agent id / 重複なし), `summary`／任意: `location_poi_id`, `relationship_delta`。`type` の語彙は §9.8。

## 7. ファイル仕様

| ファイル | 形式 | 方向 | 用途 |
| --- | --- | --- | --- |
| `pois.geojson` | GeoJSON | 入力 | POI表示と目的地候補。 |
| `aois.geojson` | GeoJSON | 入力 | エリア表示。 |
| `roadnet.geojson` | GeoJSON | 入力 | 道路表示 (MVPは表示専用)。 |
| `agent_profiles_N100.json` | JSON | 入力 | エージェント初期化。 |
| `poi_visit_records.jsonl` | JSONL | 入力/出力 | 訪問履歴 (詳細パネル補助)。 |
| `agent_states.jsonl` | JSONL | 出力/入力 | tickごとの状態。リプレイ一次ソース。 |
| `interaction_events.jsonl` | JSONL | 出力 | 会話、出会い、別れ、喧嘩など。 |
| `relationships.jsonl` | JSONL | 出力 (任意) | 関係性スナップショット (§9.9)。 |
| `summary.json` | JSON | 出力 | 件数と集計指標。 |

## 8. アプリ処理フロー

### 8.1 リプレイモード

```text
入力 run 選択 (Cloud Run: /api/runs / ローカル: ファイル選択)
  -> データ検証
  -> POI/AOI/道路/プロフィールをメモリにロード
  -> agent_states.jsonl を tick 順にインデックス化 (statesByTick)
  -> 地図UI初期化
  -> 再生操作
  -> tickごとにエージェント位置と詳細パネルを更新
```

### 8.2 シミュレーションモード

```text
プロフィールと地理データをロード
  -> 初期位置にエージェントを配置
  -> tick開始
  -> 周辺POIと近接エージェントを検索
  -> 行動決定 (ルールベース)
  -> 移動先/会話/訪問を反映
  -> 状態ログとイベントログを書き出し
  -> 次tickへ
```

MVPでは行動決定をルールベースで実装し、LLM (Vertex AI / Gemini) は後続マイルストーンで差し替えます。

## 9. 行動ルール MVP

MVP の最小シミュレーションは LLM なしで決定論的に動作させる。乱数は run seed から導出し、再現可能にする。

### 9.1 時間モデル

- 1 tick = 5 分 (`TICK_MINUTES = 5`)。
- 1 日 = 08:00:00 開始、24:00 まで → 1 日あたり最大 192 tick。MVP の受け入れは 24 tick 以上 (= 2 時間分) で可。
- `time` は開始時刻 + `tick * TICK_MINUTES` で導出する。tick↔time の正本は data-contract §Time and Tick。

### 9.2 行動状態機械 (status)

各エージェントは毎 tick 次の status のいずれかを持つ。

| status | 意味 | 遷移条件 |
| --- | --- | --- |
| `idle` | 目的地未設定で滞在中 | スケジュールが次の目的地を出すと `moving` へ |
| `moving` | 目的地へ直線移動中 | 目的地に到達すると `at_poi` へ |
| `at_poi` | POI 滞在中 | 滞在時間を消化 or スケジュール変化で `idle`/`moving` へ |

contract の status 語彙 (`moving`/`arrived`/`staying`) との対応 (正本: data-contract §Enumerations):

| 内部状態 | 条件 | 出力 status |
| --- | --- | --- |
| `moving` | 目的地へ移動中 | `moving` |
| `at_poi` | 目的地に到達したその tick | `arrived` |
| `at_poi` | 到達後の滞在 tick | `staying` |
| `idle` | 目的地未設定で現在地に滞在 | `staying` |

到達 tick (`arrived`) は「直前 tick が `moving` で当 tick に目的地スナップした」場合のみ。それ以外の滞在は `staying`。`idle` は出力に専用語彙を持たず `staying` に集約する。

### 9.3 時刻帯 × role 行動テーブル (目的地カテゴリ決定)

毎 tick、status が `idle` または滞在時間を消化済みのエージェントについて、現在時刻と role から「次の目的地カテゴリ」を決める。

| 時刻帯 (開始-終了) | role | 目的地カテゴリ | 目的地選択 | reason |
| --- | --- | --- | --- | --- |
| 08:00-10:00 | office_worker | `work_or_school_poi_id`(固定) | プロフィール固定 | `commute` |
| 08:00-10:00 | student | `work_or_school_poi_id`(固定) | プロフィール固定 | `commute` |
| 10:00-12:00 | office_worker / student | 現POI滞在 | 移動なし | `work` / `study` |
| 12:00-13:00 | 全員 | `restaurant`,`cafe`,`fast_food` | 最近傍 | `lunch` |
| 13:00-18:00 | office_worker / student | `work_or_school_poi_id`(固定) | プロフィール固定 | `work` / `study` |
| 13:00-18:00 | その他 role | `shop`,`park`,`cafe` | 最近傍からカテゴリ重み付き抽選 | `errand` |
| 18:00-22:00 | 全員 | `bar`,`restaurant`,`cafe` | social bias 込み最近傍(§9.10) | `social` |
| 22:00-08:00 | 全員 | `home_poi_id`(固定) | プロフィール固定 | `go_home` |
| 上記いずれにも該当しない | 全員 | 近傍 POI ランダム or 現POI滞在 | 確率 0.3 で近傍へ、0.7 で滞在 | `wander` |

- role 既定値: profile に `role` が無いエージェントは `other` 扱い (= 「その他 role」行)。
- `work_or_school_poi_id` / `home_poi_id` が profile に無い場合は `initial_position` 最近傍 POI で代替する。

### 9.4 目的地選択アルゴリズム

1. 対象カテゴリ集合 `C` を §9.3 から決める。
2. POI 一覧から `category` が `C` に部分一致するものを候補化する (`category` は `"<group>-<sub>"` 形式のため部分一致でマッチ)。
3. 現在地から候補 POI への **Haversine 距離** を計算する。
4. **最近傍**を選ぶ。ただし「カテゴリ重み付き抽選」指定の行では、上位 `K=5` 近傍から距離の逆数を重みにした seeded 抽選を行う (同一 POI への集中を緩和)。
5. 候補が空なら status を `idle` のまま据え置き、reason=`no_target`。

距離は道路グラフを使わず直線(Haversine)で十分 (MVP は直線補間移動のため)。

### 9.5 直線補間移動

- エージェント速度: 既定 `WALK_SPEED_MPS = 1.3` m/s (徒歩)。
- 1 tick の移動可能距離: `STEP_M = WALK_SPEED_MPS * TICK_MINUTES * 60 = 1.3 * 300 = 390 m / tick`。
- 現在地 → 目的地の直線(大圏)上を、毎 tick `STEP_M` ずつ前進する。
- 残距離が `STEP_M` 以下なら目的地へスナップし status を `at_poi` (出力では `arrived`) にする。
- 補間は緯度経度の線形補間で近似してよい (都市スケールでは誤差無視可)。`fraction = min(1, STEP_M / remaining_m)`。
- 到達 tick に `poi_visit_records.jsonl` へ visit record を 1 行出力する (`action="visit"`, `reason` は §9.3 の reason)。

### 9.6 滞在時間

| reason | 既定滞在 (tick) | 補足 |
| --- | --- | --- |
| `commute`→work/study | 18:00 まで | 退勤時刻まで固定 POI 滞在 |
| `lunch` | 2-4 tick (10-20分) | seeded 一様抽選 |
| `social` | 4-12 tick (20-60分) | seeded 一様抽選 |
| `errand` / `wander` | 1-3 tick | seeded 一様抽選 |
| `go_home` | 翌 08:00 まで | 夜間は自宅滞在 |

滞在中は status=`at_poi` (出力 `staying`)、移動しない。滞在 tick を消化したら §9.3 を再評価する。

### 9.7 近接判定と社会的交流のフック

毎 tick、status が `at_poi` のエージェント同士で近接ペアを検出する。

- 近接しきい値: `PROXIMITY_M = 30` m (= 同一 POI/隣接ベンチ程度)。
- 効率化: 同一 `current_poi_id` のエージェントを bucket 化し、bucket 内ペアのみ Haversine 判定する (全ペア O(N^2) を回避)。
- 近接ペアが成立したら §9.8 の interaction 発生判定にかける。

定数まとめ (実装は `rules.py` 冒頭に定義):

```python
TICK_MINUTES = 5
WALK_SPEED_MPS = 1.3
STEP_M = 390.0
PROXIMITY_M = 30.0
NEIGHBOR_K = 5
```

### 9.8 interaction_events 発生ルール

近接ペア `(a, b)` ごとに、その tick で 1 度だけ interaction 発生判定を行う (ペアは順序なし、`min(id),max(id)` で正規化)。

#### 9.8.1 発生確率

base 確率に social bias を加算する。

```
p_interact = clamp(BASE_P + SOCIAL_BONUS * is_in_network(a, b) + TIME_BONUS(time), 0, P_MAX)
```

| 係数 | 値 | 意味 |
| --- | --- | --- |
| `BASE_P` | 0.15 | 任意の近接ペアが交流する基礎確率/ tick |
| `SOCIAL_BONUS` | 0.55 | 互いの `social_networks` に入っている場合の加算 |
| `TIME_BONUS` | +0.15 (18:00-22:00) / 0 (他) | 夜の社交時間帯ブースト |
| `P_MAX` | 0.9 | 上限 |

抽選は `seeded_rand(run_seed, tick, a_id, b_id)` で決定論化する。

#### 9.8.2 イベント種別の決定

交流が発生したら、現在の関係状態 (§9.9 relationship state) と抽選で type を決める。

| 現在の関係 | 出やすい type (重み) |
| --- | --- |
| `stranger` | `meeting` (0.7), `conversation` (0.3) |
| `acquaintance` | `conversation` (0.8), `conflict` (0.1), `farewell` (0.1) |
| `friend` | `conversation` (0.85), `conflict` (0.15) |
| `rival` | `conflict` (0.6), `conversation` (0.4) |

- type 語彙: `meeting`(出会い) / `conversation`(会話) / `conflict`(喧嘩) / `farewell`(別れ)。
- `summary` は MVP ではテンプレ文 (例: `"{a} and {b} met at {poi}."`)。後段で Gemini 生成に差し替える。
- 同一ペアが同 tick に複数 type を出さない。
- 1 tick あたりの interaction 総数に上限 `MAX_INTERACTIONS_PER_TICK = 50` を設け、超過分は次 tick 以降に持ち越さず破棄 (ログ肥大防止)。

### 9.9 relationship_delta 遷移ルール

関係状態は順序付きで管理する。

```
stranger < acquaintance < friend < close_friend
                            |
                            +-- rival (conflict 蓄積で分岐)
```

各エージェントペアは `score`(整数) と `state`(ラベル) を持つ。type ごとに score を増減し、しきい値で state を再計算する。

| type | score 増減 |
| --- | --- |
| `meeting` | +1 |
| `conversation` | +2 |
| `conflict` | -3 |
| `farewell` | -1 |

score → state しきい値:

| score 範囲 | state |
| --- | --- |
| score <= -3 | `rival` |
| -2 .. 0 | `stranger` |
| 1 .. 4 | `acquaintance` |
| 5 .. 9 | `friend` |
| score >= 10 | `close_friend` |

- イベント書き出し時、`relationship_delta = {"from": <更新前 state>, "to": <更新後 state>}` を埋める。state 不変でも from==to で出力する。
- ペアの初期状態: 互いが `social_networks` に入っていれば `score=3 (acquaintance)`、そうでなければ `score=0 (stranger)`。
- relationship state はラン全体で保持する (in-memory dict、key=`(min_id, max_id)`)。リプレイのため `relationships.jsonl` にスナップショットを残す (任意)。

### 9.10 social_networks による交流バイアス

`social_networks` は「知人候補リスト」として 2 箇所で使う。

1. **目的地バイアス (§9.3 social 行)**: 18:00-22:00 の social 目的地選択で、候補 POI のうち「現時刻に social_networks のメンバーが滞在/向かっている POI」があれば、その POI の重みを `FRIEND_GRAVITY = 3.0` 倍する。
   - 実装: 各 tick の冒頭で「POI → 滞在/目的地エージェント集合」の逆引き index を作り、O(1) 参照する。
2. **interaction 発生確率 (§9.8.1)**: `is_in_network(a,b)` が true なら `SOCIAL_BONUS` を加算する。

social_networks が空/欠落のエージェントはバイアス 0 で通常ルールに従う。

## 10. LLM連携仕様 (後段マイルストーン)

### 10.1 Provider抽象

LLMは以下のようなインターフェースで差し替え可能にします。MVP はルールベースで完走し、後段で Vertex AI / Gemini に差し替えます。

```python
class LLMProvider:
    def complete(self, prompt: str, *, temperature: float = 0.7, max_tokens: int = 256) -> str:
        ...

class RuleBasedProvider(LLMProvider):
    """MVP デフォルト。LLM を呼ばず、ルール由来の決定論的テキストを返す。"""

class VertexGeminiProvider(LLMProvider):
    """後段。Vertex AI の Gemini を ADC 認証で呼ぶ。model 例: gemini-2.0-flash。"""
```

想定プロバイダ:

- ルールベースモック (MVP デフォルト / 認証不要 / LLM 不要で完走)
- Vertex AI / Gemini (後段マイルストーン専用。Cloud Run 上で Application Default Credentials 経由で呼ぶ)

MVP の挙動決定・会話・関係性更新はすべてルールベースモックで動作する。Gemini は後段で `LLMProvider.complete()` を差し替えるだけで有効化できる。LLM の直接呼び出しは禁止し、必ず Provider 抽象越しに使う。

### 10.2 LLMを使う対象

| 対象 | MVP | 後続 |
| --- | --- | --- |
| 行動決定 | ルールベース | Gemini で自然な日課/予定を生成。 |
| 会話生成 | イベントのみ(本文なし) | Gemini で会話要約を生成。 |
| 関係性更新 | 簡易ルール(§9.9) | Gemini で関係性変化の理由文を生成。 |

### 10.3 プロンプト入力

LLMに渡す情報は、定量・構造化を優先します。

- agent profile
- current time
- current location
- nearby POIs
- nearby agents
- recent visits
- recent interactions
- current relationship state

## 11. モジュール構成案

urban-ecosystem は単独デプロイ可能なアプリ (Cloud Run Service) として構成する。

```text
urban-ecosystem/
  app/
    main.py              # FastAPI: 静的配信 + リプレイデータAPI + (任意)sim実行API
    config.py            # 環境変数/Secret読込、fallback判定
    data_access.py       # 同梱 or GCS からの GeoJSON/JSONL 読込
    llm_provider.py      # LLMProvider 抽象 (RuleBased / VertexGemini)
  environments/
    urban_2d/
      __init__.py
      data_loader.py
      models.py
      road_graph.py      # MVPは直線補間。経路探索は後段
      simulation.py
      rules.py
      events.py
  tools/
    generate_urban_sample.py   # 合成データ生成 (seed固定)
    urban_simulation_cli.py    # バッチ実行 (Cloud Run Job 兼ローカルCLI)
    urban_viewer/
      index.html               # bootstrap loader + レイアウト骨格
      app.js                   # ViewerState / 再生ループ / イベント配線
      map_adapter.js           # adapter 共通インターフェース定義
      google_maps_adapter.js   # Maps JS API 実装 (Data layer + AdvancedMarker)
      fallback_map_adapter.js  # canvas/svg 投影実装 (APIキー無し)
      ui_panels.js             # 詳細パネル / 凡例 / 時刻コントロール DOM
      styles.css
  static/                # ビルド済アセットがあれば配置
  data/                  # 合成サンプル (同梱する小規模データ)
  Dockerfile
  cloudbuild.yaml
  requirements.txt
```

| モジュール | 責務 |
| --- | --- |
| `app/main.py` | FastAPI による静的配信・リプレイデータAPI・任意の sim 実行API。 |
| `app/config.py` | 環境変数/Secret 読込、fallback 判定。 |
| `app/data_access.py` | 同梱 or GCS からの GeoJSON/JSONL 読込。 |
| `app/llm_provider.py` | LLMProvider 抽象 (RuleBased / VertexGemini)。 |
| `data_loader.py` | GeoJSON/JSON/JSONL読込、正規化、検証。 |
| `models.py` | POI、AOI、AgentProfile、AgentState、InteractionEventの型。 |
| `road_graph.py` | 最近傍道路 (MVPは直線補間。経路探索は後段)。 |
| `rules.py` | MVP用のルールベース行動決定 (§9 の定数・ロジック)。 |
| `simulation.py` | tickループ、状態更新、ログ出力。 |
| `events.py` | 会話、出会い、関係性変化イベント。 |
| `map_adapter.js` | adapter 共通インターフェース (init/setLayer/upsertAgents/highlight/onAgentClick)。 |
| `google_maps_adapter.js` | Google Maps初期化、Marker/Polyline/Polygon描画、イベント処理。 |
| `fallback_map_adapter.js` | APIキーなしのテスト用簡易地図表示。 |
| `ui_panels.js` | 凡例・エージェント詳細・時刻コントロールの DOM 生成と更新。 |

## 11.1 採用する既存ライブラリ/公式サンプル

| 領域 | 採用 | 理由 |
| --- | --- | --- |
| Google Maps JS | Maps JavaScript API | 地図表示の本命。 |
| Google Maps loader | `importLibrary()` 方式 | 公式の動的ロード方式で、必要なライブラリだけ読み込める。 |
| GeoJSON | Google Maps Data layer | GeoJSONを直接読み込み、featureごとにスタイルとイベントを持てる。 |
| Agent marker | Advanced Markers | HTML/CSSで番号付き人物マーカーを作りやすく、アクセシビリティ対応もしやすい。 |
| Clustering | `@googlemaps/markerclusterer` | Google Maps Platform公式GitHub配下のクラスタリング実装。 |
| Maps examples | `googlemaps/js-samples` | 公式サンプルを実装参考にする。 |
| Web framework | FastAPI + uvicorn | Cloud Run Service の常駐web。 |
| Object storage | Cloud Storage | 大規模リプレイ JSONL の置き場 (スケール時)。 |
| LLM (後段) | Vertex AI / Gemini | 行動決定/会話/関係性更新の LLM 化。MVP はルールベースのみ。 |

## 11.2 実装メモ

- POI/AOI/Roadは可能な限りGoogle Maps Data layerで扱う。
- Agentは頻繁に位置更新するため、Data layerではなくAdvanced Markerで管理する。
- 100体ではクラスタリングなしでもよいが、ビューアの設計はMarkerClustererを後付けできるようにする。
- Google Maps APIキーがないテストでは、`fallback_map_adapter.js` で緯度経度を画面座標に線形変換して描画する。
- 公式サンプルコードは構造の参考に留め、必要な範囲だけ実装へ取り込む。

## 12. CLI仕様

### 12.1 シミュレーション実行

```bash
python tools/urban_simulation_cli.py run \
  --pois data/pois.geojson \
  --aois data/aois.geojson \
  --roadnet data/roadnet.geojson \
  --profiles data/agent_profiles_N100.json \
  --seed 42 \
  --out experiments/results/urban_demo
```

同一スクリプトを Cloud Run Job のエントリポイントとしても使う。

### 12.2 リプレイビュー起動 (ローカル開発)

```bash
uvicorn app.main:app --reload --port 8080
```

ローカルでは `app/main.py` (FastAPI) が静的アセットとリプレイデータAPIを配信する。

## 13. 検証仕様

### 13.1 データ検証 (正本: data-contract §Field Types and Constraints)

構造:

- 各 GeoJSON が FeatureCollection としてパースできる。
- POI=Point / AOI=Polygon|MultiPolygon / Road=LineString|MultiLineString。
- 全 JSONL は1行1 JSON オブジェクト。

ID/参照整合:

- POI/AOI/Road/Agent の id が各コレクション内で一意。
- id 接頭辞が命名規約に一致 (poi_/aoi_/road_、agent は integer)。
- AgentProfile.home_poi_id / work_or_school_poi_id が既存 POI を参照。
- AgentProfile.social_networks の各要素が既存 agent id、自己 id を含まない。
- VisitRecord.agent_id / AgentState.agent_id / InteractionEvent.agent_ids が既存 agent。
- VisitRecord.poi_id は既存 POI id または予約値 `initial_position`。
- InteractionEvent.agent_ids は要素数>=2・重複なし。

値域/型:

- lat∈[-90,90], lon∈[-180,180]。
- time が `HH:MM:SS` 正規表現に一致、秒は MVP では `00`。
- tick,day が非負整数。`tick`→`time` 変換式 (contract §Time and Tick) と (day,time) が矛盾しない。
- action/status/type/visit.action が enum に含まれる (未知値は warning として人間可読に列挙)。

エラー表示:

- invalid input は「ファイル名・行番号(JSONL)・違反フィールド・期待値」を人間可読で出す。

### 13.2 UI検証

- 地図が表示される。
- POIレイヤーをON/OFFできる。
- AOIレイヤーをON/OFFできる。
- 道路レイヤーをON/OFFできる。
- エージェントが100体表示される。
- エージェントをクリックすると詳細が表示される。
- 再生/停止/ステップ送りが動く。
- 時刻表示がtickに応じて更新される。

### 13.3 シミュレーション検証

#### 13.3.1 完走・出力 (基本)

- 100 体、24 tick 以上で例外なく完走する。
- `agent_states.jsonl` / `poi_visit_records.jsonl` / `interaction_events.jsonl` / `summary.json` が出力される。
- LLM 認証情報(Vertex/Gemini)がなくてもルールベースで完走する (RuleBasedProvider)。

#### 13.3.2 決定論・再現性

- 同一 seed・同一入力で 2 回実行し、3 出力ファイルが byte 一致する。
- seed を変えると interaction_events の件数が変化する (= 乱数が効いている証跡)。

#### 13.3.3 挙動の妥当性 (invariant チェック)

- 全 agent_state の `lat`/`lon` が入力 POI の bounding box + 余裕 500m 以内に収まる (テレポート検知)。
- 連続 tick 間の同一 agent の移動距離が `STEP_M * 1.1` 以下 (直線補間の上限超過検知)。
- 各 visit record の `poi_id` が POI 集合に存在する (no_target 除く)。
- `interaction_events` の `agent_ids` が全て profile に存在し、同一 tick で同一正規化ペアが重複しない。
- 08:00-10:00 帯で office_worker の過半数が `commute`/`work` reason を持つ (時刻帯ルールが効いている証跡)。

#### 13.3.4 関係性遷移の妥当性

- 任意の relationship_delta で `from`→`to` が §9.9 の隣接遷移(score 連続変化)で説明可能。1 イベントで stranger→close_friend のような飛躍が起きない。
- conflict イベント後のペア score が減少している。

#### 13.3.5 規模・性能 (MVP 目安)

- 100 体 × 192 tick が単一 Cloud Run コンテナ(または手元)で実用時間内に完走する。[推測] 数秒〜十数秒オーダー。具体閾値は実測後に確定。
- 近接判定が POI bucket 化されており、全ペア O(N^2) を毎 tick 実行していない (コードレビュー項目)。

### 13.4 デプロイ検証 (Cloud Run)

- コンテナがローカルで `docker run` 起動し、`GET /api/health` に 200 を返す。
- Cloud Run リビジョンが READY になる。
- 公開URLでリプレイビューが開き、サンプルデータで100体が表示される。
- `GOOGLE_MAPS_API_KEY` を Cloud Run の Secret Manager から注入できる。
- APIキー未設定時はフォールバック地図で起動し、500 を返さない。
- Maps APIキーがイメージ・git・ログに平文で含まれない。

## 14. 受け入れ基準

- サンプルデータで地図ビューが起動し、POI/AOI/道路/エージェントが表示される。
- 100体のプロフィールを読み込み、番号付きマーカーとして表示できる。
- エージェント詳細に名前、年齢、説明文、現在POI、時刻、social network IDsが表示される。
- `agent_states.jsonl` から、Day 0 08:00以降の動きをリプレイできる。
- ルールベースの最小シミュレーションで `agent_states.jsonl`、`poi_visit_records.jsonl`、`interaction_events.jsonl` が生成される。
- 合成データ生成スクリプトが seed 固定で再現可能な POI/AOI/Road/プロフィール/状態ログを出力する。
- アプリが Google Cloud Run 上のコンテナとして起動し、公開URLで上記リプレイが動作する。
- `GOOGLE_MAPS_API_KEY` 未設定でもフォールバック地図で起動し、致命的エラーで落ちない。

## 15. 実装マイルストーン

### Milestone 1: データローダー

- `environments/urban_2d/models.py` を追加。
- `environments/urban_2d/data_loader.py` を追加。
- GeoJSON/JSON/JSONLの検証テストを追加。

### Milestone 2: リプレイビュー

- FastAPI ベースのビューアサーバ (`app/main.py`) を追加。
- POI/AOI/道路/エージェント表示を実装。
- 時刻コントロールとエージェント詳細を実装。

### Milestone 3: 最小シミュレーション

- tickループを追加。
- ルールベース行動決定 (§9) を追加。
- 訪問履歴、状態、イベントログを出力。

### Milestone 4: Cloud Run デプロイ

- アプリをコンテナ化する (Dockerfile)。
- ローカルで `docker run` 起動・ヘルスチェックを通す。
- Cloud Run へデプロイし、公開URLでリプレイビューを動かす。
- `GOOGLE_MAPS_API_KEY` を環境変数 / Secret Manager 経由で注入する。
- APIキー未設定時のフォールバック地図起動を確認する。

### Milestone 5: LLM社会行動 (Vertex AI / Gemini)

- Provider抽象を追加する (`app/llm_provider.py`)。
- Vertex AI / Gemini による行動決定、会話要約、関係性更新を追加する。
- 監査用ログを追加する。

### Milestone 6: スケール対応

- エージェント表示のクラスタリングを追加する。
- LLM呼び出しのバッチ化/キャッシュを追加する。
- 大規模リプレイ JSONL の GCS 配信と Cloud Run Job 事前生成を追加する。
- 1,000体以上のリプレイに対応する。

## 16. 未決事項

| # | 論点 | 回答案 (MVP) |
| --- | --- | --- |
| 1 | サンプル都市データをリポジトリに含めるか、生成スクリプトで作るか。 | 両建て。小規模合成データ (100 agent / ~300 POI / 24 tick) は `data/` に同梱しイメージに焼く。大規模・再生成は `generate_urban_sample.py` (seed固定)。同梱データは数MB以内に抑える。 |
| 2 | 道路ネットワークの経路探索をMVPでどこまで厳密に行うか。 | MVPは直線補間のみ。`roadnet.geojson` は表示専用で、`road_graph.py` は最近傍道路スナップのみ。A* 等の経路探索は後段。 |
| 3 | LLMプロバイダを既存 `core/llm/` に統合するか、都市用に分けるか。 | urban 専用に分離 (`app/llm_provider.py`)。月面 monorepo の `core/` には依存させない。プロバイダは Vertex AI / Gemini 単一。MVPはLLM不使用のため後段M5で確定。 |
| 4 | Cloud Run の認証・公開範囲 (未認証許可 / IAP) をどうするか。 | **デプロイ時に決定 (CEO 保留 2026-05-29)**。Milestone 4 のデプロイ直前に未認証公開 / IAP / IAM を確定する。それまで実装はどちらでも動く構成にする。 |
| 5 | Google Maps APIキーの注入経路 (環境変数 vs Secret Manager) と referrer 制限。 | Cloud Run の Secret Manager 連携を第一候補。HTTP referrer は本番ドメイン + `*.run.app` に限定。API 制限は Maps JavaScript API のみ。 |
| 6 | 本番用 Map ID を自前発行するか。 | 本番は自前 Map ID 発行を推奨。MVP 検証は `*.run.app` 上のフォールバック Map ID で開始可。[推測] |
| 7 | fallback 投影を線形のままで渋谷規模の歪みを許容するか。 | 許容する (MVPは等距離線形)。Web Mercator は採用しない。[推測] |

(基盤=Cloud Run / 地図=Google Maps JS API / LLM後段=Vertex AI・Gemini は確定済みのため未決から除外)

### 確定事項 (2026-05-29 CEO)

| 論点 | 決定 |
| --- | --- |
| リポジトリ構成 | **独立 git リポジトリ**。`urban-ecosystem/` を単独 repo として `git init` し、月面 monorepo とは切り離す。CI も urban 専用に持つ。 |
| デプロイ先 GCP プロジェクト | **`nexus-ai-2045` (事業用)**。本 spec の `<project>` プレースホルダは `nexus-ai-2045` に読み替える。 |
| Cloud Run 公開範囲 (#4) | デプロイ時に決定 (保留)。実装は未認証/認証どちらでも動く構成にする。 |

## 17. デプロイ基盤 (Google Cloud Run)

### 17.1 Service と Job の使い分け

| 用途 | 実行基盤 | 起動契機 | 理由 |
| --- | --- | --- | --- |
| 地図ビューア配信 + リプレイデータAPI + 任意のsim実行API | Cloud Run **Service** (常駐web / HTTP) | リクエスト | ユーザーが常時アクセスするWeb。スケール0可、コールドスタート許容。 |
| 大規模シミュレーションの事前生成 (リプレイ用JSONL生成) | Cloud Run **Job** (バッチ) | 手動 / Scheduler | 長時間処理をHTTPタイムアウトから切り離す。結果をGCSへ書き出す。 |

MVPは Service のみで成立する (同梱サンプルデータでリプレイ)。Job は「大規模データを事前生成してGCSに置く」段階で追加する。同一イメージを `tools/urban_simulation_cli.py` のエントリポイント差し替えで Service/Job 兼用にする。

### 17.2 データ置き場所と読込経路

| データ | MVP | スケール時 |
| --- | --- | --- |
| 合成 GeoJSON / profiles / 小規模リプレイ JSONL | イメージ同梱 (`data/`) | 同左 or GCS |
| 大規模リプレイ JSONL (数十MB超) | — | GCS バケット `gs://nexus-ai-2045-urban-data/runs/<run_id>/` |

`app/data_access.py` が `DATA_SOURCE` (`local`/`gcs`) env で経路を切り替える。local=同梱パス、gcs=`google-cloud-storage` SDK + Application Default Credentials。フロントは `/api/data/<run_id>/agent_states.jsonl` 等のAPI越しに取得 (CORS同一オリジン)。

### 17.3 API エンドポイント (FastAPI)

| メソッド | パス | 用途 |
| --- | --- | --- |
| GET | `/` | 地図ビューアHTML (Maps APIキー埋込み済 or fallback) |
| GET | `/static/*` | SPA静的アセット |
| GET | `/api/health` | ヘルスチェック (Cloud Run liveness) |
| GET | `/api/runs` | 利用可能 run_id 一覧 |
| GET | `/api/data/{run_id}/{file}` | GeoJSON/JSONL/summary 配信 |
| POST | `/api/simulate` | (任意) 小規模ルールベースsimを同期実行しJSONL返却。大規模はJobへ誘導 |

### 17.4 ローカル開発と本番の差分

| 項目 | ローカル | Cloud Run 本番 |
| --- | --- | --- |
| Maps APIキー | `.env` `GOOGLE_MAPS_API_KEY` (無→fallback地図) | Secret Manager → env 注入 |
| データ経路 | `DATA_SOURCE=local` (同梱) | `local` (MVP同梱) / `gcs` (スケール時) |
| 認証 | ADC (gcloud auth) / なし | サービスアカウント (Workload Identity) |
| 起動 | `uvicorn app.main:app --reload --port 8080` | `uvicorn` Dockerコンテナ |
| LLM後段 | ルールベースモック | Vertex AI / Gemini |

fallback 地図は `fallback_map_adapter.js` が緯度経度を画面座標へ線形変換して描画する (Maps APIキー / 課金不要)。CI とローカルはこの経路でUI検証する。

### 17.5 Secrets / IAM

- `GOOGLE_MAPS_API_KEY`: Secret Manager に格納。Cloud Run デプロイ時に `--set-secrets=GOOGLE_MAPS_API_KEY=urban-maps-key:latest` で注入。
- フロント露出キーは HTTP referrer 制限 (`*.run.app` + 本番ドメイン) + Maps JavaScript API 限定。
- ランタイム SA は専用作成 (`urban-run@nexus-ai-2045.iam`)。付与は最小権限:
  - Secret Manager Secret Accessor (Mapsキー読取)
  - (GCS使用時) Storage Object Viewer (読取専用バケット)
  - (LLM後段時) Vertex AI User
- ビルドは Cloud Build SA。デプロイ実行者は別IAMで分離。
- APIキー / SA鍵は git / イメージ / ログに焼かない。

### 17.6 Dockerfile / cloudbuild 方針

軽量Python イメージ (`python:3.12-slim`) + FastAPI + 静的アセット。GPU 依存・メディア処理依存は含めない。

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY environments/ ./environments/
COPY tools/ ./tools/
COPY static/ ./static/
COPY data/ ./data/
ENV PORT=8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

`requirements.txt`: `fastapi`, `uvicorn[standard]`, `google-cloud-storage` (GCS時), `google-cloud-aiplatform` (LLM後段時のみ)。

デプロイ:

```bash
gcloud run deploy urban-ecosystem \
  --project nexus-ai-2045 \
  --source . \
  --region asia-northeast1 \
  --set-secrets=GOOGLE_MAPS_API_KEY=urban-maps-key:latest \
  --service-account=urban-run@nexus-ai-2045.iam.gserviceaccount.com
```

(`--source .` で Cloud Build が自動ビルド。明示制御したい場合のみ `cloudbuild.yaml`)
公開範囲フラグ (`--allow-unauthenticated` か IAP/IAM) はデプロイ時に確定する (§16 #4)。ランタイム SA は `urban-run@nexus-ai-2045.iam.gserviceaccount.com`。

## 18. テスト戦略

### 18.1 レイヤ別方針

| レイヤ | 手段 | 対象 |
| --- | --- | --- |
| データローダー / シミュレーション / 合成データ生成 | pytest (unit + contract) | パース・検証・正規化・tickループ・ログ出力。data contract 準拠を contract test で担保。 |
| ビューアサーバ | pytest (HTTP) | 静的配信・データAPIエンドポイント・404/500ハンドリング。 |
| フロントエンド (地図UI) | E2E (Playwright) | 地図表示・レイヤON/OFF・100体マーカー・クリック詳細・再生/停止/スライダー。 |
| Cloud Run デプロイ | smoke test | コンテナ起動・ヘルスチェック・公開URL疎通。 |

### 18.2 pytest 構成

- `tests/environments/test_urban_data_loader.py` — ローダー検証 (§13.1 を機械化)。
- `tests/tools/test_generate_urban_sample.py` — 合成データ生成 (seed固定・contract準拠)。
- `tests/environments/test_urban_simulation.py` — 100体24tick完走・3種JSONL出力 (§13.3)。
- `tests/app/test_main.py` — サーバ配信・APIエンドポイント。
- 実行: `python -m pytest tests/ -v -p no:cacheprovider`。

### 18.3 フロント E2E (Playwright)

- フォールバック地図モード (`GOOGLE_MAPS_API_KEY` 無し) で実行し、外部APIキー・課金に依存させない。
- §13.2 UI検証の各項目を E2E ケース化する (地図表示 / レイヤ3種 / 100体表示 / クリック詳細 / 再生・停止・ステップ / 時刻更新)。
- ローカルサーバを起動し、ヘッドレスブラウザでリプレイを1サイクル走らせる。

### 18.4 CI 方針 (APIキー無し fallback)

- CI では `GOOGLE_MAPS_API_KEY` / Vertex AI 認証情報を **設定しない**。
- 地図は必ずフォールバック地図アダプタで起動し、外部課金APIを呼ばない。
- LLMはルールベースモック固定 (MVPは元々LLM不使用)。
- pytest と Playwright E2E を CI で実行する。外部APIに依存するテストは `@pytest.mark.requires_api` 等でスキップ可能にする。
- Cloud Run デプロイ smoke は CI とは分離し、デプロイ後に手動 / 別ジョブで実行する。

### 18.5 Definition of Done (テスト観点)

- 対応する pytest がある。
- `python -m pytest tests/ -v -p no:cacheprovider` が通る。
- フロント E2E がフォールバック地図で通る。
- 生成物 (実験出力・コンテナイメージ) がコミット対象に混入していない。
