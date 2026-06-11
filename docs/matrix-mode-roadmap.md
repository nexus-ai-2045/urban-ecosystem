# MATRIXモード ロードマップ

status: implementation-ready draft
owner: nexus_ai
updated: 2026-06-11
public_boundary: 公開面の正本は GitHub docs / issues / PRs とする。

## 目的

MATRIXモードは、`urban-ecosystem` を都市リプレイビューアからクロスワールド型のエージェントシミュレーション基盤へ広げるための長期ロードマップである。

中心にある考え方は、特定作品のキャラクターや世界をコードベースへコピーすることではない。公開実装では、次のような有用な構造だけを残す。

- エージェントが実行時に役割を切り替えられる。
- 1体のエージェントが複数の world layer を橋渡しできる。
- world は小さくレビュー可能な influence packet として拡張できる。
- governance により、安全でない追加、stale、孤児化、法務リスクのある追加を抑止する。
- すべての追加を GitHub issues、docs、tests、PRs で検査可能にする。

## 現状

このロードマップは当初 docs-only として始まり、現在は M1-M10 の最小実装 slice まで進んでいる。公開 PR と human review は operation gate として別扱いにし、確認できないものは保証済みにしない。

通常モードのアプリケーション MVP は、引き続き次の範囲である。

- 渋谷ベースの都市エージェントシミュレーション
- 決定論的なサンプルデータとリプレイ
- API キーなしで動く fallback map viewer
- Cloud Run 互換の FastAPI service
- 後段で差し替え可能な optional LLM provider

MATRIXモードは、この土台の上に optional `matrix_events.jsonl`、CLI flags、viewer panel、docs packet、drift check として追加する。MATRIXモードが off の場合、既存 replay の挙動は変えない。

## 著作権・公開実装境界

公開実装名はオリジナルでなければならない。作品名、キャラクター名、引用、世界観は議論の参照元として扱えるが、product surface、prompt、code identifier、sample data、UI copy、visual design、music、generated asset としてコピーしてはならない。

| 参照元 | 公開実装 alias | 採用してよい抽象機能 |
|---|---|---|
| Agent Smith | `sentinel_mvp` | 実行時 role takeover、封じ込め圧、adversarial simulation |
| Neo | `bridge_agent` | `virtual`、`real`、`liminal` world layer 間の移動 |
| Morpheus | `guide_agent` | ルール説明、選択肢提示、transition 開始 |
| Trinity | `operator_agent` | 高信頼実行、rescue path、operator support |
| Agents group | `sentinel_swarm` | 協調 monitor、guard、escalation |
| Cybernetic special unit archetypes | `cybernetic_governance` | body/network 境界、field operator、command role |
| Alchemy sibling archetypes | `exchange_pair` | cost、transformation、equivalent exchange 実験 |
| Demon-slayer command archetypes | `oath_corps` | duty、hierarchy、threat containment |
| Psychic city destruction archetypes | `unstable_city_core` | power growth、collapse risk、reconstruction |
| Titan-wall archetypes | `walled_society` | boundary、outside knowledge、social fracture |
| Fighter roster archetypes | `duel_school` | skill tree、rival path、mastery loop |
| Dark social-tech anthology | `mirror_episode` | Turing-test と social consequence scenario |
| Notebook detective archetypes | `judgment_pair` | rule game、adversarial inference、moral ambiguity |
| Ecological valley archetypes | `spore_forest` | non-human ecology、toxic boundary、coexistence |

保護された短い台詞は trigger として保存しない。MVP では `wake_matrix`、`enter_bridge`、`assume_sentinel` のようなオリジナル trigger id を使う。

## ロードマップ概要

