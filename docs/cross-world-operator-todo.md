# Cross-world Operator Mode 未実装TODO

- Status: `draft`
- Version: `0.1.10`
- Owner: `manager`
- Updated: `2026-06-08`
- HTML表示: [cross-world-operator-todo.html](cross-world-operator-todo.html)
- Roadmap: [cross-world-operator-roadmap.md](cross-world-operator-roadmap.md)
- Linear起票案: [cross-world-operator-linear-drafts.md](cross-world-operator-linear-drafts.md)
- Work order: [wo-urban-019-cross-world-operator-todo.yaml](subagents/work-orders/wo-urban-019-cross-world-operator-todo.yaml)

## 目的

この文書は、Cross-world Operator Mode ロードマップに載った未実装分を、公開安全なTODOとして漏れなく残すための正本です。

ここでいう「保証」は、会話中の全ニュアンスをそのまま保存することではありません。採用済み・採用候補のideaを、公開可能な粒度で `source -> public-safe name -> TODO -> gate` に変換し、TODO化時に落ちないようにする運用保証です。

## Status Legend

- `not_started`: 未着手。実装には別work orderが必要。
- `parking-lot`: ideaは保持するが、実装条件がまだ足りない。
- `watch`: 外部状況・設計判断・追加情報待ち。
- `rejected/out-of-scope`: このroadmapでは扱わない。理由を明記する。

## Context Idea Coverage Guarantee

TODO化時は、context ideaを必ず次のどれかに分類します。

- `accepted`
- `parking-lot`
- `watch`
- `rejected/out-of-scope`

保証ルール:

- roadmapに載ったideaは、TODOまたは明示的な `parking-lot` / `watch` / `rejected/out-of-scope` に必ず現れる。
- `accepted` ideaは必ずTODO IDを持つ。
- `parking-lot` / `watch` は理由と再確認条件を持つ。
- `rejected/out-of-scope` は公開安全・実装範囲・法務/権利・外部アクション境界の理由を持つ。
- docs、PR本文、Linear draft、review handoffは日本語を基本にする。
- public docsには私的path、外部投稿本文、作品名・キャラクター名を実装IDとして出さない。
- source categoryが未設定のTODOは不可。
- `Minimum World Packet` を満たさない実装TODOは、`parking-lot` または `watch` に置く。

## 日本語優先保証

このroadmap系docsでは、日本語を正本言語にします。

英語を使ってよい範囲:

- 既存ID、ファイル名、コマンド、コード識別子。
- public-safe nameとして定義済みの抽象名。
- `Status` / `Gate` / `Acceptance` などの短い運用label。

日本語で書く範囲:

- PR本文、Linear起票案、handoff、レビュー説明。
- goal、acceptance、gate、not doing、next conditionの説明。
- contextで出た論点の扱いと保留理由。

## Coverage一覧

### operator / agent-possession idea

- Public-safe name: `Cross-world Operator Mode`
- TODO ID: `XWORLD-TODO-001`
- Status: `accepted`
- Gate: human review before implementation
- Notes: 任意agentへ入る全体構想。

### world bridge actor idea

- Public-safe name: `World Bridge Actor`
- TODO ID: `XWORLD-TODO-003`
- Status: `accepted`
- Gate: implementation work order
- Notes: `physical` / `simulated` / `liminal` を扱う。

### guide / partner / roster idea

- Public-safe name: `Guide / Partner`, `Agent Roster`
- TODO ID: `XWORLD-TODO-004`, `XWORLD-TODO-005`
- Status: `accepted`
- Gate: implementation work order
- Notes: 案内・伴走・監視・介入archetype。

### cyber-ops milestones

- Public-safe name: `Cyber-ops Milestones`
- TODO ID: `XWORLD-TODO-006`
- Status: `accepted`
- Gate: review before scope split
- Notes: 現場支援・統括role。

### added motif arcs

- Public-safe name: `Motif Arcs`
- TODO ID: `XWORLD-TODO-007`..`XWORLD-TODO-015`
- Status: `accepted`
- Gate: public-safe naming gate
- Notes: 作品名・人物名ではなくworld / behavior patternとして扱う。

### pilot sync idea

- Public-safe name: `Pilot Sync Arc`
- TODO ID: `XWORLD-TODO-015`
- Status: `accepted`
- Gate: public-safe naming gate
- Notes: 同期・bio-machine pressureの抽象化。

