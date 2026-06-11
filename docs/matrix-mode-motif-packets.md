# MATRIXモード Motif Packets

status: draft
owner: nexus_ai
updated: 2026-06-12
source: docs/matrix-mode-roadmap.md

## 目的

この文書は、MATRIXモードへ追加する cross-world influence を、公開実装可能な抽象 packet に変換するための一覧である。

保護された作品名、キャラクター名、台詞、見た目、音楽、声、公式関係の示唆は runtime、UI copy、code identifier、sample data、generated asset に入れない。採用するのは、検証可能な構造、制約、governance、world-building element だけに限定する。

## Packet Status

| ID | Status | Public alias | 種別 | 証拠 |
|---|---|---|---|---|
| MP-001 | draft | `cybernetic_governance` | Cross-world Pack 1 | この文書 |
| MP-002 | 実装済み | `exchange_pair` | Cross-world Pack 2 | この文書 / data contract v0.7.0 / test_exchange_pair_* 2 件 |
| MP-003 | 実装済み | `oath_chain` | Cross-world Pack 3 | この文書 / data contract v0.7.1 / test_oath_chain_* 2 件 |

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

## MP-002: Cross-world Pack 2

### Influence summary

「何かを得るには、同等の何かを差し出さなければならない」という等価コスト制約を、world layer transition の抽象コスト構造と agent 状態変化の不可逆イベントとして表現する。

### Public alias

`exchange_pair`

### 採用するもの

- **等価コスト制約**: world layer transition が発生するたびに、agent は `transition_cost` に相当する抽象コストを必ず負担する。コスト 0 の無償移動は許可しない (最低コスト 1)。
- **変換ペア構造**: 各 transition は「得るもの (target layer)」と「失うもの (cost payload)」の 2 要素で表現される。`MatrixEvent` optional field `exchange_cost_payload` に「消費した資源種別と量」を記録する。
- **不可逆性フラグ**: 代償を払った変換は replay で取り消せない。`exchanged=true` フラグをイベントに持たせ、逆方向 transition を発行しても元の状態には戻らない (cost が再度発生する) ことを contract で明示する。
- **replay での現れ方**: `matrix_events.jsonl` の `world_transition` イベントに `exchange_cost_payload` (string または dict) と `exchanged` (bool) を optional field として追加する。既存 run への影響なし (optional フィールドなので従来 event との後方互換を維持)。
- **contract での現れ方**: data contract v0.7.0 のオプションフィールド節に `exchange_cost_payload` と `exchanged` を追記する。

### 採用しないもの

- 保護された作品名・キャラクター名・固有の術式名・組織名・台詞・見た目・音楽・声。
- 代償として「死」「人体の喪失」などの身体損傷を直接再現する表現 (抽象コスト数値に置き換える)。
- 特定 2 人組の関係性・物語展開・因果関係の再現。
- 課金 API、外部送信、Cloud Run deploy、GitHub push、production DB 操作。
- LLM 呼び出し必須の動作 (RuleBasedProvider 経路で fallback が成立しなくなる構造)。
- 実在人物・組織のなりすまし。

### Minimum world-building element

| 要素 | 役割 | 実装場所 |
|---|---|---|
| `exchange_cost_payload` | transition で消費した資源を人間可読に記録する optional string または dict。replay で後から集計・比較できる。例: `"cost_unit:1"` | `MatrixEvent` optional field / `matrix_events.jsonl` |
| `exchanged` | この transition が等価変換として完了したことを示す optional bool。`true` の場合、逆方向の移動は元の状態を復元しない (逆 transition は別の新しい event として記録する)。 | `MatrixEvent` optional field / `matrix_events.jsonl` |
| `exchange_pair_rule` | contract 規則として「`exchanged=true` の場合は `exchange_cost_payload` が必須」制約を docs に明示する。 | `urban-ecosystem-data-contract.md` の `world_transition` Rules 節 |

### Appearance in repo surfaces

| Surface | 現れるもの | M9 の範囲 |
|---|---|---|
| docs | motif packet、採用/不採用、world-building element、risk notes | 実装済み |
| contract | `exchange_cost_payload` / `exchanged` optional field 追加、world_transition Rules 追記 | v0.7.0 で実装 |
| replay | `world_transition` event に両フィールドを optional 追加 | M9 で実装 |
| viewer | `exchange_cost_payload` を表示する候補欄 (フィールドが無ければ既存表示のまま) | 将来 TODO |
| tests | off-by-default 不変性 / 決定論 / フィールド有無の確認 | M9 で実装 |

### Risk notes

- **著作権・商標**: 採用するのは「等価交換という制約構造」という一般的な設計パターンのみ。特定作品のキャラクター名・術式名・固有名詞はコード、UI copy、trigger id、sample data のいずれにも入れない。
- **scope**: この packet は docs + data contract optional field + runtime emit の追加のみ。viewer 表示は別 TODO で扱う。
- **secret / cost**: 外部 API、Cloud Run deploy、GitHub push は対象外。ローカルテストのみ。
- **決定論**: `exchange_cost_payload` と `exchanged` は optional。既存の `matrix_events.jsonl` を出力しない run (matrix_mode=False) には影響しない。matrix_mode=True かつ `world_transition` を出力する run でのみ追加される。同一 seed・同一入力では新フィールドの有無と内容が一致することを確認する。

### Testable acceptance

