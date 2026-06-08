# MVP-007 Repo-as-Skill And Distributed Ops Prototype

- Status: `implemented`
- Version: `0.8.0`
- Owner: `manager`
- Updated: `2026-06-08`
- Linear draft: [cross-world-operator-linear-drafts.md](cross-world-operator-linear-drafts.md)
- TODO正本: [cross-world-operator-todo.md](cross-world-operator-todo.md)
- Work order: [wo-urban-026-cross-world-repo-skill-distributed-ops.yaml](subagents/work-orders/wo-urban-026-cross-world-repo-skill-distributed-ops.yaml)
- Prototype work order: [wo-urban-034-cross-world-repo-skill-distributed-ops-prototype.yaml](subagents/work-orders/wo-urban-034-cross-world-repo-skill-distributed-ops-prototype.yaml)

## 目的

`UE-XWORLD-MVP-007 Repo-as-Skill And Distributed Ops` は、Cross-world Operator Modeをrepo-as-skill mesh、recursive skill calls、distributed operations、cloud capacity envelopeへ接続する前に、loop guard、allowed I/O、identity / trust / moderation、cloud cost / account gateを固定するtoy prototypeです。

このprototypeではdata contract、cloud resource、credential、external APIを変更しません。MVP-006で明記したskill mesh + orchestration pack前提を、stateless API responseとUI panelへ落とします。

## Versioning

このprototype追加は、Cross-world Operator Mode docs package の `0.8.0` MINOR更新です。

Urban Ecosystem data contract `0.5.0` は変更しません。

## 対象TODO

- `XWORLD-TODO-031 Repository-as-Skill Mesh`
- `XWORLD-TODO-032 P2P Distributed Operations Spike`
- `XWORLD-TODO-033 Cloud Capacity Envelope`

## MVP境界

### 入れるもの

- repo-as-skill meshの責任境界。
- recursive skill callのmaximum depth、allowed I/O、loop guard。
- orchestration packがskill callを制御する方針。
- P2P Distributed Operations Spikeのidentity、trust、sync、conflict resolution、moderation、abuse resistanceの未決事項。
- Cloud Capacity Envelopeのaccount、cost、quota、billing、region、rollback、approval boundary。

### 入れないもの

- cloud resource作成、credential作成、billing変更。
- external API実行、GCP command実行、Discord投稿、Linear issue作成、GitHub issue作成。
- P2P実運用、実ノード参加、実ユーザー間同期。
- recursive skill callの実装。
- loop guardなしのrepo traversal。
- data contract変更。

## Repo-as-Skill Mesh

repoをskill集合として扱う時は、次の単位に分けます。

| Skill family | 責任 | Required guard |
| --- | --- | --- |
| `operator-entry-skill` | entry / return / trigger boundary | human gate、public-safe trigger |
| `world-bridge-skill` | world layer / Minimum World Packet | data contract review |
| `guide-roster-skill` | guide / partner / monitoring / intervention | role boundary |
| `motif-intake-skill` | motif acceptance / parking-lot | public-safe naming gate |
| `assessment-skill` | benchmark / harness assessment | safety review |
| `governance-skill` | FDE packet / oversight | user oversight |
| `distributed-ops-skill` | P2P / cloud capacity planning | trust / cost / approval gate |
| `intake-lifecycle-skill` | add request / stale / heartbeat | draft-only automation gate |

各skillは、source category、allowed input、allowed output、failure state、rollback condition、human gateを持ちます。

## Recursive Skill Call Guard

recursive skill callは、次を満たすまで実装しません。

- `maximum_depth`: 既定値と上限がある。
- `allowed_io`: 読めるsource、書けるartifact、外部write禁止範囲がある。
- `call_reason`: なぜ別skillを呼ぶか説明できる。
- `stop_condition`: 成功、失敗、watch、parking-lot、human reviewの終了条件がある。
- `evidence_packet`: 呼び出し結果がFDE packetに戻る。
- `loop_guard`: 同一skill、同一source、同一decisionを無限に再訪しない。

## P2P Distributed Operations Spike