### next motif expansion guarantee

- Public-safe name: `Next Motif Expansion Slot`
- TODO ID: `XWORLD-TODO-019`
- Status: `accepted`
- Gate: intake review
- Notes: 次の採用枠を維持する。

### minimum world richness

- Public-safe name: `Minimum World Packet`
- TODO ID: `XWORLD-TODO-036`
- Status: `accepted`
- Gate: quality gate
- Notes: 7項目が不足するものは実装不可。

### GitHub / Discord add request

- Public-safe name: `Add Request Intake`
- TODO ID: `XWORLD-TODO-037`
- Status: `accepted`
- Gate: TYPE1 public gate
- Notes: auto-writeは禁止。

### orphan / stale / heartbeat

- Public-safe name: `Lifecycle Tracking`
- TODO ID: `XWORLD-TODO-038`
- Status: `accepted`
- Gate: draft-only automation gate
- Notes: 自動公開や自動closeは禁止。

### post-singularity scenario

- Public-safe name: `Post-Singularity Scenario Boundary`
- TODO ID: `XWORLD-TODO-020`
- Status: `accepted`
- Gate: speculative boundary review
- Notes: 予測ではなくbounded scenario。

### chaotic world benchmark

- Public-safe name: `Chaotic Three-Body World Benchmark`
- TODO ID: `XWORLD-TODO-021`
- Status: `accepted`
- Gate: public-safe benchmark review
- Notes: 数学/物理の抽象benchmarkとして扱う。

### frontier AI capability benchmark

- Public-safe name: `Frontier AI Capability Layer Benchmark`
- TODO ID: `XWORLD-TODO-022`
- Status: `accepted`
- Gate: safety review
- Notes: lab/modelランキングや危険手順は禁止。

### three-world layer

- Public-safe name: `Three-world Layer`
- TODO ID: `XWORLD-TODO-017`
- Status: `accepted`
- Gate: data contract review
- Notes: data contract変更は別work order。

### event + 8-bit music

- Public-safe name: `Event + Music Layer`
- TODO ID: `XWORLD-TODO-018`
- Status: `accepted`
- Gate: implementation work order
- Notes: WebAudio cueは後続MVP候補。

### human / AI assessment idea

- Public-safe name: `Human/AI Assessment Lab`
- TODO ID: `XWORLD-TODO-016`
- Status: `accepted`
- Gate: ethics/safety review
- Notes: deceptionではなく、人間らしさ・意図推定・境界認識を評価する。

### operator-entry trigger boundary

- Public-safe name: `Operator-entry Trigger Boundary`
- TODO ID: `XWORLD-TODO-039`
- Status: `accepted`
- Gate: public-safe trigger review
- Notes: 起動語句はpublic codeにhard-codeしない。

### agent harness layer

- Public-safe name: `Agent Harness Layer Benchmark`
- TODO ID: `XWORLD-TODO-028`
- Status: `accepted`
- Gate: implementation boundary review
- Notes: model capabilityとproduct harness qualityを分ける。

### user as fourth-power oversight

- Public-safe name: `User Oversight Fourth-Power Layer`
- TODO ID: `XWORLD-TODO-029`
- Status: `accepted`
- Gate: governance review
- Notes: userはagentではなく外部監視者。

### three AI branches + meta-user

- Public-safe name: `Deliberative Separation-of-Powers Layer`
- TODO ID: `XWORLD-TODO-030`
- Status: `accepted`
- Gate: governance review
- Notes: proposal / review / execution / oversight。

### FDE decision protocol

- Public-safe name: `FDE Packet Router Benchmark`
- TODO ID: `XWORLD-TODO-027`
- Status: `accepted`
- Gate: governance review
- Notes: `entry -> packet -> evidence -> decision -> closure`。

### repo-as-skill / recursive calls

- Public-safe name: `Repository-as-Skill Mesh`
- TODO ID: `XWORLD-TODO-031`
- Status: `accepted`
- Gate: loop guard review
- Notes: maximum traversal depthが必要。

### P2P distributed operations

- Public-safe name: `P2P Distributed Operations Spike`
- TODO ID: `XWORLD-TODO-032`
- Status: `watch`
- Gate: design spike gate
- Notes: identity / trust / moderation未定義。

### cloud capacity

- Public-safe name: `Cloud Capacity Envelope`
- TODO ID: `XWORLD-TODO-033`
- Status: `watch`
- Gate: cloud/account/cost gate
- Notes: gcloud実行・resource作成は別承認。

