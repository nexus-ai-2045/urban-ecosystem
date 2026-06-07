# Cross-world Operator Mode Linear起票案

- Status: `draft`
- Version: `0.1.2`
- Owner: `manager`
- Updated: `2026-06-08`
- Roadmap: [cross-world-operator-roadmap.md](cross-world-operator-roadmap.md)
- TODO正本: [cross-world-operator-todo.md](cross-world-operator-todo.md)

## 目的

この文書は、Cross-world Operator Mode の未実装TODOを、Linearに起票しやすいMVP単位へ束ねるための公開正本です。

Linear本体へのissue作成は external write action です。この文書は起票案だけを保持し、人間レビュー後にだけLinearへ反映します。

## 起票ルール

- すべての `XWORLD-TODO-001` から `XWORLD-TODO-039` は、少なくとも1つのMVP draftに含める。
- 各MVP draftは、目的、対象TODO、成果物、受け入れ条件、gate、次に進む条件を持つ。
- 日本語を正本言語にする。英語は、公開安全なID、既存コード識別子、短いtechnical labelに限って使う。
- public docsには、作品名・キャラクター名・私的path・外部投稿本文をimplementation IDとして出さない。
- Linear issue、GitHub issue、Discord投稿、cloud/API実行は、人間レビュー前に行わない。
- MVPが実装可能でない場合は、`watch` または `parking-lot` の理由を明記して残す。

## Versioning

Cross-world Operator Mode のdocs package versionは、意味単位で自動更新します。

- `MAJOR`: public data contract、主要API、operator state modelに破壊的変更がある時。
- `MINOR`: 新しいMVP、world layer、archetype set、governance modelを追加する時。
- `PATCH`: docs正本、work order、MVP実装前仕様、review handoffを追加・整理する時。

現在の `0.1.2` は、MVP-002 World Bridge State Model の実装前仕様を追加したPATCH更新です。Urban Ecosystem data contract はこのPRでは変更しません。

## 日本語優先保証

Linear draft、PR本文、review handoff、進捗メモは日本語を基本にします。

許容する英語:

- `XWORLD-TODO-001` のような既存ID。
- `Gate`, `Acceptance`, `Status`, `MVP` のような短い運用label。
- public-safe nameとしてすでに定義済みの抽象名。
- コマンド、ファイル名、コード識別子。

禁止する運用:

- 日本語で説明できる本文を英語だけで書くこと。
- PR本文やLinear draftを英語templateのまま出すこと。
- 英語化によって、contextで出た論点のニュアンスやgateが落ちること。

## MVP順

1. `UE-XWORLD-MVP-000 Context Coverage Backbone`
2. `UE-XWORLD-MVP-001 Sentinel Operator Entry`
3. `UE-XWORLD-MVP-002 World Bridge State Model`
4. `UE-XWORLD-MVP-003 Guide And Agent Roster`
5. `UE-XWORLD-MVP-004 Motif Arc Pack`
6. `UE-XWORLD-MVP-005 Assessment And Benchmark Lab`
7. `UE-XWORLD-MVP-006 Governance And Fractal Decision`
8. `UE-XWORLD-MVP-007 Repo-as-Skill And Distributed Ops`
9. `UE-XWORLD-MVP-008 Intake Lifecycle And Worldbuilding Pipeline`

## Linear Drafts

### UE-XWORLD-MVP-000 Context Coverage Backbone

- Type: `MVP`
- Source TODO IDs: coverage guarantee, TODO正本, public-safe naming, HTML preview
- Deliverable: docs
- Status: `drafted`
- Goal: 以後のcontext ideaを落とさない運用基盤を維持する。
- Acceptance:
  - roadmap由来のideaが `accepted` / `parking-lot` / `watch` / `rejected/out-of-scope` に分類されている。
  - accepted ideaはTODO IDを持つ。
  - public-safe naming、private path exclusion、external post body exclusionが明記されている。
  - HTML previewでcoverageとTODOを読める。
- Gate: docs-only human review
- Next condition: MVP-001以降の実装work orderを切る前に、この文書とTODO正本を更新する。
- Not doing:
  - Linear issue作成、GitHub issue作成、Discord投稿、cloud/API実行。
  - 作品名・キャラクター名・私的path・外部投稿本文の公開ID化。

### UE-XWORLD-MVP-001 Sentinel Operator Entry

- Type: `MVP`
- Source TODO IDs: `XWORLD-TODO-001`, `XWORLD-TODO-002`, `XWORLD-TODO-039`
- Deliverable: prototype work order
- Status: `drafted`
- Goal: operatorがagent viewpointへ入り、通常replayへ戻る最小モードを定義する。
- Acceptance:
  - agent selection、entry、returnの3点をtoy scenarioで説明できる。
  - 起動語句や外部作品由来phraseをpublic codeにhard-codeしない。
  - implementation work orderにsource category、gate、rollback pathがある。
  - failure stateとして、entry拒否、return失敗、ambiguous targetを扱う。
