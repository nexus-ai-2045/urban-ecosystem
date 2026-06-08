# MATRIXモード Recursive Repo Skill Index

status: draft
owner: nexus_ai
updated: 2026-06-08
source: docs/matrix-mode-roadmap.md

## 目的

MATRIXモードの docs を、巨大な一枚プロンプトではなく、小さく呼び出せる operating packet として扱う。main agent はこの index を入口にし、必要な packet だけを読み、allowed files、stop conditions、tests を確認してから実装する。

この index は runtime 権限を増やさない。GitHub push、public PR、Cloud Run deploy、secret、cost、外部送信は human gate のままにする。

## Dispatch Rules

- まず `docs/matrix-mode-roadmap.md` の TODO 表を確認する。
- 今回触る packet だけ読む。全 docs を常時ロードしない。
- dispatch は 1 packet / 1 task / 明示 stop を基本にする。
- 複数 packet にまたがる場合は、main agent が採否を保持し、user または maintainer gate を挟む。
- packet の `Allowed files` 以外を変更する場合は、roadmap の TODO と理由を更新する。
- `Stop conditions` に当たったら実装を止め、human-readable reason を残す。
- `Tests` のうち、該当する最小セットを実行する。広い変更では full pytest を実行する。
- protected names、protected quotes、lookalike art、voice、music を runtime、UI copy、identifier、sample data に追加しない。
- 完了時は `Changed files`、`Tests run`、`Remaining work`、`Next packet` を返す。

## Packets

| Packet ID | Name | Trigger | Primary file |
|---|---|---|---|
| MM-SAFETY | Safety and intake | 新しい influence / motif / protected work 参照を追加する時 | `docs/matrix-mode-roadmap.md` |
| MM-RUNTIME | MATRIX runtime primitive | `matrix_events.jsonl`、role、trigger、world transition、heartbeat を変える時 | `docs/subagents/contracts/urban-ecosystem-data-contract.md` |
| MM-VIEWER | Viewer surface | MATRIX panel、world layer、audio cue、viewer affordance を変える時 | `tools/urban_viewer/` |
| MM-MOTIF | Cultural motif packet | cross-world influence を original abstract packet に変換する時 | `docs/matrix-mode-motif-packets.md` |
| MM-BENCH | Turing Bench | human/AI distinction、disclosure、deception risk を扱う時 | `docs/matrix-mode-turing-bench.md` |
| MM-AUDIO | 8-bit audio cue | MATRIX event の音 cue を扱う時 | `docs/matrix-mode-audio-cues.md` |
| MM-OPS | Governance and proof | 残務ゼロ、実装完了、運用保証、PR 前確認を行う時 | `docs/matrix-mode-roadmap.md` |

## MM-SAFETY

Allowed files:

- `.github/ISSUE_TEMPLATE/matrix_mode_influence.md`
- `docs/matrix-mode-roadmap.md`
- `docs/matrix-mode-motif-packets.md`

Stop conditions:

- protected name / quote / lookalike asset を public surface へ入れそうな時。
- issue-level scope と acceptance criteria がない「全部追加する」要求。
- secret、外部送信、deploy、cost が混ざる時。

Tests:

- `rg` で protected names / protected quotes の runtime 混入を確認する。
- `git diff --check`

## MM-RUNTIME

Allowed files:

- `docs/subagents/contracts/urban-ecosystem-data-contract.md`
- `environments/urban_2d/models.py`
- `environments/urban_2d/simulation.py`
- `tools/urban_simulation_cli.py`
- `tests/environments/test_urban_simulation.py`
- `docs/generated/current-capabilities.md`

Stop conditions:

- MATRIX mode off の既存 replay が変わる時。
- RuleBasedProvider 経路の決定論が壊れる時。
- protected names / quotes を trigger、reason、sample data に入れそうな時。

Tests:

- `./.venv/bin/python -m pytest tests/environments/test_urban_simulation.py -q`
- `./.venv/bin/python tools/docs_sync_check.py --check`
- `git diff --check`

