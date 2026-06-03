# urban-ecosystem 仕様 — 詰めるべき点の棚卸し

status: active
updated: 2026-05-29
owner: nexus_ai

改訂版 spec (`ai-ecosystem-tool-spec.md`) / data-contract / orchestration を読み込んで洗い出した「詰めるべき点」の追跡表。
凡例: ✅ 解決済 / 🔧 こちらで詰められる / 🔴 CEO 判断要 / ⏸ 保留。

## P0 — SSOT 不整合 (実装前に必須)

| # | 論点 | 状態 | 対応 |
| --- | --- | --- | --- |
| 1 | data-contract が spec に未追従 (v0.1.0 / 委譲先が空) | ✅ | data-contract を **v0.2.0** に全面改訂。§Time and Tick / §Field Types / §Enumerations / §Coordinate Systems / §Naming Conventions / §Relationship Snapshot を新設。 |
| 1a | contract に Groq 残滓 (Purpose の動画要件抽出言及) | ✅ | 削除。 |
| 1b | 例の `poi_id: "cafe_123"` が命名規約違反 | ✅ | `poi_123` に修正。 |
| 1c | category 例 `"amenity - cafe"`(スペース) vs spec `amenity-cafe` | ✅ | ハイフン形式に統一 (§Naming Conventions)。 |
| 1d | status/action/type/reason の enum 未定義 | ✅ | contract §Enumerations に固定。 |
| 1e | `relationships.jsonl` が contract File Names に無い | ✅ | 追加 (任意出力)。 |
| 1f | 座標2系統 (GeoJSON `[lon,lat]` vs flat `lat/lon`) 未明記 | ✅ | contract §Coordinate Systems に明記。 |
| 1g | API / CLI / data allowlist / runtime settings の docs drift | ✅ | `tools/docs_sync_check.py` と `docs/generated/current-capabilities.md` を追加。CI で `python tools/docs_sync_check.py --check` を実行し、実装と generated docs の不一致を PR 時点で検出する。 |
| 2 | status 写像で `idle` の出力先が未定義 | ✅ | spec §9.2 に写像表追加 (`idle`→`staying`)。 |
| 3 | summary.json `started_at` が再現性テストと衝突 | ✅ | contract で「再現性は 3 JSONL の byte 一致のみ対象、summary は対象外」を明記。`seed` を summary に追加。 |

## P1 — 実装の手戻りに直結 (着手前に詰めたい / 🔧 こちらで可能)

| # | 論点 | 状態 | メモ |
| --- | --- | --- | --- |
| 4 | 合成データ生成 (WO-002) の地理ロジック未定義 | ✅ | spec **§19** で確定。渋谷 bbox 固定 / POI 300 件カテゴリ分布 / home(75)・work(25)・school(5) POI 割当 / social_networks (Erdős-Rényi 平均次数5) / rng 消費順序固定。残だった [推測] (road 本数 ~299 / home 共有設計 / 氏名パターン / bbox 実座標) は全て `[事実: 設計決定/research]` に解決済。 |
| 5 | 行動ルールの境界ケース | ✅ | spec **§20** で確定。(a) §20.1 遠距離 commute 継続優先 (b) §20.2 初日 tick=0 初期 status (c) §20.3 MAX_INTERACTIONS_PER_TICK=50 超過時ペア優先順位 (social→距離→seeded_rand)。加えて §20.4 no_target 連続 / §20.5 滞在中の時刻帯境界跨ぎ再評価。§20 の [推測] 18 件は全て §9 由来の `[事実: 設計決定]` に解決済。 |
| 6 | API レスポンス schema 未定義 | ✅ | spec **§21** で確定。§21.1 run_id 命名・発見 / §21.2 GET /api/runs / §21.2.1 POST /api/runs / §21.2.2 GET/POST /api/settings / §21.3 GET /api/data/{run_id}/{file} (許可リスト11ファイル・JSONL raw stream・403/404) / §21.4 health / §21.6 CORS 同一オリジン。§21 の [推測] は設計決定 + FastAPI 公式 docs research で全て `[事実]` に解決済。 |

## P2 — CEO 判断 / 保留

| # | 論点 | 状態 | 決定 |
| --- | --- | --- | --- |
| 7 | repo 構成 | ✅ | **独立 git リポジトリ化** (2026-05-29 CEO)。`git init` 未実行。 |
| 8 | デプロイ先 GCP プロジェクト | ✅ | **nexus-ai-2045 (事業用)** (2026-05-29 CEO)。spec の `<project>` を全置換済。 |
| 9 | Cloud Run 公開範囲 (未認証 / IAP) | ⏸ | デプロイ時 (Milestone 4) に確定。実装はどちらでも動く構成。 |
| 10 | 本番 Map ID 自前発行 (§16 #6) | ✅ | spec §16 #6 で確定。`DEMO_MAP_ID` は本番禁止 (Google 利用規約)、Milestone 4 で Cloud Console 発行 + Secret Manager 注入。[事実: developers.google.com/maps/documentation/javascript/advanced-markers/start] |
| 11 | reference/ の Groq 由来 transcript を残すか削除か | ⏸ | 低優先。現状 `docs/reference/` に歴史資料として退避済。 |
| 12 | 性能/規模の値 (30fps / 完走時間) | 🔧 | 目標値は spec で確定 (fps 30 目標 / 完走数秒〜十数秒目安)。実測値は impl-dependent として §5.1.4 行138・§13.3.5 行790 を `[実装時確定]` に分類。実装後に実測 fps / 経過秒を記録。 |

## 次アクション候補

- P1 #4-6 は spec §19/§20/§21 に追記済 (✅)。spec 内の [推測]/[不明] は全件解決済 (設計決定 + research)。残るのは真に impl-dependent の 2 件のみ = §5.1.4 行138 (実測 fps) / §13.3.5 行790 (完走経過秒)。いずれも `[実装時確定]` タグで実装後に実測値を記録する。
- `git init` で独立リポジトリ化 (P2 #7)。
- WO-URBAN-001 Data Loader 実装着手。
