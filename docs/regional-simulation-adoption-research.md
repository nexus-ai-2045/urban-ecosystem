# 地域限定シミュレーション外部調査と採用メモ

status: draft
version: 0.1.0
owner: maintainer
updated: 2026-06-01

## 目的

特定地域に限定した都市エージェントシミュレーションについて、既存 OSS / 公式ドキュメント / GitHub 実装から取り込める考え方を整理する。

この文書は「今すぐ依存追加するリスト」ではない。既存の `urban-ecosystem` は、軽量・決定論・API キーなし完動を守りながら、外部ベストプラクティスのうち相性の良いものだけを段階採用する。

## 現在の前提

- 現行実装は `pois.geojson` / `aois.geojson` / `roadnet.geojson` / `agent_profiles_N<N>.json` を入力にし、`agent_states.jsonl` / `poi_visit_records.jsonl` / `interaction_events.jsonl` を出力する。
- データ契約の正本は `docs/subagents/contracts/urban-ecosystem-data-contract.md`。
- 既定はルールベース・決定論。Vertex AI / Google Maps / Google Places は opt-in。
- 地域 realism は、実 API 呼び出しより先に「再現可能な地域データ取り込み」「活動連鎖」「検証指標」を固める。

## 調査サマリ

| 参照先 | 種別 | 取り込める考え方 | 採用判断 |
| --- | --- | --- | --- |
| OSMnx | Python / OSM / network | OSM から道路・施設を取得し、NetworkX / GeoPandas として扱う。地域境界、bbox、place name、point+distance で取得できる。 | 優先採用候補。Google Places 依存を減らし、offline fixture 化しやすい。 |
| Mesa / Mesa-Geo | Python ABM / GIS | model / agent / space / analysis / visualization を分ける。Mesa-Geo は GeoJSON / GeoPandas / shapefile から GeoAgent を作れる。 | 設計だけ優先採用。依存追加は後回し。 |
| ActivitySim | Activity-based travel modeling | household / person / tour / trip などの activity chain を、設定・係数・trace・サンプルサイズで管理する。 | 行動モデル設計を採用。実装依存は重すぎるため非採用。 |
| MATSim | 大規模 agent-based transport | 個人の 1 日 plan、交通 network、複数 mode、KPI 出力、反復最適化を扱う。 | 概念参照。現行 MVP には重い。 |
| eqasim | MATSim scenario bootstrap | open data から synthetic population と daily activity chain を地域別に作る。 | synthetic population の作り方を参照。直接導入は後段。 |
| SUMO | microscopic traffic simulation | OSM から road network を import し、需要・交通流・信号・車両/歩行者を厳密に扱う。network import 後の patch が重要。 | 交通流をやる段階まで保留。roadnet 品質チェック観点だけ採用。 |
| Overture Maps | open map data | places / buildings / transportation / divisions などを共通 schema で取得できる。 | Google Places 代替候補。PoC は別 gate。 |
| GTFS | transit schedule standard | stops / routes / trips / stop_times で公共交通の時刻表と停留所を扱う。 | 公共交通 mode を入れる時に採用候補。現行は保留。 |

## 採用方針

### 1. 地域データ取り込みを二段階にする

現状の Google Places 取得は opt-in として残しつつ、地域 realism の主経路は open data / fixture に寄せる。

優先順:

1. `synthetic`: 既存の決定論サンプル生成。
2. `osm_snapshot`: OSMnx / Overpass 由来の POI・道路をローカル fixture として保存。
3. `overture_snapshot`: Overture Places / Buildings / Transportation を地域 bbox で切り出す。
4. `google_places_live`: 明示 opt-in の live 取得。

重要なのは「live API を毎回叩く」ことではなく、地域 snapshot の入力を versioned artifact として持ち、同じ seed で同じ replay を再生成できること。

### 2. activity chain を明示データにする

ActivitySim / MATSim / eqasim から取り込むべき一番大きい考え方は、エージェントが毎 tick で自由に目的地を選ぶのではなく、1 日の予定構造を持つこと。

追加候補:

```json
{
  "agent_id": 26,
  "day": 0,
  "activities": [
    {"kind": "home", "start": "08:00:00", "end": "08:30:00", "poi_id": "poi_home_001"},
    {"kind": "work", "start": "09:00:00", "end": "12:00:00", "poi_id": "poi_work_001"},
    {"kind": "lunch", "start": "12:00:00", "end": "13:00:00", "category": "amenity-restaurant"}
  ]
}
```

これはすぐ contract 必須にしない。まず optional な `activity_plans.jsonl` として PoC し、既存の rule simulation は plan がなければ従来通り動く形にする。

### 3. 道路ネットワークは「生成」から「取り込み + 品質検査」へ寄せる

