# MVP-003 Guide And Agent Roster prototype

- Status: `implemented`
- Version: `0.4.0`
- Owner: `manager`
- Updated: `2026-06-08`
- Linear draft: [cross-world-operator-linear-drafts.md](cross-world-operator-linear-drafts.md)
- TODO正本: [cross-world-operator-todo.md](cross-world-operator-todo.md)
- Work order: [wo-urban-022-cross-world-guide-agent-roster.yaml](subagents/work-orders/wo-urban-022-cross-world-guide-agent-roster.yaml)
- Prototype work order: [wo-urban-030-cross-world-guide-roster-prototype.yaml](subagents/work-orders/wo-urban-030-cross-world-guide-roster-prototype.yaml)

## 目的

`UE-XWORLD-MVP-003 Guide And Agent Roster` は、MVP-001のoperator entryとMVP-002のworld bridgeに対して、案内、伴走、監視、追跡、介入、現場支援、統括の抽象roleを選択・確認するためのtoy prototypeです。

このPRではdata contractを変更しません。viewer用のprocess-local stateとして、role責任、operatorとの境界、world layerとの接続、失敗状態、public-safe naming gateを固定します。

## Versioning

このprototype追加は、Cross-world Operator Mode docs package の `0.4.0` MINOR更新です。

data contract、主要API、agent runtime実装は含まないため、Urban Ecosystem data contract `0.5.0` は変更しません。

## 対象TODO

- `XWORLD-TODO-004 Guide / Partner`
- `XWORLD-TODO-005 Agent Roster`
- `XWORLD-TODO-006 Cyber-ops Milestones`

## MVP境界

### 入れるもの

- guide、partner、monitoring、pursuit、intervention、field-support、supervisor roleの抽象定義。
- operator controlとcompanion guidanceの責任範囲の分離。
- roleが `physical`、`simulated`、`liminal` のどこで観測・説明・介入候補提示を行うかの整理。
- toy replayで各roleが説明できる最小sample。
- protected role label、作品名、キャラクター名、real-person identityを使わないnaming boundary。

### 入れないもの

- 外部作品の人物構造をそのままroster化すること。
- agent人格再現、real-person identity、外部作品由来の振る舞い再現。
- exploit-like procedure、dangerous operational instruction、現実の監視・追跡手順。
- operatorがsimulation stateを直接変更するcontrol mode。
- data contract変更。
- cloud/API/Discord/Linear/GitHub issueの自動作成。

## Role定義

| Role | 主責任 | できること | できないこと |
| --- | --- | --- | --- |
| `guide` | operatorへ現在状態を説明する | world layer、entry state、次の安全な選択肢を説明する | operatorの代わりに決定しない |
| `partner` | operatorの意図を整理する | 目的、迷い、戻り先を言語化する | agent controlを実行しない |
| `monitoring` | replay内の変化を観測する | anomaly、stale、heartbeat欠落を検出する | 現実の監視手順を提供しない |
| `pursuit` | simulation内の対象推移を追跡する | toy replay上の対象agentやevent chainを追う | real-world trackingに接続しない |
| `intervention` | 介入候補を提示する | safe action候補、rollback候補、gate理由を示す | 直接stateを変更しない |
| `field-support` | `physical` layer由来の制約を説明する | human approval、cost、運用制約を説明する | cloudや外部APIを勝手に実行しない |
| `supervisor` | role間の衝突を調停する | gate、責任境界、handoff先を決める | user oversightを置き換えない |

このrole setはviewer APIのprocess-local stateとして実装します。data contractへは追加しません。

## Prototype API

- `GET /api/agent-roster`
  - active role、role一覧、各roleの責任、world layer、できること、できないこと、現在contextに合わせたguidanceを返す。
- `POST /api/agent-roster/select`
  - `role_id` を受け取り、active roleを更新する。
  - 受け付けるroleは `guide`、`partner`、`monitoring`、`pursuit`、`intervention`、`field-support`、`supervisor` の抽象roleだけにする。

## Prototype UI

- 右パネルに `Role Roster` を追加する。
- operatorは抽象roleを選び、現在layer、human gate境界、guidanceを確認できる。
- roleはoperator判断やhuman oversightを置き換えず、説明・観測・提案に限定する。

## Operator境界

- operatorは外部監視者であり、agent roleではない。
- guide / partnerはoperatorの判断を助けるが、最終判断を代替しない。
- monitoring / pursuit / interventionはtoy replay内の観測と提案に限定する。
- supervisorはrole間の衝突を整理するだけで、human gateを省略しない。

## World Layer接続

- `physical`: human approval、cost、公開境界、運用制約を説明する。
- `simulated`: replay内のagent、event chain、state change候補を観測する。
- `liminal`: entry gate、return gate、未確定状態、role handoffを説明する。

roleがどのlayerを見ているかを説明できない場合、そのroleはimplementation readyにしません。

## Toy Replay Sample

1. operatorがreplay上の抽象agentを選ぶ。
2. `guide` が現在のworld layerとentry可否を説明する。
3. `partner` がoperatorの目的を短く要約する。
4. `monitoring` がreplay内の状態変化を観測する。
5. `pursuit` が対象agentのtoy event chainを追う。
6. `intervention` が安全な候補を提示する。
7. `supervisor` がgateとhandoff先を確認する。
8. operatorが判断し、returnまたは次のMVPへ進む。

## 失敗状態

- `role_not_found`: 指定roleが定義されていない。
- `role_ambiguous`: 複数roleが同じ責任を主張している。
- `world_layer_missing`: roleがどのworld layerで働くか説明できない。
- `operator_boundary_crossed`: roleがoperator判断やhuman gateを代替しようとしている。
- `unsafe_operational_detail`: 現実の監視・追跡・危険手順に接続している。
- `public_safe_name_failed`: protected role labelや公開不適切な名前が残っている。

## Acceptance

- guide、partner、monitoring、pursuit、intervention、field-support、supervisor roleが抽象名で定義されている。
- operator controlとcompanion guidanceの責任範囲が分かれている。
- 各roleが `physical`、`simulated`、`liminal` のどこに接続するか説明できる。
- toy replayで各roleが何を説明・観測・提案するか示せる。
- protected phrase、作品名、キャラクター名、私的path、外部投稿本文がpublic implementation IDに出ていない。
- data contract変更が必要な場合は別PRに切り出す。
- PR本文、handoff、review notesは日本語を基本にする。

## 次に進む条件

- work order `wo-urban-022-cross-world-guide-agent-roster` がreviewされる。
- MVP-001のoperator entryとMVP-002のworld bridgeに対する案内・監視roleが説明できる。
- role setがMVP-004のmotif arc受け入れに使えることを確認する。
- human gate `G1` を通過する。