- `docs/matrix-mode-motif-packets.md` に `exchange_pair` packet がある。
- public alias が `lower_snake_case` のオリジナル名である。
- 採用するもの / 採用しないもの / minimum world-building element / risk notes が分かれている。
- `docs/subagents/contracts/urban-ecosystem-data-contract.md` のバージョンが v0.7.0 に更新されている。
- `matrix_mode=False` の run では `matrix_events.jsonl` が出力されず、既存 `agent_states.jsonl` に変化がない (byte 一致)。
- `matrix_mode=True` かつ `matrix_transition_tick` 指定 run で `world_transition` event に両フィールドが含まれる。同一 seed 2 回で値が一致する (決定論)。

## MP-003: Cross-world Pack 3

### Influence summary

上位者の命令が下位の行動を拘束する階層構造と、エージェントが自らに課した誓約が能力と制約を同時に与える構造を、役割の付与 (takeover_start) イベントの抽象フィールドとして表現する。

### Public alias

`oath_chain`

### 採用するもの

- **階層ランク**: 誰が誰に命令を発行できるかを `hierarchy_rank` (integer >= 0) で表現する。値が小さいほど高い権限を持ち、命令は低い rank 番号から高い rank 番号へ向かう。エージェントは自分より低い rank の命令を拒否できない。
- **誓約と制約の双方向性**: エージェントが宣言した役割/誓約を `sworn_duty` (string) として記録する。誓約は「この role を持つ間は何ができるか」と「何をしてはいけないか」の両方を与える。
- **replay での現れ方**: `matrix_events.jsonl` の `takeover_start` イベントに `hierarchy_rank` (integer) と `sworn_duty` (string) を optional field として追加する。既存 run への影響なし (optional フィールドなので後方互換を維持)。
- **contract での現れ方**: data contract v0.7.1 の optional field 節に `hierarchy_rank` と `sworn_duty` を追記する。oath_chain の Rules として「`hierarchy_rank=0` は最上位権限」「`sworn_duty` は人間可読な宣言文」を明示する。

### 採用しないもの

- 保護された作品名・キャラクター名・組織名・固有の術語・台詞・見た目・音楽・声。
- 実在する組織や人物の命令系統の再現。
- 課金 API、外部送信、Cloud Run deploy、GitHub push、production DB 操作。
- LLM 呼び出し必須の動作。
- 死や身体損傷を直接再現する表現 (抽象的な role 制約に置き換える)。
- 実在人物・組織のなりすまし。

### Minimum world-building element

| 要素 | 役割 | 実装場所 |
|---|---|---|
| `hierarchy_rank` | 命令権限の階層を示す optional integer。0 が最上位。同一 rank が複数いる場合は協調関係を持つ。replay で後から権限チェーンを再構成できる。 | `MatrixEvent` optional field / `matrix_events.jsonl` |
| `sworn_duty` | このエージェントが宣言した役割・誓約を人間可読に記録する optional string。「何ができ、何をしてはならないか」を一言で表す。保護された名称・外部秘密・個人情報を含めない。例: `"threat_containment"` | `MatrixEvent` optional field / `matrix_events.jsonl` |
| `oath_chain_rule` | contract 規則として「`hierarchy_rank=0` は apex (最上位権限)」「`sworn_duty` は人間可読宣言」を docs に明示する。 | `urban-ecosystem-data-contract.md` の Oath Chain Rules 節 |

### Appearance in repo surfaces

| Surface | 現れるもの | M9 の範囲 |
|---|---|---|
| docs | motif packet、採用/不採用、world-building element、risk notes | 実装済み |
| contract | `hierarchy_rank` / `sworn_duty` optional field 追加、Oath Chain Rules 追記 | v0.7.1 で実装 |
| replay | `takeover_start` event に両フィールドを optional 追加 | M9 で実装 |
| viewer | `hierarchy_rank` / `sworn_duty` を表示する候補欄 (フィールドが無ければ既存表示のまま) | 将来 TODO |
| tests | off-by-default 不変性 / 決定論 / フィールド有無の確認 | M9 で実装 |

### Risk notes

- **著作権・商標**: 採用するのは「命令系統と誓約という制約構造」という一般的な設計パターンのみ。特定作品のキャラクター名・術語・固有名詞はコード、UI copy、trigger id、sample data のいずれにも入れない。
- **scope**: この packet は docs + data contract optional field + runtime emit の追加のみ。viewer 表示は別 TODO で扱う。
- **secret / cost**: 外部 API、Cloud Run deploy、GitHub push は対象外。ローカルテストのみ。
- **決定論**: `hierarchy_rank` と `sworn_duty` は optional かつ固定値。既存の `matrix_events.jsonl` を出力しない run (matrix_mode=False) には影響しない。matrix_mode=True の `takeover_start` で追加される。同一 seed・同一入力では新フィールドの有無と内容が一致することを確認する。

### Testable acceptance

- `docs/matrix-mode-motif-packets.md` に `oath_chain` packet がある。
- public alias が `lower_snake_case` のオリジナル名である。
- 採用するもの / 採用しないもの / minimum world-building element / risk notes が分かれている。
- `docs/subagents/contracts/urban-ecosystem-data-contract.md` のバージョンが v0.7.1 に更新されている。
- `matrix_mode=False` の run では `matrix_events.jsonl` が出力されず、既存 `agent_states.jsonl` に変化がない (byte 一致)。
- `matrix_mode=True` の run の `takeover_start` event に `hierarchy_rank` と `sworn_duty` が含まれる。同一 seed 2 回で値が一致する (決定論)。