- Gate: public-safe trigger review
- Next condition: operator entryのtoy prototypeがdocs上で説明可能になったら、MVP-002へ進む。
- Draft artifact: [cross-world-operator-mvp-001-sentinel-entry.md](cross-world-operator-mvp-001-sentinel-entry.md)
- Work order: [wo-urban-020-cross-world-sentinel-entry.yaml](subagents/work-orders/wo-urban-020-cross-world-sentinel-entry.yaml)
- Not doing:
  - protected phraseの実装ID化。
  - real-person identityやcopyrighted character identityの再現。

### UE-XWORLD-MVP-002 World Bridge State Model

- Type: `MVP`
- Source TODO IDs: `XWORLD-TODO-003`, `XWORLD-TODO-017`, `XWORLD-TODO-018`, `XWORLD-TODO-036`
- Deliverable: model/design work order
- Status: `drafted`
- Goal: `physical`, `simulated`, `liminal` の三層worldとMinimum World Packetを定義する。
- Acceptance:
  - 3層worldの状態定義、移動条件、失敗状態がある。
  - Event + Music Layerはworld layerの体験信号として扱い、8-bit WebAudio cueは後続prototype候補に留める。
  - Minimum World Packetの7項目を満たさない実装TODOは `watch` または `parking-lot` に置く。
  - data contract変更が必要な場合は、別PRとして明記する。
  - replay explanationでworld layerの違いを説明できる。
- Gate: data contract review
- Next condition: world layerとMinimum World Packetがoperator entryに接続できたら、MVP-003へ進む。
- Draft artifact: [cross-world-operator-mvp-002-world-bridge.md](cross-world-operator-mvp-002-world-bridge.md)
- Work order: [wo-urban-021-cross-world-bridge-state-model.yaml](subagents/work-orders/wo-urban-021-cross-world-bridge-state-model.yaml)
- Not doing:
  - このMVP内でdata contractを変更すること。
  - world設定だけでactor / pressure / ruleを欠いた実装着手。

### UE-XWORLD-MVP-003 Guide And Agent Roster

- Type: `MVP`
- Source TODO IDs: `XWORLD-TODO-004`, `XWORLD-TODO-005`, `XWORLD-TODO-006`
- Deliverable: archetype design work order
- Status: `not_started`
- Goal: guide / partner / monitoring / intervention roleを抽象archetypeとして整理する。
- Acceptance:
  - guide、partner、monitoring、pursuit、intervention、field-support、supervisor roleを抽象名で定義する。
  - operator controlとcompanion guidanceの責任範囲を分ける。
  - copyrighted names、real-person identity、protected role labelsを使わない。
  - toy replayで各roleが何を説明・観測・制御するか示せる。
- Gate: public-safe naming review
- Next condition: operator entryとworld bridgeに対する案内・監視roleが定義できたら、MVP-004へ進む。
- Not doing:
  - 外部作品の人物構造をそのままroster化すること。
  - exploit-like procedureやdangerous operational instruction。

### UE-XWORLD-MVP-004 Motif Arc Pack

- Type: `MVP`
- Source TODO IDs: `XWORLD-TODO-007`, `XWORLD-TODO-008`, `XWORLD-TODO-009`, `XWORLD-TODO-010`, `XWORLD-TODO-011`, `XWORLD-TODO-012`, `XWORLD-TODO-013`, `XWORLD-TODO-014`, `XWORLD-TODO-015`, `XWORLD-TODO-019`
- Deliverable: docs
- Status: `not_started`
- Goal: 追加motifをworld / behavior patternとして受け入れる。
- Acceptance:
  - Equivalent Exchange Pair、Pillar Council Arc、Unstable Power Arc、Boundary War Arc、Fighter Archetype Set、Social-Tech Mirror Lab、Judgment Game Arc、Ecological Mediation Arc、Pilot Sync Arcをpublic-safe名で保持する。
  - 新規motifはArchetype guaranteeとWorld guaranteeを両方満たす。
  - 人物だけの追加は不可と明記する。
  - `Next Motif Expansion Slot` がTODO IDまたは `watch` / `parking-lot` 分類を必ず付ける。
- Gate: public-safe naming gate
- Next condition: motif arcがMinimum World Packetに接続できたら、MVP-005へ進む。
- Not doing:
  - 作品名・キャラクター名をimplementation IDにすること。
  - narrative detailやquoted lineの再現。

### UE-XWORLD-MVP-005 Assessment And Benchmark Lab

- Type: `MVP`
- Source TODO IDs: `XWORLD-TODO-016`, `XWORLD-TODO-020`, `XWORLD-TODO-021`, `XWORLD-TODO-022`, `XWORLD-TODO-023`, `XWORLD-TODO-028`
- Deliverable: benchmark design work order
- Status: `not_started`
- Goal: Human/AI assessment、post-singularity境界、chaotic benchmark、frontier capability、scale benchmark、agent harnessを評価枠にする。
- Acceptance:
  - Human/AI Assessment Labはdeceptionではなくhuman-likeness、intention inference、boundary recognitionを扱う。
  - Post-Singularity Scenario Boundaryは予測ではなくbounded scenario familyとして扱う。
  - Chaotic Three-Body World Benchmarkは数学/物理の抽象benchmarkとして扱う。
  - Frontier AI Capability Layer Benchmarkはlab/model rankingやprivate capability claimを避ける。
  - Scale-Simplification Simulation Benchmarkは外部post本文を引用せず、source abstractionだけを使う。
  - Agent Harness Layer Benchmarkはmodel capabilityとproduct harness qualityを分ける。