| Phase | Milestone | 目標 | レビュー可能な成果物 |
|---|---|---|---|
| 0 | Safety and Intake | アイデアの奔流を IP-safe な実装 backlog に変換する | この roadmap、issue template、adoption boundary |
| 1 | `sentinel_mvp` | 最初の runtime-switchable agent role | profile extension、CLI flag、tests |
| 2 | `bridge_agent` | world layer 間を移動できるエージェント | world-layer model、replay event、viewer display |
| 3 | `guide_agent` | guided transition と説明 layer | guide prompts/contracts、non-LLM fallback |
| 4 | `operator_agent` | rescue/rollback semantics を持つ高信頼 operator role | operator actions、human gate docs |
| 5 | `sentinel_swarm` | 複数の協調 monitor agents | swarm policy、heartbeat、stale reporting |
| 6 | Cross-world Pack 1 | cybernetic governance layer | network/body boundary、command model |
| 7 | Turing Bench | 人間/AI の区別と deception scenario | benchmark spec、metrics、real-person imitation なし |
| 8 | Three Worlds | `virtual`、`real`、`liminal`/hidden layers | tri-world contract、viewer affordance |
| 9 | Cultural Motif Packs | influence packet を安全に追加する | source packet format、review checklist |
| 10 | Recursive Repo Skills | repo docs を callable operating knowledge として扱う | skill index、bounded dispatch、drift check |

## Phase 詳細

### Phase 0: Safety and Intake

目標: 想像力を保ちつつ、散らかった実装や法務リスクのある実装にしない。

受け入れ条件:

- Markdown と HTML の roadmap が存在する。
- public alias が文書化されている。
- 保護された名前や引用を code identifier に使っていない。
- 「次の influence を追加する」ための bounded intake process がある。
- やらないことが明示されている。

### Phase 1: `sentinel_mvp`

目標: 既存の simulated agent を一時的に takeover できる role として、最初の MATRIXモード MVP を作る。

挙動:

- `sentinel_mvp` は既存の agent id に attach できる。
- takeover はコピーされたキャラクターではなく、state/event として表現する。
- takeover は TTL と exit reason を持つ。
- 同一 seed では replay output が決定論的に保たれる。

候補ファイル:

- `docs/subagents/contracts/urban-ecosystem-data-contract.md`
- `environments/urban_2d/models.py`
- `environments/urban_2d/simulation.py`
- `tools/urban_simulation_cli.py`
- `tests/environments/test_urban_simulation.py`

### Phase 2: `bridge_agent`

目標: Neo的な能力を、コピーではなく抽象能力として実装する。

挙動:

- 1体の agent が `virtual`、`real`、`liminal` の world layer を移動できる。
- 各 transition は trigger、source layer、target layer、cost を記録する。
- viewer は現在の world layer を表示できる。

受け入れ条件:

- world-layer enum が存在する。
- transition event を replay できる。
- MATRIXモード off の場合、default behavior は変わらない。

### Phase 3: `guide_agent`

目標: 説明と選択肢提示の layer を追加する。

挙動:

- guide は現在のルールと可能な transition を説明する。
- guide は提案できるが、高リスク action は実行しない。
- LLM output は optional とし、rule-based fallback が動く。

### Phase 4: `operator_agent`

目標: 高信頼 operator role を追加する。

挙動:

- operator action が public PR、external service、secret、cost、deployment に影響する場合は explicit human gate を要求する。
- operator は simulation state 内に rollback/rescue event を作成できる。
- public docs では simulation operation と real-world operation を区別する。

### Phase 5: `sentinel_swarm`

目標: 1体の sentinel から、複数の協調 monitor へ拡張する。

挙動:

- 複数の sentinel が異なる world layer を monitor できる。
- heartbeat が期限切れになった stale sentinel は自己申告する。
- orphan tolerance は設定可能にする。

初期しきい値:

- orphan threshold: deterministic test fixture では `0` から始め、long-running experiment のみ nonzero を許可する。
- stale threshold: heartbeat が 3 simulation tick 連続で欠落した状態。
- unresolved influence packet: review 済みになるまで draft issue のままにする。

### Phase 6: Cross-world Pack 1

目標: cybernetic governance motif をオリジナルの抽象概念として追加する。

概念:

- body/network boundary
- field partner role
- command role
- external observer

実装では特定キャラクターの再現ではなく、governance と perception boundary に焦点を当てる。

### Phase 7: Turing Bench

