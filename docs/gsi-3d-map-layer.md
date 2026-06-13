# GSI 3D Map Layer Packet

status: draft (起草のみ / 未実装・未起票)
owner: nexus_ai
created: 2026-06-12
source: public GSI references / internal discussion abstraction

## Influence Summary

国土地理院の 3 次元地図可視化サイトに着想を得て、API キー不要の地理院ベクトルタイルと建物 3D 表現を、fallback viewer の第 3 の map adapter として採用する案です。リアルの写実再現ではなく、シミュレーターとしての立体都市表現に限定します。

## Public Alias

`gsi_3d_layer`

## 参照資料

- 可視化サイト: `https://gsi-cyberjapan.github.io/gsi-3d-2025/`
- ソースコード: `https://github.com/gsi-cyberjapan/gsi-3d-2025` (BSD-2-Clause)
- データ: 地理院タイル (最適化ベクトルタイル) / 3次元電子国土基本図 (試験公開)

## 採用するもの

- **第 3 の map adapter**: 既存の `map_adapter.js` 抽象に `gsi_3d_adapter.js` を追加する。`google_maps_adapter.js` / `fallback_map_adapter.js` と並列に置き、既存 2 adapter の挙動は変えない。
- **MapLibre GL JS**: API キー不要・OSS の描画ライブラリ。地理院ベクトルタイルを style 指定で読み込む。
- **建物 fill-extrusion**: ベクトルタイルの建物 footprint と高さ属性を fill-extrusion で立体表示する。シミュレーター色を保つため、写実テクスチャは使わない。
- **出典表示**: 画面上に「出典: 国土地理院」を常時表示する。
- **エージェント重畳**: 既存 replay (`agent_states.jsonl` / `poi_visit_records.jsonl`) を 3D 地図上に marker / layer として重ねる。replay の決定論は変えない。
- **opt-in 切替**: 既定は現行 fallback 地図のまま。ユーザーが 3D を選んだ時だけ adapter を切り替える。

## 採用しないもの

- 地理院のサーバサイド機能への依存。タイル読み込みと描画に限定する。
- Google Photorealistic 3D Tiles などの課金 API・API キー必須経路。
- 写実テクスチャ、実在店舗ロゴ、実在広告の再現。
- 現実世界の行動予測・実在人物の再現。
- 参照リポジトリのコード一括 vendor。必要な style / extrusion 設定だけを自作し、BSD-2-Clause の表示条件を守る。
- secret、外部送信、Cloud Run 設定変更、GitHub push の自動実行。

## Minimum World-Building Element

| 要素 | 内容 | Evidence |
|---|---|---|
| place and environment | 都市の建物ボリューム・道路・鉄道の立体表現 | `gsi_3d_adapter` の表示 |
| rules of possibility | タイル提供範囲・ズーム制約の中だけで描画する | adapter の zoom / bounds 設定 |
| daily life signal | 既存 replay のエージェント移動を 3D 上に重畳 | viewer E2E |
| change pressure | 試験公開データの仕様変更に adapter 差し替えで追従 | adapter 境界 (`map_adapter.js`) |

## Risk Notes

- **試験公開リスク**: 3 次元電子国土基本図・可視化サイトは試験公開のため、タイル URL / 仕様 / 提供範囲が変わり得る。adapter 1 ファイルに依存を閉じ込め、取得失敗時は既存 fallback 地図へ降格する。
- **提供範囲未確認**: 対象エリアの建物 3D 高さ属性カバー範囲は実装前に確認する。
- **利用規約**: 出典表示、大量アクセス、測量成果の複製に当たる使い方は実装 PR 前に再確認する。
- **license**: 参照実装は BSD-2-Clause。コードを引用する場合は著作権表示を保持する。
- **公開境界**: この packet は docs のみ。実装 PR は human gate を通す。

## Testable Acceptance

- `docs/gsi-3d-map-layer.md` が存在し、採用するもの / 採用しないもの / risk notes が分かれている。
- `tools/urban_viewer/gsi_3d_adapter.js` が `map_adapter.js` の interface を満たす (実装フェーズ)。
- `GOOGLE_MAPS_API_KEY` なしで 3D 表示が動き、CI の API キーなし経路を壊さない。
- 3D adapter 選択時も同一 seed の replay 結果 (`agent_states.jsonl`) が byte 一致する。
- 画面に「出典: 国土地理院」が表示される。
- タイル取得失敗時に fallback 地図へ降格する E2E がある。
- protected name / 課金 API / サーバサイド依存が追加されていない。

## GitHub Issue 起案 (未起票・human gate 待ち)

```md
title: feat proposal: GSI 3D map layer (gsi_3d_layer) as third map adapter

API キー不要の 3D 都市表示を fallback viewer の第 3 adapter として追加する提案です。

- 参照: https://github.com/gsi-cyberjapan/gsi-3d-2025 (BSD-2-Clause)
- packet: docs/gsi-3d-map-layer.md
- 採用: MapLibre GL JS + 地理院ベクトルタイル + 建物 fill-extrusion + 出典表示
- 非採用: サーバサイド機能依存 / 課金 API / 写実テクスチャ
- acceptance: API キーなし CI 維持 / replay byte 一致 / fallback 降格 E2E

まず実装前確認: 対象エリアの建物 3D 高さ属性提供範囲。
```
