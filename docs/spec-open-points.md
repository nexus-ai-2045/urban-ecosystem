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
| 2 | status 写像で `idle` の出力先が未定義 | ✅ | spec §9.2 に写像表追加 (`idle`→`staying`)。 |
| 3 | summary.json `started_at` が再現性テストと衝突 | ✅ | contract で「再現性は 3 JSONL の byte 一致のみ対象、summary は対象外」を明記。`seed` を summary に追加。 |

## P1 — 実装の手戻りに直結 (着手前に詰めたい / 🔧 こちらで可能)

| # | 論点 | 状態 | メモ |
| --- | --- | --- | --- |
| 4 | 合成データ生成 (WO-002) の地理ロジック未定義 | 🔧 未着手 | 渋谷 bbox 固定 / POI カテゴリ分布 / home・work POI 割当 / social_networks 生成方法。第一成果物の見栄えに直結。 |
| 5 | 行動ルールの境界ケース | 🔧 未着手 | (a) 遠距離 commute が 10:00 までに終わらない場合 (b) 初日 08:00 の初期 status と最初の commute 開始 (c) `MAX_INTERACTIONS_PER_TICK=50` 超過時のペア優先順位。 |
| 6 | API レスポンス schema 未定義 | 🔧 未着手 | `/api/runs`・`/api/data/{run_id}/{file}` の返却形式、`run_id` の命名・発見方法。 |

## P2 — CEO 判断 / 保留

| # | 論点 | 状態 | 決定 |
| --- | --- | --- | --- |
| 7 | repo 構成 | ✅ | **独立 git リポジトリ化** (2026-05-29 CEO)。`git init` 未実行。 |
| 8 | デプロイ先 GCP プロジェクト | ✅ | **nexus-ai-2045 (事業用)** (2026-05-29 CEO)。spec の `<project>` を全置換済。 |
| 9 | Cloud Run 公開範囲 (未認証 / IAP) | ⏸ | デプロイ時 (Milestone 4) に確定。実装はどちらでも動く構成。 |
| 10 | 本番 Map ID 自前発行 (§16 #6) | ⏸ | 本番推奨。MVP 検証は fallback Map ID で開始可。 |
| 11 | reference/ の Groq 由来 transcript を残すか削除か | ⏸ | 低優先。現状 `docs/reference/` に歴史資料として退避済。 |
| 12 | 性能/規模の [推測] 値 (30fps / 完走時間) | ⏸ | 実測後に確定。MVP 合格ラインの数値固定は実装後。 |

## 次アクション候補

- P1 #4-6 を spec に追記して詰める (🔧 こちらで可能、必要なら壁打ち)。
- `git init` で独立リポジトリ化 (P2 #7)。
- WO-URBAN-001 Data Loader 実装着手。
