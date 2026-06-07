# Cross-world Operator Mode ロードマップ

- Status: `draft`
- Owner: `manager`
- Updated: `2026-06-08`
- 詳細表示: [cross-world-operator-roadmap.html](cross-world-operator-roadmap.html)
- Work order: [wo-urban-018-cross-world-operator-roadmap.yaml](subagents/work-orders/wo-urban-018-cross-world-operator-roadmap.yaml)

## 目的

この PR は **docs-only のロードマップ PR** です。

Cross-world Operator Mode は、viewer / operator が複数の simulation layer をまたいで
agent を一時的に観測・操作・案内するための構想です。

初回 PR では、次のものは変更しません。

- application code
- data contracts
- generated docs
- tests
- cloud resources
- Discord / Linear / GitHub issue などの外部 write action

## 公開命名方針

発想段階で参照した外部作品名・キャラクター名は、public repo の implementation ID として使いません。
公開面では、抽象化した archetype / milestone 名だけを使います。

代表的な公開名は次の通りです。

- `Cross-world Operator Mode`
- `Sentinel MVP`
- `World Bridge Actor`
- `Guide / Partner`
- `Agent Roster`
- `Cyber-ops Milestones`
- `Equivalent Exchange Pair`
- `Pillar Council Arc`
- `Unstable Power Arc`
- `Boundary War Arc`
- `Fighter Archetype Set`
- `Social-Tech Mirror Lab`
- `Judgment Game Arc`
- `Ecological Mediation Arc`
- `Pilot Sync Arc`

全文の対応表は HTML preview に置きます。

## ロードマップ概要

### Phase 1: Operator MVP

- `Sentinel MVP`
- `World Bridge Actor`
- `Guide / Partner`
- `Agent Roster`
- `Cyber-ops Milestones`

任意 agent へ入る最小モード、world layer の移動、案内役、監視・介入 archetype を整理します。

### Phase 2: Motif Arcs

- `Equivalent Exchange Pair`
- `Pillar Council Arc`
- `Unstable Power Arc`
- `Boundary War Arc`
- `Fighter Archetype Set`
- `Social-Tech Mirror Lab`
- `Judgment Game Arc`
- `Ecological Mediation Arc`
- `Pilot Sync Arc`

人物名ではなく、代償、評議会、暴走、境界、訓練、社会技術、監視、環境交渉、同期などの
world / behavior pattern として扱います。

### Phase 3: Evaluation / World Layers

- `Human/AI Evaluation Lab`
- `Three-world Layer`
- `Event + Music Layer`
- `Next Motif Expansion Slot`
- `Post-Singularity Scenario Boundary`
- `Chaotic Three-Body World Benchmark`
- `Frontier AI Capability Layer Benchmark`
- `Scale-Simplification Simulation Benchmark`

Human/AI boundary、三層 world、8-bit cue、次の motif 採用枠、post-singularity の境界、
chaotic world、frontier capability benchmark、scale を広げることで simulation noise を減らす
benchmark を扱います。

### Phase 4: Governance / Operations

- `Future-Known Implementation Frame`
- `Human Time-Sense Boundary Benchmark`
- `Numeric Operating Protocol`
- `FDE Packet Router Benchmark`
- `Agent Harness Layer Benchmark`
- `User Oversight Fourth-Power Layer`
- `Deliberative Separation-of-Powers Layer`
- `Repository-as-Skill Mesh`
- `P2P Distributed Operations Spike`
- `Cloud Capacity Envelope`
- `Worldbuilding Extraction Pipeline`

過去対話・Obsidian由来の候補を public-safe benchmark に変換し、
3 AI branches + meta-user oversight layer の fractal decision を FDE で扱います。

## 拡張保証

新しい motif を roadmap に採用するには、必ず次の2つを満たします。

- **Archetype guarantee**:
  agent selection、operator guidance、conflict、evaluation、replay explanation のいずれかに
  登場できる actor / role archetype がある。
- **World guarantee**:
  world rule、pressure、layer、institution、ecology、machine system、boundary condition の
  いずれかがある。

人物だけの追加は不可です。

## Minimum World Packet

implementation ready にする前に、次の7項目を確認します。

- place and environment
- rules of possibility
- social fabric
- resources and power
- history and memory
- daily life signal
- change pressure

不足があるものは `parking-lot` または `watch` に置きます。

## Fractal Decision / FDE

意思決定の基本形は次の4層です。

- Proposal branch
- Review branch
- Execution branch
- Meta-user oversight layer

FDE は fractal decision の採用 protocol とします。

- `entry`
- `packet`
- `evidence`
- `decision`
- `closure`

