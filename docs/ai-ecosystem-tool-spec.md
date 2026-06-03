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
4. Agent: AdvancedMarkerElement で生成。PinElement で番号付きピン (`glyphText = String(agent_id)`、role で色分け)。click で選択イベント発火。
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
- 性能受け入れ目安 [実装時確定: 100体 1x 再生を主要ブラウザ (Chrome/Firefox/Safari) で requestAnimationFrame ループ実測し、実測 fps を記録する]: 目標 30fps 以上。下回る場合は補間オフに degrade する。

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
  "name": "井上翔",
  "surname": "井上",
  "given": "翔",
  "age": 30,
  "gender": "male",
  "occupation": "エンジニア",
  "personality": "几帳面",
  "hobbies": ["プログラミング", "ゲーム"],
  "day_pattern": "morning",
  "description": "A local engineer who codes by night.",
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

必須: `id` (integer), `name`, `initial_position`／任意 (既存): `age`, `gender`, `description`, `home_poi_id`, `work_or_school_poi_id`, `role`, `social_networks`。`social_networks` は既存 agent id 配列で、自己 id を含めない・重複なし。
任意 (WO-006 追加): `surname` (姓), `given` (名 / `name == surname + given`), `occupation` (職業詳細), `personality` (性格傾向), `hobbies` (趣味リスト / string[]), `day_pattern` (`"morning"` | `"night"` | `"balanced"`)。

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

- 100 体 × 192 tick が単一 Cloud Run コンテナ(または手元)で実用時間内に完走する。[実装時確定: Cloud Run Job (または手元) で `time python tools/urban_simulation_cli.py run --agents 100 --ticks 192` を実測し、経過秒数を合格閾値として記録する] 暫定目安: 数秒〜十数秒オーダー。
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
| 6 | 本番用 Map ID を自前発行するか。 | 本番は自前 Map ID 発行が必須。`DEMO_MAP_ID` は開発・テスト専用であり本番利用は Google の利用規約で禁止されている。Milestone 4 デプロイ時に Cloud Console で Map ID を発行し、Secret Manager 経由で注入する。[事実: developers.google.com/maps/documentation/javascript/advanced-markers/start] |
| 7 | fallback 投影を線形のままで渋谷規模の歪みを許容するか。 | 許容する (MVPは等距離線形)。Web Mercator は採用しない。[事実: 設計決定+計算実測] bbox 内の cos(lat) 変化は ±0.009% → 最大位置誤差 0.1m で無視可。ただし lat/lon を等スケール (1度=1度) で扱うため経度方向のアスペクト比が約 23% 短縮される (渋谷緯度での lon_km/lat_km ≒ 0.81)。fallback の用途は CI テスト (bbox 内収束 / tick 間変化の assert) であり、アスペクト比の視覚的歪みはその目的に支障なし。 |

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

MVP の viewer API は `DATA_SOURCE=local` のみを実装する。`DATA_SOURCE=gcs` はスケール時の予約値であり、GCS 配信実装が入るまでは `/api/runs` と `/api/data/{run_id}/{file}` が 501 を返す。フロントは `/api/data/<run_id>/agent_states.jsonl` 等のAPI越しに取得 (CORS同一オリジン)。

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
| データ経路 | `DATA_SOURCE=local` (同梱) | `local` (MVP同梱) / `gcs` (スケール時予約値・現時点は501) |
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

## 19. 合成データ生成仕様 (WO-002)

> 正本: 本節。data-contract §Naming Conventions / §Coordinate Systems / §Enumerations との整合を優先する。
> スクリプト: `generate_urban_sample.py` (seed 固定・再現可能)。

### 19.1 概要と再現性

合成データは `generate_urban_sample.py` が 1 コマンドで生成する。seed を固定することで、再現性検証対象の 3 ファイル (`agent_states.jsonl` / `poi_visit_records.jsonl` / `interaction_events.jsonl`) が byte 一致で再現される (§13.3.2 が再現性検証の正本)。

```python
SEED = 42           # 既定値。CLI 引数 --seed で上書き可。
RUN_ID = "urban_demo"
rng = random.Random(SEED)   # 全乱数をこの rng から導出し、グローバル state を汚染しない
```

`random.Random(SEED)` を 1 インスタンスとして全生成ステップに順番に通す。呼び出し順を変えると出力が変わるため、ステップ順を §19.2 → §19.3 → §19.4 → §19.5 → §19.6 に固定する。rng の消費順序は §19.7 で固定する (変更禁止)。

### 19.2 合成都市の地理 (bbox)

渋谷駅周辺を模した合成 bbox を定数化する。[事実: kyorikeisan.com / rosenzu.net 複数ソース一致: 渋谷駅実座標は lat≈35.6581 / lon≈139.7017 (WGS84)。bbox (lat 35.655-35.670 / lon 139.695-139.710) は駅をほぼ中心に含み、緯度方向≒1.67km / 経度方向≒1.35km の合成都市規模として妥当。実在地物の再現は行わない]