SUMO の scenario guide では、OSM などから import した network はそのままだと不自然な渋滞や teleport 的な問題につながるため、patch / edit / diff 管理が重要になる。現行の roadnet も、今後は次を検査する。

- connected component 数。
- isolated POI から最近傍道路までの距離。
- home / work / school / food POI が到達可能 component にあるか。
- 経路なし fallback が何回発生したか。
- route length と直線距離の比率が極端でないか。

### 4. 検証指標を replay 出力から計算する

Mesa の DataCollector / batch run の発想を、軽量な `summary.json` と `metrics.json` に落とす。

最初に足す指標:

| 指標 | 意味 |
| --- | --- |
| `trip_count_by_action` | commute / lunch / social などの移動回数 |
| `arrival_rate` | target を持った移動のうち到着できた割合 |
| `no_target_rate` | 候補 POI 不足で留まった割合 |
| `route_fallback_rate` | roadnet 経路が使えず直線補間へ戻った割合 |
| `interaction_count_by_type` | meeting / conversation / conflict / farewell 件数 |
| `co_presence_distribution` | 同一 POI に同時滞在した人数の分布 |
| `poi_visit_entropy` | 特定 POI に偏りすぎていないか |

この指標があると、地域データを差し替えた時に「それっぽい」ではなく「前回と何が変わったか」を比較できる。

## 推奨 work order

### WO-URBAN-014 Regional Open Data Snapshot

目的: OSMnx または Overture から、指定 bbox / place name の POI・道路・建物 footprint を取得し、既存 contract へ変換する offline snapshot 生成器を作る。

許可候補 path:

- `tools/fetch_open_region_snapshot.py`
- `tests/tools/test_fetch_open_region_snapshot.py`
- `docs/subagents/work-orders/wo-urban-014-regional-open-data-snapshot.yaml`

受け入れ:

- API キーなしで実行できる経路を持つ。
- live download と committed fixture を分離する。
- 出力は既存 `pois.geojson` / `aois.geojson` / `roadnet.geojson` に変換できる。
- source / license / retrieval timestamp / bbox / query を `snapshot_manifest.json` に残す。

### WO-URBAN-015 Activity Plan Optional Input

目的: `activity_plans.jsonl` を optional 入力として追加し、ある場合は schedule-driven、ない場合は既存 rule-driven にする。

許可候補 path:

- `docs/subagents/contracts/urban-ecosystem-data-contract.md`
- `environments/urban_2d/models.py`
- `environments/urban_2d/data_loader.py`
- `environments/urban_2d/simulation.py`
- `tests/environments/test_urban_data_loader.py`
- `tests/environments/test_urban_simulation.py`

受け入れ:

- 後方互換を壊さない。
- plan の時刻矛盾・存在しない POI・重複 activity を検出する。
- 同一 seed の決定論を維持する。

### WO-URBAN-016 Simulation Metrics

目的: replay 出力から `metrics.json` を生成し、地域データや行動ルール変更の差分を比較できるようにする。

許可候補 path:

- `environments/urban_2d/simulation.py`
- `tools/urban_simulation_cli.py`
- `tests/environments/test_urban_simulation.py`
- `tests/tools/test_urban_simulation_cli.py`

受け入れ:

- `summary.json` に加えて `metrics.json` を出力する。
- route fallback / no target / arrival rate / interaction count を含む。
- metrics は replay JSONL から再計算可能で、実行時刻など非決定論値を含めない。

## 採用しない / まだ採用しないもの

- MATSim / SUMO の直接組み込み: 現行の Python 軽量 MVP に対して重い。別プロセス連携や変換器が必要になった時に再評価する。
- ActivitySim 本体の導入: activity-based modeling の設計は有用だが、現行 scope では設定・係数・校正データが過大。
- live Google Places を標準経路にする: 課金・再現性・公開協業の障壁が上がるため、明示 opt-in のまま維持する。
- LLM に状態遷移を直接決めさせる: 決定論と検証が壊れる。LLM は候補絞り込み・説明文生成に限定する。

## 参照

- MATSim: https://matsim.org/
- eqasim: https://eqasim.org/
- ActivitySim: https://github.com/ActivitySim/activitysim / https://activitysim.github.io/activitysim/
- Mesa: https://mesa.readthedocs.io/stable/overview.html
- Mesa-Geo: https://mesa-geo.readthedocs.io/
- OSMnx: https://osmnx.readthedocs.io/en/stable/getting-started.html
- SUMO: https://eclipse.dev/sumo/docs/ / https://eclipse.dev/sumo/docs/Tutorials/ScenarioGuide.html
- Overture Maps: https://docs.overturemaps.org/
- GTFS: https://gtfs.org/documentation/schedule/reference/