recursive skill call や repo-as-skill mesh は、loop guard と maximum traversal depth を持つまで
implementation 対象にしません。

## Add Request Intake

GitHub または Discord で「追加して」に相当する request が出た場合、まず draft candidate として扱います。

GitHub が public source of truth です。
Discord は intake / discussion surface に留めます。

Discord chat から GitHub docs / issue / PR へ auto-write しません。

## Non-goals

この PR では次を行いません。

- fictional characters の再現
- protected lines / catchphrases の public code hard-code
- private Obsidian path / voice-chat transcript / private chat phrase の公開
- current labs / models の ranking
- dangerous-capability live test
- P2P network implementation
- cloud command 実行
- secret / credential / billing / quota 変更
- Linear issue 実起票
- GitHub issue / comment 作成

## Cloud / P2P 境界

Cloud は将来の capacity envelope としてのみ扱います。
future cloud use では、次を明記してから human gate に進みます。

- target service
- account / project
- local machine から外へ出る data
- cost / quota risk
- credentials involved
- rollback plan

P2P は design spike 先行です。
identity、trust、sync、conflict resolution、moderation、abuse resistance が定義されるまで実装しません。

## Scale-Simplification Simulation Benchmark

外部公開post由来の採用候補として、scale を広げると simulation が単純化する場合がある、という
benchmark を追加します。

採用する抽象ロジックは次の通りです。

- 人間社会の個別具体は noise が多く、local simulation が難しい場合がある。
- 物理法則が支配する大きな scale では、rule set が少なくなり model 化しやすい場合がある。
- simulation の難しさは world 側だけでなく、人間の認知・理解・観測粒度にも依存する。
- Cross-world Operator Mode では、micro social layer と macro physical layer を比較できるようにする。

この benchmark は宇宙や物理を正確に実装する提案ではなく、world layer の粒度選択と
human cognition boundary を評価するための review item として扱います。

## Worldbuilding Extraction Pipeline

別projectの世界構築ロジックは、内容ではなく pipeline だけを採用します。
private path、固有記事、固有世界名、本文断片は public docs に持ち込みません。

採用する抽象ロジックは次の通りです。

- source article を section に分解する。
- section を world layer に分類する。
- section から claim candidate を抽出する。
- claim に subject、predicate、claim kind、source、terms を付ける。
- terms を concept vocabulary として集約する。
- wiki-style link / reference の欠落を検証する。
- orchestration report に生成手順、抽出数、検証結果を残す。

この pipeline は、Minimum World Packet を補完するための future benchmark として扱います。
実装する場合は別 work order で、toy input または public-safe sample だけを使います。

## Linear Issue Drafts

Linear は internal Nexus maintainer tracking 用です。
GitHub docs / issues / PRs が public source of truth です。

- `UE-XWORLD-001 Roadmap PR: Cross-world Operator Mode`
- `UE-XWORLD-002 Sentinel MVP`
- `UE-XWORLD-003 World Bridge Actor`
- `UE-XWORLD-004 Guide / Partner archetypes`
- `UE-XWORLD-005 Agent roster expansion`
- `UE-XWORLD-006 Equivalent Exchange Pair arc`
- `UE-XWORLD-007 Pillar Council arc`
- `UE-XWORLD-008 Unstable Power arc`
- `UE-XWORLD-009 Boundary War arc`
- `UE-XWORLD-010 Fighter archetype set`
- `UE-XWORLD-011 Social-Tech Mirror Lab`
- `UE-XWORLD-012 Judgment Game arc`
- `UE-XWORLD-013 Ecological Mediation arc`
- `UE-XWORLD-014 Pilot Sync arc`
- `UE-XWORLD-015 Human/AI evaluation lab`
- `UE-XWORLD-016 Three-world and 8bit event layer`
- `UE-XWORLD-017 Next motif expansion slot`
- `UE-XWORLD-018 Local dialogue candidate benchmarks`
- `UE-XWORLD-019 User oversight and separation-of-powers layer`
- `UE-XWORLD-020 Repository-as-skill mesh`
- `UE-XWORLD-021 P2P distributed operations spike`
- `UE-XWORLD-022 Cloud capacity envelope`

## Acceptance Criteria

- public docs は copyrighted work / character names を implementation IDs として使わない。
- motif references は abstract archetypes / milestones に変換されている。
- future motif additions は archetype guarantee と world guarantee の両方を含む。
- public code は sensitive operator-entry phrases を hard-code しない。
- Linear は internal management、GitHub は public source of truth のまま分離する。
- Urban Ecosystem data contract はこの roadmap PR では変更しない。
- follow-up implementation には separate approved work order が必要。