```python
# --- 既定の定数 (generate_urban_sample.py の冒頭に置く) ---
BBOX = {
    "lat_min": 35.655,
    "lat_max": 35.670,
    "lon_min": 139.695,
    "lon_max": 139.710,
}
# bbox の幅: 緯度方向 ≒ 1.67 km / 経度方向 ≒ 1.27 km (WGS84 渋谷緯度での近似)
```

POI・エージェント初期位置・AOI 頂点はすべてこの bbox 内に収める。bbox 外への座標出力は禁止する (検証対象: §13)。

### 19.3 POI 生成

#### 19.3.1 カテゴリ分布と件数

合計 300 件を以下の比率で生成する (§16 #1 「~300 POI」)。category 名は data-contract §Naming Conventions の `<group>-<sub>` 形式に従う。

| カテゴリ | 件数 | 比率 | 備考 |
| --- | --- | --- | --- |
| `amenity-cafe` | 30 | 10% | 昼・夕方の目的地 |
| `amenity-restaurant` | 30 | 10% | 昼・夕方の目的地 |
| `amenity-fast_food` | 20 | 7% | 昼の目的地 |
| `amenity-bar` | 20 | 7% | 夕方・夜の目的地 |
| `shop-convenience` | 20 | 7% | errand の目的地 |
| `shop-clothing` | 15 | 5% | errand の目的地 |
| `shop-supermarket` | 10 | 3% | errand の目的地 |
| `leisure-park` | 15 | 5% | errand・wander の目的地 |
| `amenity-school` | 5 | 2% | student の work_or_school POI 候補 |
| `office-building` | 25 | 8% | office_worker の work POI 候補 |
| `home-residential` | 75 | 25% | エージェントの home POI 候補 |
| `other-misc` | 35 | 12% | wander / no_target のバッファ |
| 計 | 300 | 100% | |

category の group は §9.3 の目的地カテゴリ選択に部分一致でマッチする。

#### 19.3.2 座標散布

```python
def gen_poi_coords(rng, n):
    """bbox 内に一様乱数で n 点を散布する"""
    lats = [rng.uniform(BBOX["lat_min"], BBOX["lat_max"]) for _ in range(n)]
    lons = [rng.uniform(BBOX["lon_min"], BBOX["lon_max"]) for _ in range(n)]
    return list(zip(lats, lons))
```

座標は GeoJSON Feature の `geometry.coordinates` に `[lon, lat]` 順で格納する。`properties` に `lat`/`lon` を重複させない (data-contract §Coordinate Systems)。

#### 19.3.3 id 採番

通常 POI は `poi_001`〜の連番。`home-residential` は `poi_home_001`〜`poi_home_075`、`office-building` は `poi_work_001`〜`poi_work_025`、`amenity-school` は `poi_school_001`〜`poi_school_005` とする (data-contract §Naming Conventions の例示に準拠)。

### 19.4 AgentProfile 生成

#### 19.4.1 件数・基本属性の分布

合計 100 体。id は integer の 0〜99 連番 (§3 / data-contract §Agent Profile)。

| 属性 | 値の分布 |
| --- | --- |
| `id` | 0〜99 (integer) |
| `name` | `surname + given` で構成。`surname == name[:len(surname)]` が成立する (WO-006) |
| `surname` | 姓 20 パターンからランダム選択 / リスト: `["田中","佐藤","鈴木","高橋","渡辺","伊藤","山本","中村","小林","加藤","吉田","山田","佐々木","山口","松本","井上","木村","林","清水","斎藤"]` |
| `given` | 名 20 パターンからランダム選択 / リスト: `["健","誠","拓也","翔","大輝","蓮","颯","陸","優斗","海斗","さくら","葵","陽菜","美咲","彩","結衣","莉子","七海","凜","ひかり"]` (実在人物の直接再現は意図せず) |
| `age` | 20〜65 の一様整数 |
| `gender` | `"male"` 50 体 / `"female"` 50 体 |
| `role` | `office_worker` 60% (60 体) / `student` 20% (20 体) / `other` 20% (20 体) |
| `occupation` | role 別リストからランダム選択 (WO-006 / Step 10) |
| `personality` | 12 パターンからランダム選択 (WO-006 / Step 11) |
| `hobbies` | 18 種のプールから 1〜3 件をランダム選択 (WO-006 / Step 12) |
| `day_pattern` | `"morning"` / `"night"` / `"balanced"` をシャッフルして割当て (WO-006 / Step 13) |

```python
ROLES = (["office_worker"] * 60 + ["student"] * 20 + ["other"] * 20)
rng.shuffle(ROLES)  # seed 由来のシャッフル (Step 2)
```

rng 消費順序 (§19.7 + WO-006 拡張):

| Step | 操作 |
| --- | --- |
| 1 | POI 座標 (lat/lon 各 n_pois 回) |
| 2 | role shuffle |
| 3 | home_poi_id 割当て (n_agents × choice) |
| 4 | work_or_school_poi_id 割当て (office+student のみ × choice) |
| 5 | social_networks (C(n,2) × random) |
| 6 | road shuffle |
| 7 | surname/given/name (n_agents × 2 choice) |
| 8 | age (n_agents × randint) |
| 9 | gender shuffle |
| 10 | occupation (n_agents × choice / role 別リスト) |
| 11 | personality (n_agents × choice) |
| 12 | hobbies (n_agents × randint(1,3) + sample) |
| 13 | day_pattern shuffle |

#### 19.4.2 home_poi_id の割当て

`home-residential` POI 75 件からランダム (重複あり) にエージェントへ割当てる。[事実: 設計決定/§19.3.1+§19.4.1] 75 件の home POI を 100 体が共有する設計で確定。1 件の home に複数エージェントが割当たることを許容する (`rng.choice` で独立抽選)。

```python
home_pois = [p["id"] for p in pois if p["category"] == "home-residential"]
for agent in agents:
    agent["home_poi_id"] = rng.choice(home_pois)
```

#### 19.4.3 work_or_school_poi_id の割当て

- `office_worker` → `office-building` POI 25 件からランダム (重複あり)。
- `student` → `amenity-school` POI 5 件からランダム (重複あり)。
- `other` → `work_or_school_poi_id` を割当てない (フィールド省略)。§9.3 の「`work_or_school_poi_id` が無い場合は `initial_position` 最近傍 POI で代替」に委ねる。

#### 19.4.4 initial_position の決め方

開始位置は割当て済み `home_poi_id` の POI 座標と同一にする。これにより tick=0 の全エージェントが自宅付近に存在する初期状態を作る。

```python
poi_coords = {p["id"]: (p["lat"], p["lon"]) for p in pois}  # flat dict (lat/lon 個別)
for agent in agents:
    lat, lon = poi_coords[agent["home_poi_id"]]
    agent["initial_position"] = {"lat": lat, "lon": lon}
```

`initial_position` は flat JSON の `{lat, lon}` キーで持つ (data-contract §Coordinate Systems)。

### 19.5 social_networks 生成

#### 19.5.1 パラメータ

| パラメータ | 値 | 備考 |
| --- | --- | --- |
| 平均次数 | 5 | エージェント 1 体あたり平均 5 本の辺 |
| グラフ種別 | Erdős-Rényi G(n, p) | n=100, p = mean_degree / (n-1) ≈ 0.0505 |
| 有向/無向 | 無向 (相互リスト) | A と B が接続 → 双方の `social_networks` に相手を追加 |
| 自己ループ | 禁止 | 自己 id を含めない (data-contract §Agent Profile / §9.7 検証 §13.1) |
| 重複 | 禁止 | 同一 id の重複なし (data-contract §Agent Profile) |

#### 19.5.2 生成手順

```python
def build_social_networks(n, mean_degree, rng):
    p = mean_degree / (n - 1)
    adj = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p:
                adj[i].add(j)
                adj[j].add(i)
    # list に変換し昇順ソートで deterministic にする
    return {i: sorted(adj[i]) for i in range(n)}
```

`social_networks` が空のエージェント (孤立ノード) は許容する。空/欠落のエージェントは §9.10 のバイアス 0 で通常ルールに従う。

### 19.6 AOI / Road 生成

#### 19.6.1 AOI (矩形ポリゴン)

bbox を規則的に分割した矩形を 10 枚生成する (§16 #1 summary.json 例 `"aois": 10`)。

```python
AOI_ROWS, AOI_COLS = 2, 5   # 2 行 × 5 列 = 10 枚

def gen_aois(bbox, rows, cols):
    aois = []
    dlat = (bbox["lat_max"] - bbox["lat_min"]) / rows
    dlon = (bbox["lon_max"] - bbox["lon_min"]) / cols
    n = 1
    for r in range(rows):
        for c in range(cols):
            lat0 = bbox["lat_min"] + r * dlat
            lat1 = lat0 + dlat
            lon0 = bbox["lon_min"] + c * dlon
            lon1 = lon0 + dlon
            # GeoJSON Polygon: coordinates は [lon, lat] 順, 閉じたリング
            ring = [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]
            aois.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {"id": f"aoi_{n:03d}", "name": f"District {n}", "category": "district"},
            })
            n += 1
    return aois
```

AOI の座標も `[lon, lat]` 順 (data-contract §Coordinate Systems)。

#### 19.6.2 Road (POI 間 LineString)

WO-011 (2026-05-31) でトポロジーを **距離順スパニングツリー (Prim 法 MST)** に変更した。
従来の Hamilton chain (一筆書き / `rng.shuffle` 後の隣接ペア) は迂回が長く、
道路追従 (--roadnet) シミュレーションで interaction が発生しにくい問題があった。
MST は最寄り POI 同士を結ぶため迂回を最小化し、interaction 発生を改善する。

rng 消費 (§19.7 Step 6): `rng.shuffle` 呼び出し自体は維持する。
shuffle 後の順序はトポロジーに使わないが、下流 Step 7-13 (demographics) の
rng 位置を変えないために消費を保存する。

```python
def gen_roads(pois, rng):
    # rng 位置保存のため shuffle は維持 (§19.7 Step 6 / 結果はトポロジーに使わない)
    shuffled = pois[:]
    rng.shuffle(shuffled)

    n = len(pois)
    # O(n^2) Prim 法: タイブレーク = (距離二乗, i, j) の昇順で決定論的に安定化
    in_tree = [False] * n
    nearest_dist = [float("inf")] * n
    nearest_from = [-1] * n
    in_tree[0] = True
    for j in range(1, n):
        nearest_dist[j] = (pois[0]["lat"]-pois[j]["lat"])**2 + (pois[0]["lon"]-pois[j]["lon"])**2
        nearest_from[j] = 0

    edges = []  # (min_idx, max_idx)
    for _ in range(n - 1):
        best_j = min((j for j in range(n) if not in_tree[j]),
                     key=lambda j: (nearest_dist[j], j))
        in_tree[best_j] = True
        edges.append((min(nearest_from[best_j], best_j), max(nearest_from[best_j], best_j)))
        for k in range(n):
            if not in_tree[k]:
                d = (pois[best_j]["lat"]-pois[k]["lat"])**2 + (pois[best_j]["lon"]-pois[k]["lon"])**2
                if d < nearest_dist[k] or (d == nearest_dist[k] and best_j < nearest_from[k]):
                    nearest_dist[k] = d
                    nearest_from[k] = best_j

    edges.sort()  # (min_idx, max_idx) 昇順で採番安定化
    roads = []
    for num, (i, j) in enumerate(edges, 1):
        a, b = pois[i], pois[j]
        roads.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[a["lon"], a["lat"]], [b["lon"], b["lat"]]]},
            "properties": {"id": f"road_{num:03d}", "walkable": True},
        })
    return roads
```

POI=300 件のスパニングツリーでは road 数は n_pois-1=299 本になる。[事実: 設計決定/§19.6.2] ~299 本で確定。summary.json 例の `"roads": 500` は hard requirement にしない。`length_m` は省略可 (data-contract §Road Feature で Optional)。

### 19.7 seed 固定と再現性の保証

| 保証レベル | 対象 | 方法 |
| --- | --- | --- |
| byte 一致 | `agent_states.jsonl` / `poi_visit_records.jsonl` / `interaction_events.jsonl` | `random.Random(SEED)` を同一順で消費する |
| byte 不一致 (許容) | `summary.json` | `started_at` (実行時刻) を含むため再現性検証対象外 (data-contract §Summary JSON) |
| byte 不一致 (許容) | `pois.geojson` / `aois.geojson` / `roadnet.geojson` | 静的生成で毎回同一だが再現性検証対象には含めない |

再現性検証は `python generate_urban_sample.py --seed 42` を 2 回実行し、3 ファイルの `sha256sum` が一致することで確認する (§13.3.2 が正本)。

#### rng 消費順序 (変更禁止)

```
Step 1: POI 座標生成 (300 calls × rng.uniform × 2)
Step 2: role シャッフル (1 call × rng.shuffle)
Step 3: home_poi_id 割当て (100 calls × rng.choice)
Step 4: work_or_school_poi_id 割当て (80 calls × rng.choice, office+student のみ)
Step 5: social_networks 生成 (C(100,2) = 4950 calls × rng.random)
Step 6: road 生成の POI シャッフル (1 call × rng.shuffle)
```

ステップを追加・削除・並べ替えた場合は seed を変えて再配布する。

### 19.8 生成スクリプト CLI インタフェース

```
python generate_urban_sample.py [--seed SEED] [--agents N] [--pois N] [--out-dir DIR]

既定値:
  --seed   42
  --agents 100
  --pois   300
  --out-dir data/
```

出力先の `data/` 以下に全ファイルを書き出す。ファイル名は data-contract §File Names に従う。

## 20. 行動ルール 補遺 (境界ケース)

本節は §9 の定数・テーブルと矛盾しない範囲で、未定義だった境界ケースの挙動を確定する。実装は `rules.py` で本節を参照する。

### 20.1 遠距離 commute — 08:00-10:00 で職場に到達できない場合

前提:

- `STEP_M = 390 m/tick` (§9.5)。
- commute 目的地は `work_or_school_poi_id` 固定 (§9.3)。
- 10:00 (tick=24) を過ぎると §9.3 テーブルは現 POI 滞在側に切り替わる (§9.3)。

決定ルール:

1. commute 継続優先: tick=24 (10:00) 時点でまだ `moving` の場合、`action` を `commute` のまま保持し移動を継続する。§9.3 の時刻帯は「新しい目的地を引く契機」であり、目的地確定済みの移動中エージェントには適用しない。[事実: §9.3「毎 tick、status が idle または滞在時間を消化済みのエージェントについて」の対偶 — moving は対象外]
2. 到達後に即 work/study 開始: 職場 POI 到達 tick に `arrived` を出力し、以降は §9.6 の通勤後滞在ルール (18:00 まで) に従い滞在する。到達 tick が 10:00 以降でも退勤時刻 (18:00) は変わらない。[事実: §9.6「commute→work/study: 18:00 まで 退勤時刻まで固定 POI 滞在」は到達タイミングを限定しない]
3. 打ち切りしない: 11:00・12:00 到達等でも commute を途中打ち切りしない。現実的な距離では無限ループにならないため打ち切り判定は追加しない。[事実: §9 に打ち切り条件の記述なし。設計決定として追加しない]
4. lunch 割り込み禁止: 12:00 到達前で移動中でも lunch への目的地切り替えはしない。commute 継続が優先する。[事実: §9.3 の評価対象は「idle または滞在消化済み」に限定。moving 状態には lunch 遷移契機が存在しない]
5. `action` フィールドの記録: 移動中 tick はすべて `action="commute"` / `status="moving"` で記録する (data-contract §Enumerations / §9.2)。

### 20.2 初日 tick=0 (08:00:00) の初期状態

前提:

- `tick=0` は `08:00:00` (data-contract §Time and Tick)。
- エージェントは `initial_position` から開始する (data-contract §Agent Profile)。

決定ルール:

1. 位置: tick=0 の `lat`/`lon` は `initial_position` の値をそのまま使う (data-contract §Agent State JSONL)。
2. `current_poi_id`: tick=0 時点では POI 未到達のため `null` (省略可)。ただし `initial_position` が既存 POI 座標と一致する場合はその POI の `id` を設定してもよい。[事実: 設計決定。到達判定は §9.5 の「残距離が STEP_M 以下なら到達」に従い tick=0 は initial_position から評価]
3. 目的地の引き方: tick=0 の処理冒頭で §9.3 テーブルを評価する。office_worker / student は `work_or_school_poi_id` を目的地として commute 開始。other は §9.3 テーブルの「上記いずれにも該当しない → wander」行を参照 (08:00-10:00 に office_worker/student 以外向けの明示行がないため)。[事実: §9.3 テーブル最終行「上記いずれにも該当しない 全員 wander」から直接導出]
4. tick=0 の `status`: 目的地を引けた場合は `moving`、初期位置 = 目的地 POI に一致する場合のみ `arrived`。候補が空なら `staying` (reason=`no_target`)。[事実: §9.4 項5「候補が空なら status を idle のまま据え置き、reason=no_target」、§9.2「idle は出力で staying にマップ」から直接導出]
5. visit_record の tick=0 出力: tick=0 で `arrived` となる場合のみ `poi_visit_records.jsonl` に 1 行出力する。移動開始は記録しない (§9.5)。

### 20.3 MAX_INTERACTIONS_PER_TICK=50 超過時の処理

前提:

- 上限 `MAX_INTERACTIONS_PER_TICK = 50` を超えた分は破棄する (§9.8.2)。
- 同一 tick・同一正規化ペアの interaction は 1 件まで (data-contract §Interaction Event JSONL)。

どのペアを残すか — 次の優先順位で上位 50 件を出力する:

| 優先順位 | 選択基準 | 根拠 |
| --- | --- | --- |
| 1 | 両者が互いの `social_networks` に含まれるペア | social 重視が §9.10 の設計方針 [事実: §9.10 が social_networks ペアを目的地バイアス・interaction 確率の両方で優遇することを明示。超過時選別でも同方針を適用] |
| 2 | 距離が近い順 (Haversine 昇順) | 近接物理モデルとの整合 [事実: §9.7 が PROXIMITY_M=30m を interaction の主要判定軸として定義。超過時選別でも近い順を採用するのは同設計原則の適用] |
| 3 | `seeded_rand(run_seed, tick, a_id, b_id)` 昇順 | 決定論性保持 (§9.8.1 の seeded_rand 定義を流用) |

破棄分の扱い:

- 破棄ペアの `score` / `state` は更新しない。当 tick では交流不成立として扱う。[事実: §9.8.2「超過分は破棄」= 交流不成立。§9.9 の score 更新は interaction type 発生の帰結であり、破棄された interaction は score 変化の原因にならない]
- 破棄ペアは「次 tick に持ち越さず破棄」(§9.8.2) の通り再試行しない。
- summary.json の `interactions` カウントには破棄分を含めない (出力件数のみ計上)。[事実: §9.8.2「超過分は破棄」= 出力なし。出力されないイベントは計上不可]

### 20.4 `no_target` が連続する場合の挙動

前提:

- 候補 POI が空の場合は status を `idle` のまま据え置き reason=`no_target` (§9.4 項5)。
- `idle` は出力 status では `staying` にマップ (§9.2 / data-contract §Enumerations)。

決定ルール:

1. 毎 tick 再評価: `no_target` のエージェントは次 tick でも §9.3 テーブルを評価する。候補が空でなくなれば通常の目的地選択に戻る。連続 `no_target` の tick 数に制限は設けない (MVP スコープでは POI 全滅は想定しない)。[事実: §9.3「毎 tick idle を評価」+ §9.4 項5「候補が空なら idle」の結合。§9 に tick 数制限の記述なし = 設計決定として制限なし]
2. 位置は変化しない: `no_target` の間は現在地に留まる (`lat`/`lon` 変化なし) (§9.4 から外挿)。
3. `action` フィールド: `no_target` を出力する (data-contract §Enumerations)。
4. 近接判定への参加: `no_target` (出力 status=`staying`) のエージェントは `at_poi` 内部状態ではないため §9.7 の interaction バケット対象に含めない。[事実: §9.7「毎 tick、status が at_poi のエージェント同士で近接ペアを検出する」の直接適用。no_target の内部状態は idle であり at_poi ではない]
5. visit_record は出力しない: 移動・到達がないため記録なし。[事実: §9.5「到達 tick に poi_visit_records.jsonl へ visit record を 1 行出力する」= 到達が出力条件。no_target は移動なし・到達なし → 条件未達]

### 20.5 滞在中エージェントが時刻帯境界 (例: 12:00) を跨いだ時の再評価タイミング

前提:

- 滞在中は内部状態 `at_poi` (出力 status=`staying`)。滞在 tick を消化したら §9.3 を再評価する (§9.6)。
- §9.3 は「毎 tick、status が idle または滞在時間を消化済みのエージェント」を評価する (§9.3)。

決定ルール:

1. 再評価契機は「滞在消化」のみ: 滞在時間未消化なら、時刻帯境界 (12:00 等) を跨いでも再評価せず元の action のまま滞在を続ける (§9.3 の条件が「消化済み」に限定されるため)。[事実: §9.3「毎 tick、status が idle または滞在時間を消化済みのエージェントについて」= 未消化の at_poi は評価対象外]
2. 消化と同 tick に境界が重なる場合: 消化 tick = 境界 tick なら、その tick で §9.3 を再評価し新しい時刻帯のルールに従う。[事実: §9.3/§9.6 の結合。消化済みフラグ立つ → §9.3 評価 → tick 現在の時刻帯ルール適用。tick 内処理順は §20.5 項5 実装メモで確定]
3. 例 (lunch → 午後): lunch (2-4 tick) を消化した tick が 13:00 以降なら、再評価で職場滞在中の office_worker は目的地変化なしで `work` 継続 (status は `staying` のまま)。[事実: §9.3「13:00-18:00 / office_worker → work_or_school_poi_id 固定」= 目的地は職場のまま変化なし]
4. `go_home` 割り込み禁止: 22:00 境界を迎えても滞在消化前なら `go_home` に切り替えない。消化後の再評価で 22:00 以降なら `go_home` が選ばれる。[事実: §9.3 の評価対象は「消化済み or idle」に限定。未消化なら 22:00 跨ぎでも評価なし = go_home 遷移なし。20.5 項1 と同一根拠]
5. 実装メモ: tick ループ内で「消化済み or idle」フラグを先に判定し、立っていれば §9.3 評価 → 目的地更新 → 移動開始の順で処理する。立っていなければ位置を保持して次 tick へ。[事実: §9.3「status が idle または消化済み」条件 + §9.4「候補空なら idle 据え置き」+ §9.5「到達でなければ記録なし」の結合で処理順序が確定]

## 21. API レスポンス schema 詳細

> 本節は §17.3 の API エンドポイント表を補完する。§17.3 が列挙するパスとメソッドと整合する。
> 正本: 本節。§17.3 との差異は本節を優先する。

### 21.1 run_id の命名規約と発見方法

命名規約 [事実: 設計決定/§21.1・§12.1・data-contract §Summary JSON]:

- `run_id` は CLI の `--out <dir>` 末尾ディレクトリ名から自動取得する。
  - 例: `--out experiments/results/urban_demo` → `run_id = "urban_demo"`
  - 例: `--out experiments/results/scenario_a_seed42` → `run_id = "scenario_a_seed42"`
- 推奨フォーマット: `<scenario>_seed<seed>` または自由な英数字・アンダースコア・ハイフン。スラッシュ・ドット・空白は禁止 (パストラバーサル防止)。
- バリデーション正規表現: `^[A-Za-z0-9_-]{1,128}$`。[事実: 設計決定/§21.1 — 上限 128 はパストラバーサル防止として仕様確定]

発見方法 (§17.2 `data/` 同梱 / §17.3 `/api/runs`):

- MVP (local): `data/` 配下のサブディレクトリを走査し、`summary.json` を持つものを run として列挙する。
- スケール時 (gcs): GCS 実装追加後に、GCS バケット `gs://nexus-ai-2045-urban-data/runs/` 直下のプレフィックスを列挙する。現時点で `DATA_SOURCE=gcs` を設定した場合は 501 を返す。
- フロントは必ず `/api/runs` を経由して run_id を取得し、`data/` を直接走査しない。
- manifest ファイルは設けない。[事実: 設計決定/§21.1 — summary.json の存在をマニフェスト代わりとする方針を確定]

### 21.2 GET /api/runs

利用可能な run の一覧を返す。フロントの run 選択 (§4.2 / §8.1) の入力源。

```
HTTP 200 OK
Content-Type: application/json
```

```json
{
  "runs": [
    {
      "run_id": "urban_demo",
      "seed": 42,
      "ticks": 24,
      "agents": 100,
      "pois": 300,
      "interactions": 12,
      "started_at": "2026-05-29T00:00:00Z"
    }
  ]
}
```

フィールド定義:

| フィールド | 型 | Required | 出典 |
| --- | --- | --- | --- |
| `run_id` | string | yes | data-contract §Summary JSON `run_id` |
| `seed` | integer | yes | data-contract §Summary JSON `seed` |
| `ticks` | integer | yes | data-contract §Summary JSON `ticks` |
| `agents` | integer | yes | data-contract §Summary JSON `agents` |
| `pois` | integer | yes | data-contract §Summary JSON `pois` |
| `interactions` | integer | yes | data-contract §Summary JSON `interactions` |
| `aois` | integer | no | data-contract §Summary JSON `aois` |
| `roads` | integer | no | data-contract §Summary JSON `roads` |
| `started_at` | string (ISO 8601) | no | data-contract §Summary JSON `started_at` |

- `runs` 配列はサーバが見つけた全 run を返す。ソート順は `started_at` 降順。[事実: 設計決定/§21.2 — ソートキー確定]
- run が 0 件のとき `"runs": []` を返す。4xx/5xx は返さない。
- 各要素は `summary.json` をそのまま転送する形で実装してよい。[事実: 設計決定/§21.2 — MVP 規模 (ラン数 < 100) ではキャッシュ不要。スケール時は要検討]

### 21.3 GET /api/data/{run_id}/{file}

run のデータファイルを 1 件ずつ返す。フロントはリプレイ開始時に必要なファイルを個別取得する。

#### 21.3.1 許可ファイル一覧 (data-contract §File Names を正本)

| file | Content-Type | MVP Required | 形式 |
| --- | --- | --- | --- |
| `pois.geojson` | `application/geo+json` | yes | GeoJSON FeatureCollection |
| `aois.geojson` | `application/geo+json` | no | GeoJSON FeatureCollection |
| `roadnet.geojson` | `application/geo+json` | no | GeoJSON FeatureCollection |
| `agent_profiles_N100.json` | `application/json` | yes | JSON 配列 |
| `agent_states.jsonl` | `application/x-ndjson` | yes | JSONL (1 行 1 JSON オブジェクト) |
| `poi_visit_records.jsonl` | `application/x-ndjson` | no | JSONL |
| `interaction_events.jsonl` | `application/x-ndjson` | yes | JSONL |
| `relationships.jsonl` | `application/x-ndjson` | no | JSONL |
| `summary.json` | `application/json` | yes | JSON オブジェクト |

上記 9 ファイル以外のパスは 403 Forbidden を返す (パストラバーサル防止・許可リスト方式)。[事実: 設計決定/§21.3.1 — `ALLOWED_FILES = frozenset({...})` による先頭チェックを実装方針として確定]

#### 21.3.2 JSONL の返却形式

JSONL ファイルは raw ストリーム (`application/x-ndjson`) として返す。JSON 配列に変換しない。

```
HTTP 200 OK
Content-Type: application/x-ndjson
```

ボディ例 (agent_states.jsonl 冒頭 2 行):

```
{"tick":0,"day":0,"time":"08:00:00","agent_id":0,"lat":35.659,"lon":139.700,"action":"commute","status":"moving"}
{"tick":0,"day":0,"time":"08:00:00","agent_id":1,"lat":35.661,"lon":139.702,"action":"staying","status":"staying"}
```

JSON 配列に変換しない理由: 大規模ファイルのストリーミングを想定し、配列変換するとサーバメモリにファイル全体を乗せる必要が生じるため。フロントは `fetch()` + `getReader()` でストリーミング、または一括 `text()` 後に行分割する。[事実: FastAPI 公式 docs — `StreamingResponse` は async/sync generator を受け取りチャンク単位で送出する。メモリ全乗せなしに大ファイルを返せる (source: github.com/fastapi/fastapi docs/advanced/stream-data.md)] MVP 規模 (24 tick × 100 agents = 2400 行) では一括取得でも問題ないが、設計はストリーミング互換とする。

#### 21.3.3 GeoJSON / JSON の返却形式

GeoJSON / JSON はファイルをそのまま転送する。Content-Type は GeoJSON が `application/geo+json`、JSON が `application/json`。

#### 21.3.4 エラーレスポンス

| 状況 | ステータス | レスポンス例 |
| --- | --- | --- |
| `run_id` が存在しない | 404 | `{"detail": "run not found: <run_id>"}` |
| `file` が許可リストにない | 403 | `{"detail": "file not allowed: <file>"}` |
| `file` が許可リストにあるが run に存在しない | 404 | `{"detail": "file not found: <file>"}` |
| `run_id`/`file` にパストラバーサル文字 (`..`, `/`) が含まれる | 403 | `{"detail": "invalid path"}` |

403 は許可リスト違反 (存在有無を明かさない)、404 は許可された上で存在しない場合に使い分ける。[事実: FastAPI 公式 docs — `from fastapi import HTTPException` で `raise HTTPException(status_code=403, detail="...")` / `raise HTTPException(status_code=404, detail="...")` として実装する (source: github.com/fastapi/fastapi docs/reference/exceptions.md)]

### 21.4 GET /api/health

Cloud Run の liveness チェックに使用する (§13.4 `GET /api/health` に 200 を返す)。

```
HTTP 200 OK
Content-Type: application/json
```

```json
{
  "status": "ok",
  "maps_key": "present",
  "data_source": "local",
  "data_source_supported": true
}
```

| フィールド | 型 | 値 | 備考 |
| --- | --- | --- | --- |
| `status` | string | `"ok"` 固定 | 200 を返す時点で常に `"ok"` |
| `maps_key` | string | `"present"` / `"absent"` | `GOOGLE_MAPS_API_KEY` の設定有無。キー値は返さない |
| `data_source` | string | `"local"` / `"gcs"` | `DATA_SOURCE` env の値 |
| `data_source_supported` | boolean | `true` / `false` | 現在の viewer API で配信可能な data source か |
| `data_source_error` | string | optional | `data_source_supported=false` の理由 |

- `maps_key` が `"absent"` でも 200 を返す (フォールバック地図で起動するため。§13.4 「APIキー未設定時はフォールバック地図で起動し、500 を返さない」)。
- Cloud Run liveness probe は HTTP 200 を判定基準とし、ボディの中身は probe が解釈しない。

### 21.5 POST /api/simulate (任意)

小規模ルールベース sim を同期実行しリプレイデータを返す。大規模は Cloud Run Job へ誘導する (§17.3 に記載)。MVP では実装任意 (Milestone 5 以降で確定)。以下は概形のみ。

リクエスト:

```
POST /api/simulate
Content-Type: application/json
```

```json
{ "seed": 42, "ticks": 24, "agents": 100 }
```

| フィールド | 型 | Required | デフォルト |
| --- | --- | --- | --- |
| `seed` | integer | no | `42` |
| `ticks` | integer | no | `24` |
| `agents` | integer | no | `100` |

小規模 (デフォルト `agents <= 100 and ticks <= 48`) の場合: [事実: 設計決定/§21.5 — MVP 同期境界値として確定。変更は §21.5 改訂で行う]

```
HTTP 200 OK
Content-Type: application/json
```

```json
{ "run_id": "sim_seed42_20260529T120000Z", "status": "completed", "ticks": 24, "agents": 100, "interactions": 12 }
```

結果は `data/` (local) または GCS に書き出し `run_id` を返す。フロントは後続で `/api/data/{run_id}/...` を取得する。[事実: 設計決定/§21.5 — `/api/data/` との一貫性を優先しリダイレクト方式に確定。データ本体埋め込みは採用しない]

大規模 (同期境界超過) の場合:

```
HTTP 202 Accepted
Content-Type: application/json
```

```json
{
  "status": "job_required",
  "message": "Request exceeds sync limit (agents > 100 or ticks > 48). Submit as Cloud Run Job.",
  "recommended_cli": "python tools/urban_simulation_cli.py run --seed 42 --agents 500 --ticks 192 --out experiments/results/large_run"
}
```

同期実行に失敗した場合 (タイムアウト等) は 504 Gateway Timeout を返す。[事実: 設計決定/§21.5 — Cloud Run のデフォルトリクエストタイムアウトを超過した場合の HTTP セマンティクスとして 504 を確定]

### 21.6 CORS / 同一オリジン方針

(§17.2 「フロントは `/api/data/<run_id>/agent_states.jsonl` 等の API 越しに取得 (CORS 同一オリジン)」)

- MVP は同一オリジン (CORS なし)。FastAPI のデフォルト CORS 設定を変更しない。
- フロント (`index.html`) と API (`/api/*`) は同一コンテナ・同一ポートで配信するため Same-Origin Policy を自然に満たす。
- `CORSMiddleware` は追加しない。[事実: FastAPI 公式 docs — FastAPI は `CORSMiddleware` を明示的に `app.add_middleware(CORSMiddleware, ...)` しない限り CORS ヘッダーを一切付与しない。デフォルトで CORS なし (source: github.com/fastapi/fastapi docs/tutorial/cors.md)] 将来外部 SPA からアクセスする場合のみ許可オリジンを追加。その際は `allow_origins=["https://<本番ドメイン>"]` に限定し `["*"]` は禁止。
- ローカル開発 (`uvicorn --reload`) でもポート 8080 の単一オリジンとなり CORS 問題は発生しない。