## MM-VIEWER

Allowed files:

- `tools/urban_viewer/app.js`
- `tools/urban_viewer/index.html`
- `tools/urban_viewer/styles.css`
- `tools/urban_viewer/ui_panels.js`
- `tools/urban_viewer_server.py`
- `tests/tools/test_urban_viewer_server.py`
- `docs/matrix-mode-roadmap.md`
- `docs/matrix-mode-roadmap.html`

Stop conditions:

- 外部 asset、CDN、API key、audio file、protected lookalike visual が必要になる時。
- 既存 fallback viewer の通常 replay が読めなくなる時。
- text overlap / horizontal overflow が疑われ、ブラウザ確認が policy でできない時は理由を報告する。

Tests:

- `./.venv/bin/python -m pytest tests/tools/test_urban_viewer_server.py -q`
- `./.venv/bin/python -m pytest -q`
- `git diff --check`

## MM-MOTIF

Allowed files:

- `docs/matrix-mode-motif-packets.md`
- `docs/matrix-mode-roadmap.md`
- `.github/ISSUE_TEMPLATE/matrix_mode_influence.md`

Stop conditions:

- motif packet が fan-fiction、場面コピー、character operation へ寄る時。
- minimum world-building element が書けない時。
- 採用するもの / 採用しないものを分離できない時。

Tests:

- `rg` で protected names / protected quotes の runtime 混入を確認する。
- `git diff --check`

## MM-BENCH

Allowed files:

- `docs/matrix-mode-turing-bench.md`
- `docs/matrix-mode-roadmap.md`
- `docs/matrix-mode-roadmap.html`

Stop conditions:

- real-person impersonation、hidden manipulation、consciousness proof を目的にしそうな時。
- public demo に deception optimization を入れそうな時。

Tests:

- `rg` で impersonation / protected copy の混入を確認する。
- `git diff --check`

## MM-AUDIO

Allowed files:

- `docs/matrix-mode-audio-cues.md`
- `tools/urban_viewer/app.js`
- `tools/urban_viewer/index.html`
- `tools/urban_viewer/styles.css`
- `tests/tools/test_urban_viewer_server.py`
- `docs/matrix-mode-roadmap.md`
- `docs/matrix-mode-roadmap.html`

Stop conditions:

- 音声ファイル、既存メロディ、声、効果音素材、外部生成 API が必要になる時。
- 自動再生や user gesture なしの AudioContext 開始が必要になる時。

Tests:

- `./.venv/bin/python -m pytest tests/tools/test_urban_viewer_server.py -q`
- `rg` で protected melody / voice / quote の混入を確認する。
- `git diff --check`

## MM-OPS

Allowed files:

- `docs/matrix-mode-roadmap.md`
- `docs/matrix-mode-roadmap.html`
- `docs/matrix-mode-skill-index.md`
- `tools/matrix_mode_skill_check.py`
- `tests/tools/test_matrix_mode_skill_check.py`

Stop conditions:

- GitHub push、PR 作成、deploy、secret、cost、external API を human gate なしで行いそうな時。
- 残務ゼロ / 実装完了 / 運用保証の evidence が不足している時。

Tests:

- `./.venv/bin/python tools/matrix_mode_skill_check.py --check`
- `./.venv/bin/python -m pytest tests/tools/test_matrix_mode_skill_check.py -q`
- `./.venv/bin/python -m pytest -q`
- `git diff --check`

## Drift Gate

`tools/matrix_mode_skill_check.py --check` は、少なくとも次を検査する。

- roadmap TODO の M0-M10 がすべて `完了` / `進行中` / `未着手` / `保留` のいずれか。
- M10-001 がこの skill index と drift check を証拠として参照している。
- 各 packet が `Allowed files`、`Stop conditions`、`Tests` を持つ。
- public intake surface として `.github/ISSUE_TEMPLATE/matrix_mode_influence.md` が存在する。