### worldbuilding pipeline idea

- Public-safe name: `Worldbuilding Extraction Pipeline`
- TODO ID: `XWORLD-TODO-034`
- Status: `accepted`
- Gate: public-safe sample gate
- Notes: 内容ではなくpipelineだけ採用。

### scale-simplification idea

- Public-safe name: `Scale-Simplification Simulation Benchmark`
- TODO ID: `XWORLD-TODO-023`
- Status: `accepted`
- Gate: source abstraction review
- Notes: 外部post本文は引用しない。

## Phase 1: Operator MVP

### XWORLD-TODO-001 Cross-world Operator Mode

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-001 Sentinel Operator Entry 実装前仕様](cross-world-operator-mvp-001-sentinel-entry.md)
- Gate: human review before implementation
- Acceptance:
  - operatorがtoy/public-safe scenarioでagentを選択できる。
  - inspection/control viewpointに入れる。
  - 通常replayへ戻れる。
  - protected phraseやcharacter nameをpublic codeにhard-codeしない。

### XWORLD-TODO-002 Sentinel MVP

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-001 Sentinel Operator Entry 実装前仕様](cross-world-operator-mvp-001-sentinel-entry.md)
- Gate: human review before implementation
- Acceptance:
  - 最小operator modeの範囲が決まっている。
  - agent selection、entry、returnの3点がtoy scenarioで説明できる。
  - data contract変更が必要なら別work orderに切り出す。

### XWORLD-TODO-003 World Bridge Actor

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-002 World Bridge State Model 実装前仕様](cross-world-operator-mvp-002-world-bridge.md)
- Gate: data contract review
- Acceptance:
  - `physical`, `simulated`, `liminal` の状態定義がある。
  - layer間移動の条件と失敗状態が説明できる。
  - existing Urban Ecosystem data contractへの影響を明記する。

### XWORLD-TODO-004 Guide / Partner

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-003 Guide And Agent Roster 実装前仕様](cross-world-operator-mvp-003-guide-agent-roster.md)
- Gate: public-safe naming review
- Acceptance:
  - operator向け案内roleが定義されている。
  - companion roleの責任範囲がagent controlと混同されていない。
  - replay explanationで使える説明文がtoy sampleで確認できる。

### XWORLD-TODO-005 Agent Roster

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-003 Guide And Agent Roster 実装前仕様](cross-world-operator-mvp-003-guide-agent-roster.md)
- Gate: public-safe naming review
- Acceptance:
  - monitoring / pursuit / intervention archetypeが抽象名で定義されている。
  - copyrighted namesやreal-person identitiesを使っていない。
  - roster expansionがoperator MVPと衝突しない。

### XWORLD-TODO-006 Cyber-ops Milestones

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-003 Guide And Agent Roster 実装前仕様](cross-world-operator-mvp-003-guide-agent-roster.md)
- Gate: scope review
- Acceptance:
  - cross-world operation、field support、supervisor roleを分けて説明できる。
  - dangerous or exploit-like procedureを含まない。
  - future work order単位に分割されている。

## Phase 2: Motif Arcs

### XWORLD-TODO-007 Equivalent Exchange Pair

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-004 Motif Arc Pack 実装前仕様](cross-world-operator-mvp-004-motif-arc-pack.md)
- Gate: public-safe naming review
- Acceptance:
  - cost、restoration、pair dependencyを抽象mechanicsとして定義する。
  - Minimum World Packetを満たす。

### XWORLD-TODO-008 Pillar Council Arc

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-004 Motif Arc Pack 実装前仕様](cross-world-operator-mvp-004-motif-arc-pack.md)
- Gate: public-safe naming review
- Acceptance:
  - guardian、council、patron-leader、corruption-prime structureを抽象化する。
  - social fabricとresources/powerを明記する。

### XWORLD-TODO-009 Unstable Power Arc

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-004 Motif Arc Pack 実装前仕様](cross-world-operator-mvp-004-motif-arc-pack.md)
- Gate: safety review
- Acceptance:
  - city-scale instability、uncontrolled power、containment dynamicsをtoy scenarioで表す。
  - escalationやmisuseに直結する手順を含まない。

