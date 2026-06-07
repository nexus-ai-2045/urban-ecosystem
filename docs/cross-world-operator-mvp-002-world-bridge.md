# MVP-002 World Bridge State Model 実装前仕様

- Status: `draft`
- Version: `0.1.2`
- Owner: `manager`
- Updated: `2026-06-08`
- Linear draft: [cross-world-operator-linear-drafts.md](cross-world-operator-linear-drafts.md)
- TODO正本: [cross-world-operator-todo.md](cross-world-operator-todo.md)
- Work order: [wo-urban-021-cross-world-bridge-state-model.yaml](subagents/work-orders/wo-urban-021-cross-world-bridge-state-model.yaml)

## 目的

`UE-XWORLD-MVP-002 World Bridge State Model` は、MVP-001のoperator entryを、`physical`、`simulated`、`liminal` の三層worldへ接続するための実装前仕様です。

このPRでは実装コードとdata contractを変更しません。次の実装PRで迷わないよう、world layer、移動条件、失敗状態、Minimum World Packet、event/music layerの扱いを公開安全な粒度で固定します。

## 対象TODO

- `XWORLD-TODO-003 World Bridge Actor`
- `XWORLD-TODO-017 Three-world Layer`
- `XWORLD-TODO-018 Event + Music Layer`
- `XWORLD-TODO-036 Minimum World Packet Checklist`

## MVP境界

### 入れるもの

- `physical`、`simulated`、`liminal` の三層world定義。
- layer間移動の条件と失敗状態。
- Minimum World Packetの7項目をimplementation ready判定に使う方針。
- Event + Music Layerをworld layerの体験信号として扱う方針。
- data contract変更が必要になった場合に別PRへ切り出す判断基準。

### 入れないもの

- data contractの実変更。
- WebAudio実装、音源生成、asset追加。
- real-world eventやbrand固有体験の再現。
- cloud/API/Discord/Linear/GitHub issueの自動作成。
- operatorがsimulation stateを直接変更するcontrol mode。

## 三層world定義

- `physical`: 現実側の観測・制約・human approvalを表すlayer。
- `simulated`: replay、agent state、scenario stateを観測するlayer。
- `liminal`: `physical` と `simulated` の間で、operator intent、entry gate、return gateを扱う境界layer。

この三層は実装候補であり、このPRではdata contractへ追加しません。

## 最小フロー

1. operatorはMVP-001の `replay` または `inspection` viewpointからworld bridge要求を出す。
2. systemは移動元layer、移動先layer、対象agent、Minimum World Packetの充足を確認する。
3. 移動が許可されると、viewpoint explanationに現在layerと移動理由を表示する。
4. `liminal` layerでは、移動中・未確定・境界確認中であることを明示する。
5. 移動できない場合は、元のviewpointを維持し、失敗理由を説明する。

## 失敗状態

- `layer_not_found`: 指定layerが定義されていない。
- `transition_not_allowed`: 移動元と移動先の組み合わせが許可されていない。
- `world_packet_incomplete`: Minimum World Packetの必須項目が不足している。
- `agent_context_missing`: layer移動に必要なagent contextが不足している。
- `asset_signal_unavailable`: event/music signalを表示できないが、world transition自体は継続できる。
- `data_contract_required`: 実装にdata contract変更が必要で、このPR範囲では進めない。

## Minimum World Packet

implementation readyにする前に、次の7項目を確認します。

- place and environment
- rules of possibility
- social fabric
- resources and power
- history and memory
- daily life signal
- change pressure

不足がある場合は、そのideaを `watch` または `parking-lot` に戻し、missing fieldsを明記します。

## Event + Music Layer

- Event + Music Layerは、world layerの体験信号として扱う。
- 8-bit WebAudio cueは後続prototype候補に留める。
- このPRでは音源、asset、WebAudio実装を追加しない。
- real-world eventやbrand固有体験は再現せず、participation feelだけを抽象化する。

## Acceptance

- `physical`、`simulated`、`liminal` の三層定義がある。
- layer間移動の条件と失敗状態が説明できる。
- Minimum World Packetの7項目がimplementation ready判定に使われている。
- Event + Music Layerがworld layerの体験信号として扱われ、実装は後続prototypeに分離されている。
- data contract変更が必要な場合は別PRに切り出す。
- PR本文、handoff、review notesは日本語を基本にする。

## 次に進む条件

- work order `wo-urban-021-cross-world-bridge-state-model` がreviewされる。
- MVP-001のoperator entryと三層world modelの接続点が説明できる。
- data contract影響の有無が次PRで確定する。
- human gate `G1` を通過する。