目標: social-tech fiction と AI evaluation から着想した human/AI distinction scenario を、場面コピーなしで設計する。

指標:

- identity ambiguity rate
- persuasion success rate
- disclosure clarity
- deception risk flag
- human-review-required count

ルール:

- real-person impersonation はしない。
- public demo に hidden manipulation benchmark を入れない。
- benchmark が consciousness を証明すると主張しない。

### Phase 8: Three Worlds

目標: 三層の world design を統合する。

最初の triad:

- `real`: grounded city replay と visible map state
- `virtual`: simulation overlay、generated scenario、rule game
- `liminal`: hidden/threshold state、memory、dreamlike transition layer

設計原則:

- すべての world は entry condition、exit condition、cost、observable evidence を持つ。

### Phase 9: Cultural Motif Packs

目標: future inspiration を許可しつつ、repo を未レビューの fan-fiction にしない。

各 motif pack は次を含む。

- 1文の influence summary
- public alias
- 採用するもの
- 採用しないもの
- minimum world-building element
- copyright risk notes
- testable acceptance criteria

最初の backlog:

- exchange and transformation
- oath hierarchy and command
- unstable city core
- walled society and outside knowledge
- duel school
- mirror episode
- judgment pair
- spore forest
- 8-bit audio cue layer
- vehicle / virtual event experience layer

### Phase 10: Recursive Repo Skills

目標: reviewability を失わずに、repo を skill collection のように振る舞わせる。

挙動:

- docs は小さく callable な operating packet を定義する。
- 各 packet は allowed files、stop conditions、tests を宣言する。
- agent dispatch は bounded に保つ。
- GitHub issues は public intake surface のままにする。
- user は external observer / fourth power として残る。

## Governance モデル

MATRIXモードは、三権モデルに external observation を加えた形で運用する。

| 権限 | Role | 責務 |
|---|---|---|
| Proposal | `guide_agent` / docs | 選択肢を説明し、candidate plan を作る |
| Execution | `operator_agent` / developer | bounded change を実装する |
| Review | `sentinel_mvp` / quality gate | drift、stale state、unsafe expansion を検出する |
| External observer | user / GitHub review | public direction と high-risk change を承認する |

## Context drop policy

MATRIXモードの要望、壁打ち、外部エージェント出力、チャット断片は、実装へ進める前に必ずこの全体ロードマップへ落とす。チャット上の勢いをそのまま実装せず、次の順序で公開可能な context に変換する。

1. 原文の意図を読む。
2. 保護された名前・台詞・見た目・音楽・声を public alias と抽象機能に変換する。
3. Motif packet template に落とす。
4. 実装TODOへ ID、Status、完了条件、証拠を追加する。
5. ClaudeCode / Grok / AGI / agy など外部 worker が触る場合も、成果物はこの roadmap、issue、PR、test のいずれかで検証可能にする。

この policy により、「よく分からないアイデア」も、reviewable な roadmap context へ変換してから実装する。

## Parallel delegation map

MATRIXモードは複数 workstream に分かれるため、main agent は orchestrator として採否、統合、Type1 / secret / cost / deployment gate を保持する。AIごとの得意領域に合わせ、ClaudeCode / Grok は並列実装 lane、AGI / agy は review / research / quality gate lane に寄せる。

| Lane | 担当候補 | Packet | 成果物 | Stop 条件 |
|---|---|---|---|---|
| Contract implementation lane | ClaudeCode | `matrix_events.jsonl` と `MatrixEvent` の contract / type / loader 整合 | data contract、型、contract tests | contract が draft のまま runtime 実装へ進みそうな時 |
| Runtime implementation lane | ClaudeCode | `sentinel_mvp` attach / TTL / `takeover_end` 生成 | simulation / CLI / deterministic tests | 既存 run の byte 再現性が壊れる時 |
| Viewer implementation lane | Grok | fallback viewer で MATRIX event を読みやすく表示 | UI、E2E、スクリーンショット | API key や外部 asset が必要になった時 |
| Parallel feature lane | Grok | `bridge_agent` / heartbeat / 8-bit cue など独立実装候補 | 小さな feature patch、tests、risk notes | write path が ClaudeCode lane と衝突する時 |
| Research lane | AGI / agy | 文化モチーフ、Turing Bench、Three Worlds の比較・要約 | motif packet、採用/不採用表、source/risk notes | 実装 patch を直接持ち始めた時 |
| Review lane | AGI / agy | 差分、テスト、docs drift、IP境界、残務ゼロ判定の二次確認 | review report、追加TODO候補 | 直接証拠がない時 |
| Governance lane | main + reviewer | 三権分立、heartbeat、stale/orphan threshold、human gate | roadmap、issue、test gate | public PR / secret / cost / deploy に触れる時 |