### XWORLD-TODO-010 Boundary War Arc

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-004 Motif Arc Pack 実装前仕様](cross-world-operator-mvp-004-motif-arc-pack.md)
- Gate: public-safe naming review
- Acceptance:
  - wall/boundary logic、external-world pressure、protector、strategist、elite interventionを抽象化する。
  - conflict structureがMinimum World Packetを満たす。

### XWORLD-TODO-011 Fighter Archetype Set

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-004 Motif Arc Pack 実装前仕様](cross-world-operator-mvp-004-motif-arc-pack.md)
- Gate: public-safe naming review
- Acceptance:
  - discipline、rivalry、precision、training、event-duelを抽象scenario patternにする。
  - real eventやbrand固有の再現にしない。

### XWORLD-TODO-012 Social-Tech Mirror Lab

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-004 Motif Arc Pack 実装前仕様](cross-world-operator-mvp-004-motif-arc-pack.md)
- Gate: social-risk review
- Acceptance:
  - technologyがhuman behavior、identity、trustを歪めるshort scenarioを定義する。
  - manipulationやharmful persuasionを運用手順として書かない。

### XWORLD-TODO-013 Judgment Game Arc

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-004 Motif Arc Pack 実装前仕様](cross-world-operator-mvp-004-motif-arc-pack.md)
- Gate: safety review
- Acceptance:
  - judgment、surveillance、inference、counter-inferenceを抽象化する。
  - real-person targetingやprivate data inferenceを含まない。

### XWORLD-TODO-014 Ecological Mediation Arc

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-004 Motif Arc Pack 実装前仕様](cross-world-operator-mvp-004-motif-arc-pack.md)
- Gate: world packet review
- Acceptance:
  - environmental negotiation、swarm intelligence、non-human agencyを扱う。
  - ecologyとsocial fabricが両方定義されている。

### XWORLD-TODO-015 Pilot Sync Arc

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-004 Motif Arc Pack 実装前仕様](cross-world-operator-mvp-004-motif-arc-pack.md)
- Gate: public-safe naming review
- Acceptance:
  - synchronization thresholdとbio-machine pressureを抽象mechanicsにする。
  - protected namesやquoted linesを使わない。

## Phase 3: Assessment / World Layers

### XWORLD-TODO-016 Human/AI Assessment Lab

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-005 Assessment And Benchmark Lab 実装前仕様](cross-world-operator-mvp-005-assessment-benchmark-lab.md)
- Gate: ethics/safety review
- Acceptance:
  - deceptionではなくhuman-likeness、intention inference、boundary recognitionを評価する。
  - assessor calibrationを含む。

### XWORLD-TODO-017 Three-world Layer

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-002 World Bridge State Model 実装前仕様](cross-world-operator-mvp-002-world-bridge.md)
- Gate: data contract review
- Acceptance:
  - `physical`, `simulated`, `liminal` の3層定義を持つ。
  - data contract変更が必要なら別PRにする。

### XWORLD-TODO-018 Event + Music Layer

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-002 World Bridge State Model 実装前仕様](cross-world-operator-mvp-002-world-bridge.md)
- Gate: asset/publication review
- Acceptance:
  - event participation feelをpublic-safeに抽象化する。
  - 8-bit WebAudio cueのtoy prototype範囲が決まっている。

### XWORLD-TODO-019 Next Motif Expansion Slot

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-004 Motif Arc Pack 実装前仕様](cross-world-operator-mvp-004-motif-arc-pack.md)
- Gate: human review
- Acceptance:
  - new motifがarchetype guaranteeとworld guaranteeを満たす。
  - TODO IDまたはparking-lot/watch分類が必ず付く。

### XWORLD-TODO-020 Post-Singularity Scenario Boundary

- Status: `drafted`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-005 Assessment And Benchmark Lab 実装前仕様](cross-world-operator-mvp-005-assessment-benchmark-lab.md)
- Gate: speculative claim review
- Acceptance:
  - predictionではなくbounded scenario familyとして扱う。
  - assumptions、uncertainty、failure conditionsを明記する。

### XWORLD-TODO-021 Chaotic Three-Body World Benchmark

- Status: `drafted`
- Source category: `external-practice`
- Next artifact: [MVP-005 Assessment And Benchmark Lab 実装前仕様](cross-world-operator-mvp-005-assessment-benchmark-lab.md)
- Gate: public-safe benchmark review
- Acceptance:
  - initial-condition sensitivityとstable-windowをtoy scenarioで扱う。
  - protected narrative detailsを再現しない。