- Gate: ethics/safety review
- Next condition: benchmarkの入力・出力・不合格条件がdocsで説明できたら、MVP-006へ進む。
- Not doing:
  - deceptionやdangerous live test。
  - private capability claim、外部post本文引用、危険手順の公開。

### UE-XWORLD-MVP-006 Governance And Fractal Decision

- Type: `MVP`
- Source TODO IDs: `XWORLD-TODO-024`, `XWORLD-TODO-025`, `XWORLD-TODO-026`, `XWORLD-TODO-027`, `XWORLD-TODO-029`, `XWORLD-TODO-030`
- Deliverable: governance work order
- Status: `not_started`
- Goal: FDE、三権分立、user oversight、three AI branches + meta-userの意思決定構造を定義する。
- Acceptance:
  - Future-Known Implementation Frameはprophecyではなく、old future image、current local capacity、implementation gapの比較にする。
  - Human Time-Sense Boundary Benchmarkはwait value、progress、stuck state、next return pointを扱う。
  - Numeric Operating Protocolは実装根拠が成熟するまで `parking-lot` を維持する。
  - FDE Packet Router Benchmarkは `entry -> packet -> evidence -> decision -> closure` を使う。
  - User Oversight Fourth-Power Layerではuserをagentではなくexternal monitorとして扱う。
  - Deliberative Separation-of-Powers Layerではproposal / review / execution / oversightを分ける。
- Gate: governance review
- Next condition: decision packetとoversight boundaryがdocsで説明できたら、MVP-007へ進む。
- Not doing:
  - userを自動agentとして扱うこと。
  - human approvalを省略するclosed-loop automation。

### UE-XWORLD-MVP-007 Repo-as-Skill And Distributed Ops

- Type: `MVP`
- Source TODO IDs: `XWORLD-TODO-031`, `XWORLD-TODO-032`, `XWORLD-TODO-033`
- Deliverable: spike work order
- Status: `watch`
- Goal: repo-as-skill、recursive skill call、P2P spike、cloud capacity envelopeを安全に検討する。
- Acceptance:
  - Repository-as-Skill Meshにはmaximum traversal depthとloop guardがある。
  - P2P Distributed Operations Spikeはidentity、trust、moderationが未定義なら実装しない。
  - Cloud Capacity Envelopeはaccount、cost、quota、billing、region、rollbackを明記するまで実行しない。
  - cloud commandやexternal API executionは別承認にする。
- Gate: loop guard and cloud/account/cost gate
- Next condition: loop guard、identity/trust/moderation、cloud approval boundaryが決まったら、MVP-008へ進む。
- Not doing:
  - cloud resource作成、credential作成、billing変更。
  - P2Pの実運用化。

### UE-XWORLD-MVP-008 Intake Lifecycle And Worldbuilding Pipeline

- Type: `MVP`
- Source TODO IDs: `XWORLD-TODO-034`, `XWORLD-TODO-035`, `XWORLD-TODO-037`, `XWORLD-TODO-038`
- Deliverable: validator / draft flow work order
- Status: `not_started`
- Goal: worldbuilding source extraction、public-safe validator、GitHub/Discord追加依頼、orphan/stale/heartbeat管理をつなぐ。
- Acceptance:
  - Worldbuilding Extraction Pipelineは内容ではなくpipelineだけを採用する。
  - Public-safe Naming Validatorはprotected names、private paths、external post body、secret-like stringsを検出する。
  - Add Request Intake Draft FlowはGitHub/Discordからの「追加して」をdraft-onlyで受ける。
  - Orphan / Stale / Heartbeat Trackingは自己申告・heartbeat・閾値を設計するが、自動closeや自動公開はしない。
  - external writeは人間レビュー前に行わない。
- Gate: TYPE1 public gate and draft-only automation gate
- Next condition: intakeからcoverage分類、TODO ID付与、gate確認までのdry-runが通ったら、Linear本体への起票候補にする。
- Not doing:
  - GitHub issue、Linear issue、Discord投稿の自動作成。
  - private source contentや外部post本文の公開。

## Coverage Check

このLinear draftで扱うTODO ID:

- `XWORLD-TODO-001` through `XWORLD-TODO-039`

受け入れ条件:

- 欠番がない。
- すべてのTODO IDが少なくとも1つのMVP draftに含まれている。
- MVP draftごとにGateとAcceptanceがある。
- `watch` または `parking-lot` のMVPは、理由と次に進む条件を持つ。

## Test Plan

- `python tools/docs_sync_check.py --check`
- `python -m pytest tests/ -q -p no:cacheprovider`
- static scan:
  - protected namesなし
  - private pathなし
  - external post bodyなし
  - secret-like stringなし
- coverage check:
  - `XWORLD-TODO-001` から `XWORLD-TODO-039` がMVP draftに含まれる。
  - 各MVP draftに `Gate:` と `Acceptance:` がある。