P2Pは、このMVPでは実装しません。次の未決事項を設計対象にします。

- identity
- trust
- sync
- conflict resolution
- moderation
- abuse resistance
- offline / partial failure
- rollback and audit trail

central serviceとの比較設計ができるまで、P2P実運用化はしません。

## Cloud Capacity Envelope

cloudは「余裕があるから使う」ではなく、次のcapacity envelopeが揃った時だけ検討します。

- target service
- account / project
- billing owner
- estimated cost
- quota
- region
- data egress
- credential boundary
- rollback plan
- human approval

このMVPではcloud commandを実行しません。cloud/API実行は別承認、別work order、別PRに分けます。

## Orchestration Pack接続

MVP-006のFDE packetに、次を追加して扱います。

- `skill_call_plan`: 呼び出すskill、理由、depth。
- `allowed_io`: read / write / external write境界。
- `distributed_risk`: P2P / cloud / moderation / abuse resistanceのrisk。
- `approval_state`: human gateの状態。
- `rollback_condition`: 中断、撤回、watch戻しの条件。

## Prototype API

- `GET /api/repo-skill-mesh`
  - 8つのskill family、recursive guard、P2P design-spike条件、Cloud Capacity Envelope、external write禁止状態を返す。
- `POST /api/repo-skill-mesh/evaluate`
  - `skill_id` が定義済みskill familyなら、guard付きskill planとして評価する。
  - `maximum_depth` は `0..3` の範囲だけ受け入れる。
  - `allowed_io: false` は `allowed_io_missing` で拒否する。
  - `loop_guard: false` は `loop_guard_missing` で拒否する。
  - `p2p_operationalize: true` は `trust_model_missing` で拒否する。
  - `cloud_execute: true` は `cloud_approval_missing` で拒否する。
  - `external_write: true` は `external_write_attempted` で拒否する。

## Prototype UI

右パネルの `Repo Skill` でskill familyを選択し、maximum depth、P2P design-spike、cloud approval boundary、guard statusを確認できます。

このUIはrecursive skill call、P2P、cloudの実行エンジンではありません。外部API、cloud、Discord、GitHub issue、Linear issueへのwriteは行いません。

## 失敗状態

- `recursive_depth_exceeded`: maximum depthを超えた。
- `allowed_io_missing`: skill callの読取/書込境界が未定義。
- `loop_guard_missing`: recursive callの停止条件がない。
- `trust_model_missing`: P2Pのidentity / trust / moderationが未定義。
- `cloud_approval_missing`: account、cost、billing、rollback、approvalが未定義。
- `external_write_attempted`: human review前に外部writeを試みた。

## Acceptance

- repo-as-skill meshのskill familyと責任が定義されている。
- `GET /api/repo-skill-mesh` がskill family、recursive guard、P2P/cloud境界を返す。
- `POST /api/repo-skill-mesh/evaluate` がguard付きskill planだけを受け入れる。
- allowed I/O不足、loop guard不足、depth超過、P2P実運用化、cloud実行、外部writeを拒否する。
- UIからRepo Skill panelでskill family、depth、P2P、cloud、guard statusを確認できる。
- recursive skill callにmaximum depth、allowed I/O、stop condition、loop guardがある。
- P2Pはidentity、trust、moderation、abuse resistanceが未定義なら実装しないと明記されている。
- Cloud Capacity Envelopeにaccount、cost、quota、billing、region、rollback、approval boundaryがある。
- cloud/API/Discord/GitHub/Linear writeをこのMVPで実行しない。
- protected phrase、作品名、キャラクター名、私的path、外部投稿本文がpublic implementation IDに出ていない。
- PR本文、handoff、review notesは日本語を基本にする。

## 次に進む条件

- work order `wo-urban-026-cross-world-repo-skill-distributed-ops` がreviewされる。
- loop guard、allowed I/O、trust/moderation、cloud approval boundaryが説明できる。
- MVP-008のintake lifecycleへ、draft-only automationとheartbeatの境界を渡せる。
- human gate `G1` を通過する。