外部 worker への共通指示:

- 実装 lane は検索専任にしない。成果物は patch、test、docs のいずれかにする。
- review / research lane は実装を直接持たず、比較表、risk notes、review report、追加TODO候補を返す。
- 変更可能範囲、完了条件、検証コマンド、残リスクを明記する。
- 保護された固有名詞は議論参照に留め、コード識別子・UI copy・trigger に入れない。
- secret、外部送信、Cloud Run、GitHub push、public PR 作成は main / human gate なしで行わない。
- 変更後は、変更ファイル、実行した検証、未完了項目、次の推奨作業を返す。

## Guarantee gate

「残務ゼロ」「実装完了」「運用まで保証」は、以下の全項目を current evidence で確認できる場合だけ Yes とする。1つでも未確認なら No とし、次の TODO に落とす。

| 判定 | Yes 条件 | 現状 |
|---|---|---|
| 残務ゼロ？ | TODO がすべて `完了`、または `保留` に human-readable reason と再開条件がある | No (2026-06-10 実測監査: M0-M10 の証拠 file / test / contract version 0.6.0-0.6.4 は全件実在を確認。public PR は #93 として 2026-06-09 に作成・merge 済みで「PR 作成未完了」記述は解消したが、human review は 0 件のまま author self-merge。監査で見つかった残務を M11-001 / M11-002 として未着手で追加したため残務ゼロではない) |
| 実装完了してる？ | `sentinel_mvp`、`bridge_agent`、`guide_agent`、`operator_agent`、`sentinel_swarm` の contract / runtime / viewer / tests が揃い、M6-M10 の docs / UI / drift gate が完了している | Yes (2026-06-10 実測: unit/integration 602 件 pass・fail 0・skip 0 (matrix mode 関連 14 件含む)、E2E Playwright 21 件 pass を 2 回連続確認、drift gate は `matrix_mode_skill_check.py --check` と `docs_sync_check.py --check` の 2/2 が exit 0・drift 0 件、決定論 smoke は同一 seed 2 回 run で matrix on 10 file / off 9 file の sha256 byte 一致と off-by-default (matrix_events.jsonl 非生成・出力への matrix 混入ゼロ) を確認) |
| 運用まで保証された？ | issue intake、worker packet、human gate、docs drift、E2E、公開境界、rollback/stop 条件が検証済み | No (2026-06-10 実測: local checks / E2E / drift gate / 決定論はすべて pass。public PR #93 は merge 済みだが reviews 0 件で author が作成 2 分後に self-merge しており、「human review なしで public PR を行わない」の運用境界が evidence で確認できていない。human review 経路の確立は M11-001) |

No の場合の運用:

- 原因を人間語で書く。
- 対応 TODO を `進行中` または `保留` に更新する。
- 証拠となる file / command / test / screenshot を残す。
- 同じ blocker が 3 回連続するまで blocked 扱いにしない。
- 「たぶんできた」ではなく、current evidence で確認できるまで完了にしない。

## 実装TODO

この表を MATRIXモードの進捗正本とする。Status は `未着手`、`進行中`、`完了`、`保留` のいずれかだけを使う。

| ID | Status | 項目 | 完了条件 | 次の証拠 |
|---|---|---|---|---|
| M0-001 | 完了 | roadmap を Markdown / HTML で作成する | Markdown と HTML が存在し、当初 docs-only から現在の実装状態まで明記する | `docs/matrix-mode-roadmap.md` / `.html` |
| M0-002 | 完了 | TODO・進捗運用を正本化する | Status 付き TODO、更新タイミング、報告テンプレートが roadmap にある | この表と「進捗報告運用」 |
| M0-003 | 完了 | GitHub issue intake を作る | 「追加して」系の要望を issue 化する template と acceptance criteria がある | `.github/ISSUE_TEMPLATE/matrix_mode_influence.md` |
| M0-004 | 完了 | IP-safe motif packet format を定義する | 参照元、public alias、採用/不採用、世界観要素、risk、test が1 packetで書ける | 「Motif packet template」 |
| M0-005 | 完了 | 全体ロードマップへ context detail を落とす方針を明記する | チャット断片、motif、worker output を roadmap context に変換する policy がある | 「Context drop policy」 |
| M0-006 | 完了 | 並列分担 map を作る | ClaudeCode / Grok は並列実装、AGI / agy は review / research として lane、成果物、stop 条件が明記される | 「Parallel delegation map」 |
| M0-007 | 完了 | 残務ゼロ保証 gate を作る | 残務ゼロ / 実装完了 / 運用保証を Yes/No 判定できる | 「Guarantee gate」 |
| M1-001 | 完了 | `sentinel_mvp` takeover event を設計する | event 名、TTL、exit reason、determinism、off-by-default が data contract に反映される | data contract v0.6.0 / `MatrixEvent` |
| M1-002 | 完了 | `sentinel_mvp` を実装する | 既存 agent id に attach でき、同一 seed で replay が再現する | `test_matrix_mode_*` / CLI smoke |
| M1-003 | 完了 | viewer に takeover 状態を表示する | MATRIXモード off では表示変化なし、on では role/event が読める | Browser check 1280/390 / `TestViewerAppRobustLoad` |
| M2-001 | 完了 | `bridge_agent` world layer model を設計する | `real`、`virtual`、`liminal` の entry/exit/cost/evidence が定義される | data contract v0.6.1 / `WORLD_LAYER_MODEL` |
| M2-002 | 完了 | world transition event を実装する | transition が replay 可能で、既存 run を壊さない | `test_matrix_mode_emits_bridge_world_transition` / CLI test |
| M3-001 | 完了 | `guide_agent` の説明 layer を作る | rule-based fallback で現在ルールと選択肢を説明できる | data contract v0.6.2 / guide tests |
| M4-001 | 完了 | `operator_agent` の human gate 境界を作る | public PR、secret、cost、deployment へ影響する操作が gate される | data contract v0.6.3 / human gate tests |
| M5-001 | 完了 | `sentinel_swarm` heartbeat を設計・実装する | stale は 3 tick 欠落、orphan tolerance は初期 `0` として明記される | data contract v0.6.4 / swarm tests |
| M6-001 | 完了 | Cross-world Pack 1 を作る | cybernetic governance をオリジナル抽象で表現する | `docs/matrix-mode-motif-packets.md` |
| M7-001 | 完了 | Turing Bench を設計する | real-person impersonation なしで評価指標を定義する | `docs/matrix-mode-turing-bench.md` |
| M8-001 | 完了 | Three Worlds を viewer に接続する | 現在の world layer が UI で確認できる | `matrix-world` UI / viewer tests |
| M9-001 | 完了 | 8-bit audio cue layer を実装する | 生成/権利リスクなしの短い audio cue 方針がある | `docs/matrix-mode-audio-cues.md` / `btn-audio-cue` |
| M10-001 | 完了 | Recursive Repo Skills を設計する | docs が callable operating packet として読め、dispatch が bounded になる | `docs/matrix-mode-skill-index.md` / `tools/matrix_mode_skill_check.py` |
| M11-001 | 未着手 | public PR の human review 経路を確立する | 公開名義方針 (`docs/public-identity-policy.md`) に従い、以後の matrix mode 関連 PR は (a) 外部協力者の review approve、または (b) maintainer の out-of-band 人間レビュー完了を merge 前に PR comment へ記録してから merge する運用が evidence で確認できる | 次回 PR の review approve、または merge 前の「maintainer out-of-band review 済み」comment |
| M11-002 | 完了 | 手動確認の証拠を artifact 化する | M1-003 の「Browser check 1280/390」と M1-002 の「CLI smoke」に対応する検証可能な artifact (screenshot / smoke log) が repo 内または PR に存在し、第三者が現物で検証できる | `docs/evidence/m11-002-cli-smoke-2026-06-11.log` / `docs/evidence/m11-002-viewer-1280.png` / `docs/evidence/m11-002-viewer-390.png` |

## 進捗報告運用

作業開始時:

- この roadmap を読み、TODO 表を確認する。
- 今回触る TODO を `進行中` にする。
- 同時に複数 TODO を進める場合は、依存関係と stop 条件を明記する。

キリの良い単位:

- 完了した TODO は `完了` に変え、証拠を `次の証拠` に残す。
- 判断待ち、外部依存、法務/公開境界で止めるものは `保留` にする。
- 途中で設計判断が必要になった場合は、採用案と理由をこの roadmap か関連 issue に残す。

各作業セクションの終わり:

- 今回の進捗: どの TODO がどう変わったか。
- 確認できたこと: ファイル、コマンド、表示、テストなどの証拠。
- 次の予定: 次に `進行中` にする TODO と stop 条件。

コミット前:

- 変更ファイル、実装内容、検証結果、未完了 TODO、次の推奨作業を整理する。
- runtime 実装がない docs-only PR では、そのことを明記する。
- public PR、secret、cost、deployment、外部送信を含む場合は human gate を通す。

最終報告:

- 実装内容
- 変更ファイル
- 実行した検証
- 未完了項目
- 次の推奨作業

## Motif packet template

MATRIXモードに新しい influence を追加する場合は、この最小 packet に落としてから TODO または issue に載せる。

```md
## Influence summary

1文で、何に着想を得て、どの抽象機能だけを採用するかを書く。

## Public alias

`lower_snake_case` のオリジナル名。

## 採用するもの

- 実装したい抽象機能
- 最低限の世界観要素
- replay / viewer / contract のどこに現れるか

## 採用しないもの

- 保護された名前、台詞、見た目、音楽、声
- 公式関係の示唆
- 実在人物のなりすまし
- 課金 API、外部送信、Cloud Run deploy

## Risk notes

- 著作権・商標・肖像・公開範囲・secret・cost の懸念

## Testable acceptance

- docs / contract / unit test / E2E / screenshot のどれで完了を証明するか
```

## やらないこと

- 保護されたキャラクター名を code identifier にコピーしない。
- 保護された引用を trigger として保存しない。
- lookalike art、voice、music を生成しない。
- 参照作品との公式関係を示唆しない。
- real-person impersonation を実装しない。
- human review なしで public PR、deployment、secret change、costly cloud run を行わない。
- issue-level scope と acceptance criteria なしに「全部追加する」を受け入れない。

## 当初 docs-only PR 案

タイトル:

`docs: add MATRIX Mode roadmap`

ファイル:

- `docs/matrix-mode-roadmap.md`
- `docs/matrix-mode-roadmap.html`

受け入れ条件:

- roadmap が Smith > Neo > Morpheus > Trinity > Agents を alias として整理している。
- cross-world milestone が表現されている。
- copyright boundary が明示されている。
- やらないことが明示されている。
- runtime behavior change がない docs-only slice として始める。
- external call がない。
- secret がない。

## 次の実装 PR 案

タイトル:

`feat: add sentinel_mvp role takeover event`

範囲:

- オリジナルの `sentinel_mvp` role/event model を追加する。
- MATRIXモードは default off のままにする。
- deterministic tests を追加する。
- data contract と generated docs を更新する。

範囲外:

- copied name は入れない。
- protected quote は入れない。
- LLM call はしない。
- Cloud Run deploy はしない。
- public demo claim はしない。