### XWORLD-TODO-022 Frontier AI Capability Layer Benchmark

- Status: `drafted`
- Source category: `external-practice`
- Next artifact: [MVP-005 Assessment And Benchmark Lab 実装前仕様](cross-world-operator-mvp-005-assessment-benchmark-lab.md)
- Gate: safety review
- Acceptance:
  - long-horizon autonomy、tool use、governance gateを公開安全に扱う。
  - lab/model ranking、private capability claim、dangerous live testをしない。

### XWORLD-TODO-023 Scale-Simplification Simulation Benchmark

- Status: `drafted`
- Source category: `external-practice`
- Next artifact: [MVP-005 Assessment And Benchmark Lab 実装前仕様](cross-world-operator-mvp-005-assessment-benchmark-lab.md)
- Gate: source abstraction review
- Acceptance:
  - micro social layerとmacro physical layerを比較できる。
  - external post bodyを引用しない。
  - human cognition boundaryを評価項目に含める。

## Phase 4: Governance / Operations

### XWORLD-TODO-024 Future-Known Implementation Frame

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-006 Governance And Fractal Decision 実装前仕様](cross-world-operator-mvp-006-governance-fractal-decision.md)
- Gate: source category review
- Acceptance:
  - old future image、current local capacity、implementation gapを比較する。
  - prophecyやinevitable futureとして扱わない。

### XWORLD-TODO-025 Human Time-Sense Boundary Benchmark

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-006 Governance And Fractal Decision 実装前仕様](cross-world-operator-mvp-006-governance-fractal-decision.md)
- Gate: assessment review
- Acceptance:
  - wait value、progress、stuck state、next return pointをreportできる。
  - raw intelligenceだけをhuman/AI boundaryにしない。

### XWORLD-TODO-026 Numeric Operating Protocol

- Status: `parking-lot`
- Source category: `creative-hypothesis`
- Next artifact: [MVP-006 Governance And Fractal Decision 実装前仕様](cross-world-operator-mvp-006-governance-fractal-decision.md)
- Gate: human review before implementation
- Reason: numeric meaningはcreative hypothesisであり、実装根拠としては未成熟。
- Recheck condition: concrete operator workflowに接続できた時。

### XWORLD-TODO-027 FDE Packet Router Benchmark

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-006 Governance And Fractal Decision 実装前仕様](cross-world-operator-mvp-006-governance-fractal-decision.md)
- Gate: governance review
- Acceptance:
  - `entry -> packet -> evidence -> decision -> closure` をTODO/PR判断に適用できる。
  - recursive expansionにloop guardがある。

### XWORLD-TODO-028 Agent Harness Layer Benchmark

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-005 Assessment And Benchmark Lab 実装前仕様](cross-world-operator-mvp-005-assessment-benchmark-lab.md)
- Gate: implementation boundary review
- Acceptance:
  - model capabilityとproduct harness qualityを分ける。
  - goals、permissions、approval UX、tool routing、recovery、checksを評価する。

### XWORLD-TODO-029 User Oversight Fourth-Power Layer

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-006 Governance And Fractal Decision 実装前仕様](cross-world-operator-mvp-006-governance-fractal-decision.md)
- Gate: human oversight review
- Acceptance:
  - userをagentではなくexternal monitorとして定義する。
  - public release authorityと異議申し立て権を明記する。

### XWORLD-TODO-030 Deliberative Separation-of-Powers Layer

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-006 Governance And Fractal Decision 実装前仕様](cross-world-operator-mvp-006-governance-fractal-decision.md)
- Gate: governance review
- Acceptance:
  - proposal、review、execution、meta-user oversightを分ける。
  - major changeがsingle-agent unilateral decisionにならない。

### XWORLD-TODO-031 Repository-as-Skill Mesh

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-007 Repo-as-Skill And Distributed Ops 実装前仕様](cross-world-operator-mvp-007-repo-skill-distributed-ops.md)
- Gate: loop guard review
- Reason: recursive skill callのloop guardとmax traversal depthが未設計。
- Recheck condition: callable skill entrypointとallowed I/Oを定義できた時。

### XWORLD-TODO-032 P2P Distributed Operations Spike

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-007 Repo-as-Skill And Distributed Ops 実装前仕様](cross-world-operator-mvp-007-repo-skill-distributed-ops.md)
- Gate: trust/moderation review
- Reason: identity、trust、sync、conflict resolution、moderation、abuse resistanceが未定義。
- Recheck condition: central serviceとの比較設計ができた時。

