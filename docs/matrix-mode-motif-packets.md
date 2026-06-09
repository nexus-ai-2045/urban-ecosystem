# MATRIXモード Motif Packets

status: draft
owner: nexus_ai
updated: 2026-06-08
source: docs/matrix-mode-roadmap.md

## 目的

この文書は、MATRIXモードへ追加する cross-world influence を、公開実装可能な抽象 packet に変換するための一覧である。

保護された作品名、キャラクター名、台詞、見た目、音楽、声、公式関係の示唆は runtime、UI copy、code identifier、sample data、generated asset に入れない。採用するのは、検証可能な構造、制約、governance、world-building element だけに限定する。

## Packet Status

| ID | Status | Public alias | 種別 | 証拠 |
|---|---|---|---|---|
| MP-001 | draft | `cybernetic_governance` | Cross-world Pack 1 | この文書 |

## MP-001: Cross-world Pack 1

### Influence summary

身体、ネットワーク、現場判断、指揮系統、外部監視の境界を、都市シミュレーション上の governance model として扱う。

### Public alias

`cybernetic_governance`

### 採用するもの

- body/network boundary: simulated agent の physical state と network-visible state を分ける。
- field partner role: 現場で観測し、transition や gate の根拠を補助する抽象 role。
- command role: 高リスク action を直接実行せず、human gate と review queue へ送る抽象 role。
- external observer: user / GitHub review / issue intake を第4の監視面として扱う。
- perception boundary: replay で観測できる evidence と、未観測・推測・LLM 生成を分ける。

### 採用しないもの

- 保護されたキャラクター名、組織名、台詞、見た目、音楽、声。
- 既存作品の事件、設定、都市、関係性、物語展開の再現。
- 実在人物・実在組織のなりすまし。
- secret、外部 API、GitHub push、Cloud Run deploy、production DB 操作。
- hidden manipulation、surveillance を肯定する UI copy や benchmark。

### Minimum world-building element

`cybernetic_governance` は、次の4層で構成する。

| Layer | Public role | 説明 | Evidence |
|---|---|---|---|
| Body | simulated agent | 位置、行動、状態など replay で観測できる身体側の状態。 | `agent_states.jsonl` |
| Network | MATRIX event | role、world transition、heartbeat、stale など network 側の状態。 | `matrix_events.jsonl` |
| Command | `operator_agent` / human gate | 高リスク action を止め、承認前の intent と reason だけを記録する。 | `human_gate` event |
| Observer | user / GitHub issue | 外部監視者として、方向性、公開境界、追加要求を review する。 | issue / PR / roadmap |

### Appearance in repo surfaces

| Surface | 現れるもの | M6 の範囲 |
|---|---|---|
| docs | motif packet、採用/不採用、world-building element、risk notes | 実装済み |
| contract | 将来の `MatrixEvent` field / enum 候補を検討する入口 | M6 では変更しない |
| replay | `agent_states.jsonl` と `matrix_events.jsonl` の境界として説明する | M6 では新規 event を出さない |
| viewer | body/network/command/observer の説明を将来 UI に出す候補 | M6 では UI copy を追加しない |
| tests | docs boundary、protected term absence、TODO 証拠の確認 | M6 は `rg` / diff check で検証する |

### Risk notes

- copyright/trademark: 抽象構造だけを扱い、protected name は roadmap の境界説明以外へ移さない。
- privacy: 個人情報や secret を evidence_ref、reason、issue template に入れない。
- safety: surveillance や manipulation を「便利機能」として扱わず、human gate と observer review を必須にする。
- scope: M6 は docs-only motif packet。runtime primitive、viewer UI、外部連携は別 TODO で扱う。

### Testable acceptance

- `docs/matrix-mode-motif-packets.md` に `cybernetic_governance` packet がある。
- public alias が `lower_snake_case` のオリジナル名である。
- 採用するもの / 採用しないもの / minimum world-building element / risk notes が分かれている。
- protected names、protected quotes、lookalike art、voice、music が runtime、UI copy、code identifier に追加されていない。
- `docs/matrix-mode-roadmap.md` の M6-001 がこの packet を証拠として参照する。
