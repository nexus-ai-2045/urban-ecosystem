# MATRIXモード 8-bit Audio Cues

status: draft
owner: nexus_ai
updated: 2026-06-08
source: docs/matrix-mode-roadmap.md

## 目的

MATRIXモードのイベントを、短い 8-bit 風 cue として聞けるようにする。音楽作品、既存メロディ、声、効果音素材は使わず、ブラウザの WebAudio oscillator で生成する短い square wave だけを使う。

## Public alias

`audio_cue_layer`

## 採用するもの

- viewer footer の opt-in toggle。
- MATRIX event がある tick に入った時だけ鳴る短い cue。
- `takeover_start`、`takeover_end`、`world_transition`、`heartbeat`、`stale_report`、`human_gate` ごとの単純な周波数差。
- square wave oscillator、短い gain envelope、外部 asset なしの生成音。

## 採用しないもの

- 既存作品のメロディ、ジングル、効果音、声、音色コピー。
- protected quote を歌詞、音声、trigger、UI copy にすること。
- 自動再生。user gesture なしに AudioContext を開始しない。
- 外部音源、CDN、生成 API、課金 API、Cloud Run 連携。

## Safety / Rights Boundary

- すべての cue は runtime で合成する。音声ファイルは repo に保存しない。
- cue は通知音であり、楽曲として扱わない。
- public demo では既定 off。ユーザーが `音 on` を選んだ時だけ鳴る。
- secret、個人情報、未公開ログ、外部 API response を音に変換しない。

## Testable Acceptance

- `tools/urban_viewer/index.html` に `btn-audio-cue` がある。
- `tools/urban_viewer/app.js` に WebAudio `AudioContext` / square wave oscillator / opt-in toggle がある。
- `tools/urban_viewer/styles.css` に cue button の状態 styling がある。
- `docs/matrix-mode-roadmap.md` の M9-001 がこの design note と viewer 実装を証拠として参照する。
- protected melody、voice、lyrics、sound asset が追加されていない。
