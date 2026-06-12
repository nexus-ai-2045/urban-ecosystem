# MATRIXモード Motif Packets

status: draft
owner: nexus_ai
updated: 2026-06-12

source: docs/matrix-mode-roadmap.md

## 目的

この文書は、MATRIXモードへ追加する cross-world influence を、公開実装可能な抽象 packet に変換するための一覧である。

保護された作品名、キャラクター名、台詞、見た目、音楽、声、公式関係の示唆は runtime、UI copy、code identifier、sample data、generated asset に入れない。採用するのは、検証可能な構造、制約、governance、world-building element だけに限定する。

## Packet Status

Status 語彙: `docs-only` = runtime field を持たない docs packet。`実装済み` = docs + data contract optional field + runtime emit + unit test が揃った packet。

| ID | Status | Public alias | 種別 | 証拠 |
|---|---|---|---|---|
| MP-001 | docs-only | `cybernetic_governance` | Cross-world Pack 1 | この文書 |
| MP-002 | 実装済み | `exchange_pair` | Cross-world Pack 2 | この文書 / data contract v0.7.0 / test_exchange_pair_* 2 件 |
| MP-003 | 実装済み | `oath_chain` | Cross-world Pack 3 | この文書 / data contract v0.7.1 / test_oath_chain_* 2 件 |
| MP-004 | 実装済み | `unstable_city_core` | Cross-world Pack 4 | この文書 / data contract v0.7.2 / test_unstable_city_core_* 2 件 |
| MP-005 | 実装済み | `walled_society` | Cross-world Pack 5 | この文書 / data contract v0.7.3 / test_walled_society_* 2 件 |
| MP-006 | 実装済み | `duel_school` | Cross-world Pack 6 | この文書 / data contract v0.7.4 / test_duel_school_* 2 件 |

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
| docs | motif packet、採用/不採用、world-building element、risk notes | 実装済み (docs-only) |
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

## MP-004: Cross-world Pack 4

### Influence summary

都市の中核 system が周期的に不安定化し、agent 行動に環境圧として現れる構造 (崩壊予兆 → 安定化介入のループ) を、監視系の self-report event に付与する抽象フィールドとして表現する。

### Public alias

`unstable_city_core`

### 採用するもの

- **不安定度レベル**: 都市中枢が蓄積する抽象的な不安定度を `core_instability_level` (integer >= 0) で表現する。0 = 安定基準値。値が大きいほど不安定化が進んでいることを示す。replay で推移を追跡・比較できる。
- **安定化フェーズ**: 崩壊予兆 → 安定化介入 → 回復のループを `stabilization_phase` (string) で記録する。許容値: `precursor` (不安定化の予兆。しきい値以下)、`collapse` (しきい値超過、都市中枢が不安定化)、`intervention` (安定化操作が進行中)、`recovery` (安定状態へ復帰中)、`stable` (完全安定)。
- **replay での現れ方**: `matrix_events.jsonl` の `stale_report` イベント (sentinel_swarm の heartbeat 欠落自己申告) に `core_instability_level` と `stabilization_phase` を optional field として追加する。既存 run への影響なし (optional フィールドなので後方互換を維持)。
- **contract での現れ方**: data contract v0.7.2 の optional field 節に `core_instability_level` と `stabilization_phase` を追記する。Unstable City Core Rules として語彙制約を明示する。

### 採用しないもの

- 保護された作品名・キャラクター名・組織名・台詞・見た目・音楽・声。
- 実在する都市・組織・人物の崩壊シナリオの再現。
- 課金 API、外部送信、Cloud Run deploy、GitHub push、production DB 操作。
- LLM 呼び出し必須の動作。
- 身体損傷・暴力・破壊を直接描写する表現 (抽象的な数値と状態フェーズに置き換える)。
- 実在人物・組織のなりすまし。

### Minimum world-building element

| 要素 | 役割 | 実装場所 |
|---|---|---|
| `core_instability_level` | 都市中枢の抽象的な不安定度。0 が安定基準値。`stale_report` event に付与し、replay で推移を追跡できる。保護された名称・外部秘密・個人情報を含めない。 | `MatrixEvent` optional field / `matrix_events.jsonl` |
| `stabilization_phase` | 崩壊予兆から回復までの循環フェーズを人間可読に記録する optional string。許容値: `precursor` / `collapse` / `intervention` / `recovery` / `stable`。 | `MatrixEvent` optional field / `matrix_events.jsonl` |
| `unstable_city_core_rule` | contract 規則として「`core_instability_level=0` が安定基準」「`stabilization_phase` は許容値リストから選ぶ」を docs に明示する。 | `urban-ecosystem-data-contract.md` の Unstable City Core Rules 節 |

