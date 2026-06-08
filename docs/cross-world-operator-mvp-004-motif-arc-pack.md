# MVP-004 Motif Arc Pack prototype

- Status: `implemented`
- Version: `0.5.0`
- Owner: `manager`
- Updated: `2026-06-08`
- Linear draft: [cross-world-operator-linear-drafts.md](cross-world-operator-linear-drafts.md)
- TODO正本: [cross-world-operator-todo.md](cross-world-operator-todo.md)
- Work order: [wo-urban-023-cross-world-motif-arc-pack.yaml](subagents/work-orders/wo-urban-023-cross-world-motif-arc-pack.yaml)
- Prototype work order: [wo-urban-031-cross-world-motif-arc-prototype.yaml](subagents/work-orders/wo-urban-031-cross-world-motif-arc-prototype.yaml)

## 目的

`UE-XWORLD-MVP-004 Motif Arc Pack` は、追加motifを人物名や作品名ではなく、world structure、behavior pattern、pressure、gateとして受け入れるためのtoy prototypeです。

このPRではdata contractを変更しません。MVP-001からMVP-003で定義したoperator entry、world bridge、role setに対して、motifを安全に接続できるかをviewer APIとUIで確認できるようにします。

## Versioning

このprototype追加は、Cross-world Operator Mode docs package の `0.5.0` MINOR更新です。

Urban Ecosystem data contract `0.5.0` は変更しません。

## 対象TODO

- `XWORLD-TODO-007 Equivalent Exchange Pair`
- `XWORLD-TODO-008 Pillar Council Arc`
- `XWORLD-TODO-009 Unstable Power Arc`
- `XWORLD-TODO-010 Boundary War Arc`
- `XWORLD-TODO-011 Fighter Archetype Set`
- `XWORLD-TODO-012 Social-Tech Mirror Lab`
- `XWORLD-TODO-013 Judgment Game Arc`
- `XWORLD-TODO-014 Ecological Mediation Arc`
- `XWORLD-TODO-015 Pilot Sync Arc`
- `XWORLD-TODO-019 Next Motif Expansion Slot`

## MVP境界

### 入れるもの

- motifをworld / behavior patternとして受け入れる基準。
- Archetype guaranteeとWorld guarantee。
- Minimum World Packetへの接続条件。
- motifごとのpublic-safe summary。
- 次に追加されるmotifを落とさないための `Next Motif Expansion Slot`。

### 入れないもの

- 作品名・キャラクター名・引用台詞のpublic implementation ID化。
- narrative detail、plot再現、固有設定の再現。
- real-person identityやbrand固有eventの再現。
- harmful procedure、real-person targeting、private data inference。
- data contract変更。
- cloud/API/Discord/Linear/GitHub issueの自動作成。

## Motif受け入れ保証

### Archetype Guarantee

motifは最低1つ以上の抽象archetypeを持つ必要があります。

- actor role
- relationship pattern
- pressure source
- failure mode
- recovery or transition path

人物名だけ、または印象だけの追加は不可です。

### World Guarantee

motifはMinimum World Packetに接続できる必要があります。

- place and environment
- rules of possibility
- social fabric
- resources and power
- history and memory
- daily life signal
- change pressure

不足がある場合、そのmotifは `watch` または `parking-lot` に戻し、不足項目を明記します。

## Motif Arc一覧