### XWORLD-TODO-033 Cloud Capacity Envelope

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-007 Repo-as-Skill And Distributed Ops 実装前仕様](cross-world-operator-mvp-007-repo-skill-distributed-ops.md)
- Gate: cloud/account/cost review
- Reason: target service、account/project、data egress、cost/quota、credentials、rollback planが未確定。
- Recheck condition: cloud use caseが具体化した時。

### XWORLD-TODO-034 Worldbuilding Extraction Pipeline

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-008 Intake Lifecycle And Worldbuilding Pipeline 実装前仕様](cross-world-operator-mvp-008-intake-lifecycle-worldbuilding.md)
- Gate: private-source containment review
- Acceptance:
  - source article -> section -> world layer -> claim candidate -> concept vocabulary -> link validation -> orchestration reportのpipelineをtoy inputで検証する。
  - private path、固有記事、固有世界名、本文断片をpublic docsに出さない。

## Cross-cutting TODO

### XWORLD-TODO-035 Public-safe Naming Validator

- Status: `drafted`
- Source category: `public-policy`
- Next artifact: [MVP-008 Intake Lifecycle And Worldbuilding Pipeline 実装前仕様](cross-world-operator-mvp-008-intake-lifecycle-worldbuilding.md)
- Gate: quality-gate review
- Acceptance:
  - protected names、private paths、external post body、secret-like stringsを検出できる。
  - docs-only PRでも実行できる。

### XWORLD-TODO-036 Minimum World Packet Checklist

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-002 World Bridge State Model 実装前仕様](cross-world-operator-mvp-002-world-bridge.md)
- Gate: quality-gate review
- Acceptance:
  - 7項目を満たさないideaをimplementation readyにしない。
  - missing fieldsをparking-lot/watchに送れる。

### XWORLD-TODO-037 Add Request Intake Draft Flow

- Status: `drafted`
- Source category: `public-policy`
- Next artifact: [MVP-008 Intake Lifecycle And Worldbuilding Pipeline 実装前仕様](cross-world-operator-mvp-008-intake-lifecycle-worldbuilding.md)
- Gate: TYPE1 public gate
- Acceptance:
  - GitHub/Discordの「追加して」をdraft candidateに変換できる。
  - DiscordからGitHubへauto-writeしない。

### XWORLD-TODO-038 Orphan / Stale / Heartbeat Tracking

- Status: `drafted`
- Source category: `project-hypothesis`
- Next artifact: [MVP-008 Intake Lifecycle And Worldbuilding Pipeline 実装前仕様](cross-world-operator-mvp-008-intake-lifecycle-worldbuilding.md)
- Gate: draft-only automation review
- Acceptance:
  - orphan thresholdを追跡できる。
  - staleはself-report firstで扱う。
  - heartbeatはread-only/draft-onlyを守る。

### XWORLD-TODO-039 Operator-entry Trigger Boundary

- Status: `drafted`
- Source category: `public-policy`
- Next artifact: [MVP-001 Sentinel Operator Entry 実装前仕様](cross-world-operator-mvp-001-sentinel-entry.md)
- Gate: public-safety review
- Acceptance:
  - public codeにprotected phraseをhard-codeしない。
  - trigger classはabstract nameだけを使う。

## Rejected / Out of Scope

- 作品名・キャラクター名をpublic implementation IDにすること。
  - Status: `rejected/out-of-scope`
  - Reason: public safety / rights boundary。
- private note path、private chat phrase、voice-chat transcriptをpublic docsへ出すこと。
  - Status: `rejected/out-of-scope`
  - Reason: privacy / source containment。
- 外部post本文をpublic docsに引用すること。
  - Status: `rejected/out-of-scope`
  - Reason: source abstraction / quote containment。
- GitHub issue、Linear issue、Discord投稿をこのTODO PRで作ること。
  - Status: `rejected/out-of-scope`
  - Reason: external write action boundary。

## Validation Checklist

- roadmap-derived itemがTODOまたは明示分類に現れる。
- `accepted` ideaにTODO IDがある。
- `parking-lot`, `watch`, `rejected/out-of-scope` に理由がある。
- source categoryが全TODOに設定されている。
- private path、外部post本文、作品名・キャラクター名を実装IDとして含まない。