### Appearance in repo surfaces

| Surface | 現れるもの | M9 の範囲 |
|---|---|---|
| docs | motif packet、採用/不採用、world-building element、risk notes | 実装済み |
| contract | `core_instability_level` / `stabilization_phase` optional field 追加、Unstable City Core Rules 追記 | v0.7.2 で実装 |
| replay | `stale_report` event に両フィールドを optional 追加 | M9 で実装 |
| viewer | `core_instability_level` / `stabilization_phase` を表示する候補欄 (フィールドが無ければ既存表示のまま) | 将来 TODO |
| tests | off-by-default 不変性 / 決定論 / フィールド有無の確認 | M9 で実装 |

### Risk notes

- **著作権・商標**: 採用するのは「周期的な都市中枢不安定化という抽象状態機械」という一般的な設計パターンのみ。特定作品のキャラクター名・固有名詞はコード、UI copy、trigger id、sample data のいずれにも入れない。
- **scope**: この packet は docs + data contract optional field + runtime emit の追加のみ。viewer 表示は別 TODO で扱う。
- **secret / cost**: 外部 API、Cloud Run deploy、GitHub push は対象外。ローカルテストのみ。
- **決定論**: `core_instability_level` と `stabilization_phase` は optional かつ固定値。既存の `matrix_events.jsonl` を出力しない run (matrix_mode=False) には影響しない。matrix_mode=True かつ `matrix_swarm_stale_tick` 指定 run の `stale_report` で追加される。同一 seed・同一入力では新フィールドの有無と内容が一致することを確認する。

### Testable acceptance

- `docs/matrix-mode-motif-packets.md` に `unstable_city_core` packet がある。
- public alias が `lower_snake_case` のオリジナル名である。
- 採用するもの / 採用しないもの / minimum world-building element / risk notes が分かれている。
- `docs/subagents/contracts/urban-ecosystem-data-contract.md` のバージョンが v0.7.2 に更新されている。
- `matrix_mode=False` の run では `matrix_events.jsonl` が出力されず、既存 `agent_states.jsonl` に変化がない (byte 一致)。
- `matrix_mode=True` かつ `matrix_swarm_stale_tick` 指定 run の `stale_report` event に `core_instability_level` と `stabilization_phase` が含まれる。同一 seed 2 回で値が一致する (決定論)。

## MP-005: Cross-world Pack 5

### Influence summary

境界の内側で完結した social system と、外部からの知識流入が境界認識を変える構造を、boundary の透過性と外部知識の蓄積レベルを guide_agent heartbeat に付与する抽象フィールドとして表現する。

### Public alias

`walled_society`

### 採用するもの

- **境界透過性**: 社会システムの境界がどれほど外部情報を通すかを `boundary_permeability` (integer >= 0) で表現する。0 = 完全封鎖 (境界は固く、外部知識が入らない)。値が大きいほど境界が透過的で外部との情報交換が起きやすい。replay で境界状態の推移を追跡・比較できる。
- **外部知識蓄積レベル**: 境界の外から流入し蓄積した知識の度合いを `outside_knowledge_level` (integer >= 0) で表現する。0 = 外部知識が流入していない状態。値が大きいほど外部知識が境界認識に影響していることを示す。
- **replay での現れ方**: `matrix_events.jsonl` の `guide_agent` が発行する `heartbeat` イベントに `boundary_permeability` と `outside_knowledge_level` を optional field として追加する。guide_agent は layer 間の移動候補 (何が境界の外にあるか) を説明するため、境界透過性と外部知識レベルの記録に適している。既存 run への影響なし (optional フィールドなので後方互換を維持)。
- **contract での現れ方**: data contract v0.7.3 の optional field 節に `boundary_permeability` と `outside_knowledge_level` を追記する。Walled Society Rules として語彙制約と禁止事項を明示する。

### 採用しないもの

- 保護された作品名・キャラクター名・組織名・台詞・見た目・音楽・声。
- 実在する国・地域・政治体制の壁や検閲制度の再現。
- 課金 API、外部送信、Cloud Run deploy、GitHub push、production DB 操作。
- LLM 呼び出し必須の動作。
- 暴力・弾圧・身体損傷を直接描写する表現 (抽象的な数値と境界状態に置き換える)。
- 実在人物・組織のなりすまし。

### Minimum world-building element

