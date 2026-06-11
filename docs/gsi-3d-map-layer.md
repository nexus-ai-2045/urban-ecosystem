# GSI 3D Map Layer Packet

status: draft (起草のみ / 未実装・未起票)
owner: nexus_ai
created: 2026-06-12
source: docs/matrix-mode-roadmap.md (Motif packet template) / Discord 2026-06-08「渋谷は3Dリアル路線へ舵を切る」

## Influence summary

国土地理院「3次元地図可視化サイト」(2026-06-01 試験公開) に着想を得て、API キー不要の地理院ベクトルタイルと建物 3D 表現を、fallback viewer の第 3 の map adapter として採用する。リアルの写実再現ではなく、シミュレーターとしての立体都市表現に限定する。

## Public alias

`gsi_3d_layer`

## 参照資料

- X 投稿: `https://x.com/GSI_chiriin/status/2061314177399169040` (2026-06-01)
- 可視化サイト: `https://gsi-cyberjapan.github.io/gsi-3d-2025/`
- ソースコード: `https://github.com/gsi-cyberjapan/gsi-3d-2025` (BSD-2-Clause)
- データ: 地理院タイル (最適化ベクトルタイル) / 3次元電子国土基本図 (試験公開)

## 採用するもの

- **第 3 の map adapter**: 既存の `map_adapter.js` 抽象に `gsi_3d_adapter.js` を追加する。`google_maps_adapter.js` / `fallback_map_adapter.js` と並列で、既存 2 adapter の挙動は変えない。
- **MapLibre GL JS**: API キー不要・OSS の描画ライブラリ。地理院ベクトルタイルを style 指定で読み込む。
- **建物 fill-extrusion**: ベクトルタイルの建物 footprint + 高さ属性を fill-extrusion で立体表示する。シミュレーター色を保つため、写実テクスチャは使わない。
- **出典表示**: 画面上に「出典: 国土地理院」を常時表示する (地理院タイル利用規約準拠)。
- **エージェント重畳**: 既存の replay (`agent_states.jsonl` / `poi_visit_records.jsonl`) を 3D 地図上に marker / layer として重ねる。replay の決定論は変えない。
- **opt-in 切替**: 既定は現行 fallback 地図のまま。ユーザーが 3D を選んだ時だけ adapter を切り替える (audio_cue_layer と同じ opt-in 方針)。

## 採用しないもの

- 地理院のサーバサイド機能 (住所検索ジオコーディング等) への依存。README が予告なき変更・終了を明記しているため、タイル読み込みのみに限定する。
- Google Photorealistic 3D Tiles 等の課金 API・API キー必須経路。
- 写実テクスチャ、実在店舗ロゴ、実在広告の再現。
- 現実世界の行動予測・実在人物の再現 (既存スコープ外項目を維持)。
- gsi-3d-2025 リポジトリのコード一括 vendor。参照実装として読み、必要な style / extrusion 設定だけを自作する。BSD-2 条件 (著作権表示・免責) を満たさない複製はしない。
- secret、外部送信、Cloud Run 設定変更、GitHub push の自動実行。

## Minimum world-building element

| 要素 | 内容 | Evidence |
|---|---|---|
| place and environment | 渋谷の建物ボリューム・道路・鉄道の立体表現 | gsi_3d_adapter の表示 |
| rules of possibility | タイル提供範囲・ズーム制約の中だけで描画する | adapter の zoom / bounds 設定 |
| daily life signal | 既存 replay のエージェント移動を 3D 上に重畳 | viewer E2E |
| change pressure | 試験公開データの仕様変更に adapter 差し替えで追従 | adapter 境界 (map_adapter.js) |

## Risk notes

- **試験公開リスク**: 3次元電子国土基本図・可視化サイトは試験公開。タイル URL / 仕様 / 提供範囲が予告なく変わり得る。adapter 1 ファイルに依存を閉じ込め、取得失敗時は既存 fallback 地図へ自動降格する。
- **提供範囲未確認**: 渋谷の建物 footprint は標準地図ベクトルタイルで実地確認済み (2026-06-12)。建物 3D (高さ属性) の渋谷カバー範囲は実装前に要確認 [不明]。
- **利用規約**: 地理院タイルは出典明示で利用可。大量アクセスや測量成果の複製に当たる使い方をする場合は国土地理院の利用規約・承認要否を再確認する。
- **license**: 参照実装 gsi-3d-2025 は BSD-2-Clause。コードを引用する場合は著作権表示を保持する。
- **公開境界**: この packet は docs のみ。実装 PR は human gate (public PR review 経路 M11-001) を通す。

## Testable acceptance

- `docs/gsi-3d-map-layer.md` (本ファイル) が存在し、採用するもの / 採用しないもの / risk notes が分かれている。
- `tools/urban_viewer/gsi_3d_adapter.js` が `map_adapter.js` の interface を満たす (実装フェーズ)。
- `GOOGLE_MAPS_API_KEY` なしで 3D 表示が動き、CI の API キーなし経路を壊さない。
- 3D adapter 選択時も同一 seed の replay 結果 (`agent_states.jsonl`) が byte 一致する (描画層のみの変更)。
- 画面に「出典: 国土地理院」が表示される (スクリーンショット evidence)。
- タイル取得失敗時に fallback 地図へ降格する E2E がある。
- protected name / 課金 API / サーバサイド依存が追加されていない。

## GitHub issue 起案 (未起票・human gate 待ち)

```md
title: feat proposal: GSI 3D map layer (gsi_3d_layer) as third map adapter

国土地理院の 3 次元地図可視化サイト (2026-06-01 試験公開) のデータ・方式を使い、
API キー不要の 3D 都市表示を fallback viewer の第 3 adapter として追加する提案です。

- 参照: https://github.com/gsi-cyberjapan/gsi-3d-2025 (BSD-2-Clause)
- packet: docs/gsi-3d-map-layer.md
- 採用: MapLibre GL JS + 地理院ベクトルタイル + 建物 fill-extrusion + 出典表示
- 非採用: サーバサイド機能依存 / 課金 API / 写実テクスチャ
- acceptance: API キーなし CI 維持 / replay byte 一致 / fallback 降格 E2E

まず実装前確認: 渋谷の建物 3D (高さ属性) 提供範囲。
```
