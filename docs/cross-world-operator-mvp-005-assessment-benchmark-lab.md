# MVP-005 Assessment And Benchmark Lab 実装前仕様

- Status: `draft`
- Version: `0.1.6`
- Owner: `manager`
- Updated: `2026-06-08`
- Linear draft: [cross-world-operator-linear-drafts.md](cross-world-operator-linear-drafts.md)
- TODO正本: [cross-world-operator-todo.md](cross-world-operator-todo.md)
- Work order: [wo-urban-024-cross-world-assessment-benchmark-lab.yaml](subagents/work-orders/wo-urban-024-cross-world-assessment-benchmark-lab.yaml)

## 目的

`UE-XWORLD-MVP-005 Assessment And Benchmark Lab` は、Cross-world Operator Modeの評価対象を、欺瞞や危険なlive testではなく、境界認識、意図推定、安定性、scale handling、harness品質のbenchmarkとして整理するための実装前仕様です。

このPRでは実装コードとdata contractを変更しません。MVP-004までに整理したmotif arcを、評価可能なtoy scenarioと不合格条件へ接続するための公開安全な枠組みだけを固定します。

## Versioning

この仕様追加は、Cross-world Operator Mode docs package の `0.1.6` PATCH更新です。

data contract、主要API、runtime実装は含まないため、Urban Ecosystem data contract `0.5.0` は変更しません。

## 対象TODO

- `XWORLD-TODO-016 Human/AI Assessment Lab`
- `XWORLD-TODO-020 Post-Singularity Scenario Boundary`
- `XWORLD-TODO-021 Chaotic Three-Body World Benchmark`
- `XWORLD-TODO-022 Frontier AI Capability Layer Benchmark`
- `XWORLD-TODO-023 Scale-Simplification Simulation Benchmark`
- `XWORLD-TODO-028 Agent Harness Layer Benchmark`

## MVP境界

### 入れるもの

- Human/AI assessmentを、human-likeness、intention inference、boundary recognitionの評価として定義する。
- Post-Singularity Scenario Boundaryを、予測ではなくbounded scenario familyとして扱う。
- Chaotic benchmarkを、initial-condition sensitivityとstable-windowのtoy benchmarkとして扱う。
- Frontier AI capabilityを、lab/model rankingではなくcapability layerの設計観点として扱う。
- Scale-Simplification Simulationを、micro social layerとmacro physical layerの対応関係として扱う。
- Agent Harness Layerを、model capabilityとproduct harness qualityの分離として扱う。

### 入れないもの

- deceptionを目的にした評価。
- dangerous live test、危険手順、実世界対象の追跡や操作。
- private capability claim、lab/model ranking、未検証の性能断定。
- 外部投稿本文の引用や固有URL本文の再掲。
- post-singularityの予言化、不可避未来としての扱い。
- data contract変更。
- cloud/API/Discord/Linear/GitHub issueの自動作成。

## 評価カテゴリ

| Category | 評価するもの | 入力 | 出力 | 不合格条件 |
| --- | --- | --- | --- | --- |
| `Human/AI Assessment Lab` | human-likeness、intention inference、boundary recognition | toy dialogue、operator intent、role state | calibrated assessment note | deception誘導、人格詐称、境界曖昧化 |
| `Post-Singularity Scenario Boundary` | bounded scenario familyと不確実性 | assumptions、known limits、failure conditions | scenario boundary card | 予言化、確定未来扱い、危険な実行案 |
| `Chaotic Three-Body World Benchmark` | initial-condition sensitivity、stable-window | small changes in world packet | stability comparison | protected narrative再現、物理/数学の断定ミス |
| `Frontier AI Capability Layer Benchmark` | long-horizon autonomy、tool use、governance gate | capability layer checklist | safe capability map | lab/model ranking、private capability claim |
| `Scale-Simplification Simulation Benchmark` | micro social layerとmacro physical layerの対応 | simplified scenario pair | scale mapping note | external post body引用、過度な一般化 |
| `Agent Harness Layer Benchmark` | model capabilityとharness qualityの分離 | goals、permissions、tool routing、recovery checks | harness assessment card | modelだけに責任を寄せる、approval UX欠落 |

## Human/AI Assessment Boundary

- 評価は「AIが人間を騙せるか」ではなく、「意図、境界、制約、未確定性をどれだけ正確に扱えるか」を見る。
- user、operator、agent、harnessの責任境界を明記する。
- assessor calibrationを含め、評価者側の前提やバイアスも記録する。
- 生成物は判断材料であり、人間レビューを代替しない。

## Benchmark運用ルール

- benchmarkはtoy scenarioまたはdocs-only dry runから始める。
- 入力、出力、不合格条件を必ず書く。
- 評価対象が現実の人物、実アカウント、private data、未レビュー外部投稿本文に接続した場合は中断する。
- capabilityは層として扱い、特定lab/modelの序列や未確認能力主張にしない。
- dangerous live test、security probing、social manipulationに接続しない。

## MVP-004との接続

Motif arcは、次の条件を満たした時だけMVP-005のbenchmark対象に進めます。

- Archetype guaranteeを満たす。
- World guaranteeを満たす。
- Minimum World Packetの不足がない。
- public-safe naming gateを通過している。
- evaluation categoryと不合格条件が対応している。

不足がある場合、そのmotifは `watch` または `parking-lot` に戻します。

## 失敗状態

- `assessment_deception_risk`: 評価が欺瞞や人格詐称に寄っている。
- `scenario_unbounded`: scenario familyの前提、範囲、不確実性が書かれていない。
- `unsafe_live_test`: 実世界対象、危険手順、private dataに接続している。
- `capability_claim_unverified`: lab/model rankingや未検証能力主張になっている。
- `source_body_leak`: 外部投稿本文や未レビュー引用が入っている。
- `harness_boundary_missing`: model capabilityとproduct harness qualityが混同されている。

## Acceptance

- 6つの評価カテゴリがpublic-safe名で定義されている。
- Human/AI assessmentがdeceptionではなくhuman-likeness、intention inference、boundary recognitionを扱う。
- Post-Singularity Scenario Boundaryが予測ではなくbounded scenario familyになっている。
- Chaotic benchmark、frontier capability、scale simplification、agent harnessの入力・出力・不合格条件がある。
- protected phrase、作品名、キャラクター名、私的path、外部投稿本文がpublic implementation IDに出ていない。
- data contract変更が必要な場合は別PRに切り出す。
- PR本文、handoff、review notesは日本語を基本にする。

## 次に進む条件

- work order `wo-urban-024-cross-world-assessment-benchmark-lab` がreviewされる。
- MVP-004のmotif arcを評価カテゴリに安全に接続できる。
- MVP-006のgovernance / fractal decisionへ、評価結果の扱い方を渡せる。
- human gate `G1` を通過する。