| 要素 | 役割 | 実装場所 |
|---|---|---|
| `boundary_permeability` | 境界の透過性を示す optional integer。0 = 完全封鎖。大きいほど透過的で外部知識が流入しやすい。`guide_agent` heartbeat event に付与し、replay で境界推移を追跡できる。保護された名称・外部秘密・個人情報を含めない。 | `MatrixEvent` optional field / `matrix_events.jsonl` |
| `outside_knowledge_level` | 外部から流入した知識の蓄積レベルを示す optional integer。0 = 外部知識なし。大きいほど境界内の社会が外部知識に影響されていることを示す。`guide_agent` heartbeat event に付与する。保護された名称・外部秘密・個人情報を含めない。 | `MatrixEvent` optional field / `matrix_events.jsonl` |
| `walled_society_rule` | contract 規則として「`boundary_permeability=0` は完全封鎖」「`outside_knowledge_level=0` は外部知識なし」を docs に明示する。 | `urban-ecosystem-data-contract.md` の Walled Society Rules 節 |

### Appearance in repo surfaces

| Surface | 現れるもの | M9 の範囲 |
|---|---|---|
| docs | motif packet、採用/不採用、world-building element、risk notes | 実装済み |
| contract | `boundary_permeability` / `outside_knowledge_level` optional field 追加、Walled Society Rules 追記 | v0.7.3 で実装 |
| replay | `guide_agent` heartbeat event に両フィールドを optional 追加 | M9 で実装 |
| viewer | `boundary_permeability` / `outside_knowledge_level` を表示する候補欄 (フィールドが無ければ既存表示のまま) | 将来 TODO |
| tests | off-by-default 不変性 / 決定論 / フィールド有無の確認 | M9 で実装 |

### Risk notes

- **著作権・商標**: 採用するのは「境界による社会封鎖と外部知識流入という抽象状態機械」という一般的な設計パターンのみ。特定作品のキャラクター名・固有名詞はコード、UI copy、trigger id、sample data のいずれにも入れない。
- **scope**: この packet は docs + data contract optional field + runtime emit の追加のみ。viewer 表示は別 TODO で扱う。
- **secret / cost**: 外部 API、Cloud Run deploy、GitHub push は対象外。ローカルテストのみ。
- **決定論**: `boundary_permeability` と `outside_knowledge_level` は optional かつ固定値。既存の `matrix_events.jsonl` を出力しない run (matrix_mode=False) には影響しない。matrix_mode=True かつ `matrix_guide_tick` 指定 run の `guide_agent` heartbeat で追加される。同一 seed・同一入力では新フィールドの有無と内容が一致することを確認する。

### Testable acceptance

- `docs/matrix-mode-motif-packets.md` に `walled_society` packet がある。
- public alias が `lower_snake_case` のオリジナル名である。
- 採用するもの / 採用しないもの / minimum world-building element / risk notes が分かれている。
- `docs/subagents/contracts/urban-ecosystem-data-contract.md` のバージョンが v0.7.3 に更新されている。
- `matrix_mode=False` の run では `matrix_events.jsonl` が出力されず、既存 `agent_states.jsonl` に変化がない (byte 一致)。
- `matrix_mode=True` かつ `matrix_guide_tick` 指定 run の `guide_agent` heartbeat event に `boundary_permeability` と `outside_knowledge_level` が含まれる。同一 seed 2 回で値が一致する (決定論)。

## MP-006: Cross-world Pack 6

### Influence summary

1 対 1 の構造化された competitive interaction において、流派 (school) ごとの engagement style と、勝敗の累積が rank / 評判として replay 可能な記録に反映される構造を、`takeover_start` イベントの抽象フィールドとして表現する。

### Public alias

`duel_school`

### 採用するもの

- **1 対 1 structured engagement**: takeover イベントは 1 体の agent が別の agent に対して構造化された挑戦を行う場面を表す。決闘は本質的に 1 対 1 の engagement であるため、`takeover_start` はこの構造と概念整合が高い。TTL (ttl_ticks) は決闘の持続期間として読める。
- **engagement style (流派)**: どの school / style でこの決闘が行われたかを `duel_style` (string) として記録する。例: `"aggressive"`, `"defensive"`, `"technical"`, `"adaptive"`。保護された固有の流派名は使わず、行動特性を抽象的に表現する。
- **rank / 評判の記録**: 決闘参加時点の competitive rank を `duel_rank` (integer >= 0) として記録する。0 = 未ランク / 初期値。値が大きいほど高い地位を示す。replay で複数の takeover_start event を比較することで、rank 推移を追跡できる。
- **replay での現れ方**: `matrix_events.jsonl` の `takeover_start` イベントに `duel_style` (string) と `duel_rank` (integer >= 0) を optional field として追加する。既存 run への影響なし (optional フィールドなので後方互換を維持)。
- **contract での現れ方**: data contract v0.7.4 の optional field 節に `duel_style` と `duel_rank` を追記する。Duel School Rules として語彙制約と禁止事項を明示する。

### 設計メモ: host event 選定理由