| Motif | Public-safe core | 必須world要素 | Gate |
| --- | --- | --- | --- |
| `Equivalent Exchange Pair` | cost、restoration、pair dependency | rules of possibility、resources and power、history and memory | public-safe naming review |
| `Pillar Council Arc` | guardian、council、patron、corruption-prime structure | social fabric、resources and power、change pressure | public-safe naming review |
| `Unstable Power Arc` | city-scale instability、uncontrolled power、containment dynamics | place and environment、rules of possibility、change pressure | safety review |
| `Boundary War Arc` | boundary logic、external pressure、protector、strategist、elite intervention | place and environment、social fabric、history and memory | public-safe naming review |
| `Fighter Archetype Set` | discipline、rivalry、precision、training、event-duel | daily life signal、rules of possibility、change pressure | public-safe naming review |
| `Social-Tech Mirror Lab` | technology distortion、identity、trust、short scenario | social fabric、daily life signal、change pressure | social-risk review |
| `Judgment Game Arc` | judgment、surveillance、inference、counter-inference | rules of possibility、social fabric、resources and power | safety review |
| `Ecological Mediation Arc` | environmental negotiation、swarm intelligence、non-human agency | place and environment、social fabric、history and memory | world packet review |
| `Pilot Sync Arc` | synchronization threshold、bio-machine pressure、identity strain | rules of possibility、relationship pattern、failure mode | public-safe naming review |
| `Next Motif Expansion Slot` | future motif intake with TODO or classification | Minimum World Packet coverage | human review |

## Prototype API

- `GET /api/motif-arcs`
  - public-safe motif arc pack、active motif、Archetype guarantee、World guarantee、public-safe gateを返す。
- `POST /api/motif-arcs/evaluate`
  - `motif_id` を受け取り、定義済みpublic-safe motifだけを評価する。
  - 未定義motifや生の固有名っぽい入力は `motif_name_not_safe` で拒否する。
  - `Next Motif Expansion Slot` は、次の採用候補にTODO IDまたは分類が必要であることを返す。

## Prototype UI

- 右パネルに `Motif Arc` を追加する。
- operatorはpublic-safe motifを選び、Archetype ready / World ready / coreを確認できる。
- motifはsimulation stateを変更せず、MVP-005以降のassessment候補として保持する。

## Next Motif Expansion Slot

新しいmotifを採用する時は、次のどちらかに必ず分類します。

- TODO IDを付けて `accepted` にする。
- `watch` / `parking-lot` / `rejected/out-of-scope` に置き、理由と再確認条件を書く。

採用判定では、人物だけの追加を禁止し、最低限のworld contextを要求します。

## Toy Replay接続

1. operatorがmotif候補を追加する。
2. `guide` がmotifのpublic-safe nameと不足world要素を説明する。
3. `partner` がmotifの目的とoperator intentを要約する。
4. `supervisor` がArchetype guarantee、World guarantee、public-safe naming gateを確認する。
5. gateを通ったmotifだけがTODOまたはMVP draftに進む。
6. 不足があるmotifは `watch` または `parking-lot` に戻る。

## 失敗状態

- `motif_name_not_safe`: 作品名、キャラクター名、protected phrase、私的pathが残っている。
- `archetype_missing`: actor role、relationship pattern、pressure sourceが不足している。
- `world_packet_incomplete`: Minimum World Packetを満たしていない。
- `narrative_detail_leak`: 固有plot、引用、固有設定に寄りすぎている。
- `unsafe_scenario_detail`: harmful procedure、targeting、private inferenceに接続している。
- `slot_without_classification`: Next motifがTODO IDまたは分類を持たない。

## Acceptance

- 9つのmotif arcと `Next Motif Expansion Slot` がpublic-safe名で定義されている。
- 新規motifはArchetype guaranteeとWorld guaranteeを両方満たす必要がある。
- 人物だけの追加は禁止と明記されている。
- Minimum World Packetに不足がある場合の `watch` / `parking-lot` 戻しが定義されている。
- protected phrase、作品名、キャラクター名、私的path、外部投稿本文がpublic implementation IDに出ていない。
- data contract変更が必要な場合は別PRに切り出す。
- PR本文、handoff、review notesは日本語を基本にする。

## 次に進む条件

- work order `wo-urban-023-cross-world-motif-arc-pack` がreviewされる。
- motif arcがMVP-002のMinimum World PacketとMVP-003のrole setに接続できる。
- MVP-005のassessment / benchmark labへ、安全なmotif評価対象を渡せる。
- human gate `G1` を通過する。