`takeover_start` を選んだ根拠:

| 候補 | 評価 |
|---|---|
| `takeover_start` | 1 体が別の 1 体に挑む構造 (1 対 1) / TTL が決闘持続期間に対応 / 既存 `hierarchy_rank` と rank 概念が整合 / `sentinel_mvp` のrole takeover = 競争的 engagement のモデルとして最適 |
| `human_gate` | 人間の明示承認が必要なゲート専用。競争インタラクションには不適合。`duel_rank` や `duel_style` を保持する意味が薄い |
| `world_transition` | layer 間移動専用 (`bridge_agent`)。決闘は layer 移動ではなく同 layer 内の対戦 |
| `stale_report` | 欠落した heartbeat の自己申告専用 (`sentinel_swarm`)。競争的 engagement とは無関係 |
| `heartbeat` | 生存確認専用。決闘 start イベントとして不適切 |

`takeover_start` は最も概念整合が高い host event である。

### 採用しないもの

- 保護された作品名・キャラクター名・流派名・組織名・台詞・見た目・音楽・声。
- 実在する武道流派・格闘技団体・競技者の名称・エピソードの再現。
- 課金 API、外部送信、Cloud Run deploy、GitHub push、production DB 操作。
- LLM 呼び出し必須の動作。
- 暴力・身体損傷を直接描写する表現 (抽象的な style 文字列と integer rank に置き換える)。
- 実在人物・組織のなりすまし。

### Minimum world-building element

| 要素 | 役割 | 実装場所 |
|---|---|---|
| `duel_style` | この決闘 engagement で使用する抽象的な school / style を人間可読に記録する optional string。例: `"aggressive"` / `"defensive"` / `"technical"` / `"adaptive"`。保護された流派名・外部秘密・個人情報を含めない。`takeover_start` で使用する。 | `MatrixEvent` optional field / `matrix_events.jsonl` |
| `duel_rank` | 決闘参加時点の competitive rank / 評判を示す optional integer。0 = 未ランク / 初期値。値が大きいほど高い地位を示す。replay で複数 event を比較して rank 推移を追跡できる。保護された名称・外部秘密・個人情報を含めない。`takeover_start` で使用する。 | `MatrixEvent` optional field / `matrix_events.jsonl` |
| `duel_school_rule` | contract 規則として「`duel_rank=0` は未ランク基準」「`duel_style` は人間可読な抽象 style 文字列」を docs に明示する。 | `urban-ecosystem-data-contract.md` の Duel School Rules 節 |

### Appearance in repo surfaces

| Surface | 現れるもの | M9 の範囲 |
|---|---|---|
| docs | motif packet、採用/不採用、world-building element、risk notes | 実装済み |
| contract | `duel_style` / `duel_rank` optional field 追加、Duel School Rules 追記 | v0.7.4 で実装 |
| replay | `takeover_start` event に両フィールドを optional 追加 | M9 で実装 |
| viewer | `duel_style` / `duel_rank` を表示する候補欄 (フィールドが無ければ既存表示のまま) | 将来 TODO |
| tests | off-by-default 不変性 / 決定論 / フィールド有無の確認 | M9 で実装 |

### Risk notes

- **著作権・商標**: 採用するのは「流派ごとの engagement style と competitive rank という抽象状態機械」という一般的な設計パターンのみ。特定作品のキャラクター名・流派名・固有名詞はコード、UI copy、trigger id、sample data のいずれにも入れない。
- **scope**: この packet は docs + data contract optional field + runtime emit の追加のみ。viewer 表示は別 TODO で扱う。
- **secret / cost**: 外部 API、Cloud Run deploy、GitHub push は対象外。ローカルテストのみ。
- **決定論**: `duel_style` と `duel_rank` は optional かつ固定値。既存の `matrix_events.jsonl` を出力しない run (matrix_mode=False) には影響しない。matrix_mode=True の `takeover_start` で追加される。同一 seed・同一入力では新フィールドの有無と内容が一致することを確認する。

### Testable acceptance

- `docs/matrix-mode-motif-packets.md` に `duel_school` packet がある。
- public alias が `lower_snake_case` のオリジナル名である。
- 採用するもの / 採用しないもの / minimum world-building element / risk notes が分かれている。
- `docs/subagents/contracts/urban-ecosystem-data-contract.md` のバージョンが v0.7.4 に更新されている。
- `matrix_mode=False` の run では `matrix_events.jsonl` が出力されず、既存 `agent_states.jsonl` に変化がない (byte 一致)。
- `matrix_mode=True` の run の `takeover_start` event に `duel_style` と `duel_rank` が含まれる。同一 seed 2 回で値が一致する (決定論)。
