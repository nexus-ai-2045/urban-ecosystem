# MVP-008 Intake Lifecycle And Worldbuilding Pipeline Prototype

- Status: `implemented`
- Version: `0.9.0`
- Owner: `manager`
- Updated: `2026-06-08`
- Linear draft: [cross-world-operator-linear-drafts.md](cross-world-operator-linear-drafts.md)
- TODO正本: [cross-world-operator-todo.md](cross-world-operator-todo.md)
- Work order: [wo-urban-027-cross-world-intake-lifecycle-worldbuilding.yaml](subagents/work-orders/wo-urban-027-cross-world-intake-lifecycle-worldbuilding.yaml)
- Prototype work order: [wo-urban-035-cross-world-intake-lifecycle-prototype.yaml](subagents/work-orders/wo-urban-035-cross-world-intake-lifecycle-prototype.yaml)

## 目的

`UE-XWORLD-MVP-008 Intake Lifecycle And Worldbuilding Pipeline` は、Cross-world Operator Modeの最後のMVPとして、追加依頼、worldbuilding抽出、public-safe validator、orphan / stale / heartbeat管理を1つの運用入口にまとめるtoy prototypeです。

このprototypeではdata contract、cloud resource、credential、external APIを変更しません。MVP-007で定義したrepo-as-skill meshとorchestration packに、draft-only intake lifecycleをstateless API responseとUI panelとして接続します。

## Versioning

このprototype追加は、Cross-world Operator Mode docs package の `0.9.0` MINOR更新です。

Urban Ecosystem data contract `0.5.0` は変更しません。

## 対象TODO

- `XWORLD-TODO-034 Worldbuilding Extraction Pipeline`
- `XWORLD-TODO-035 Public-safe Naming Validator`
- `XWORLD-TODO-037 Add Request Intake Draft Flow`
- `XWORLD-TODO-038 Orphan / Stale / Heartbeat Tracking`

## MVP境界

### 入れるもの

- worldbuilding sourceを、公開安全なconcept candidateへ抽象化するpipeline。
- protected names、private paths、external post body、secret-like stringsを検出するpublic-safe validator方針。
- GitHub / Discordの「追加して」依頼をdraft candidateへ変換するintake flow。
- orphan threshold、self-report stale、read-only / draft-only heartbeatの扱い。
- Coverage Guaranteeへ `source category -> public-safe name -> TODO ID -> gate` を戻す運用。

### 入れないもの

- GitHub issue、Linear issue、Discord投稿の自動作成。
- private source content、外部投稿本文、私的path、固有作品名・キャラクター名の公開。
- cloud resource作成、credential作成、billing変更、external API実行。
- 自動close、自動公開、自動merge。
- data contract変更。

## Intake Lifecycle

追加依頼は、次の順でdraft candidateに変換します。

1. `receive`: GitHub / Discord / local note / chatから追加依頼を受ける。
2. `classify`: context idea classを `accepted`、`parking-lot`、`watch`、`rejected/out-of-scope` に分類する。
3. `source_category`: `project-hypothesis`、`public-policy`、`external-benchmark`、`local-source-abstraction` などのsource categoryを付ける。
4. `public_safe_name`: implementation IDではなく、公開安全なabstract nameへ変換する。
5. `minimum_world_packet`: world layer、actor role、conflict、constraint、signal、transition、failure stateを確認する。
6. `todo_or_gate`: acceptedならTODO IDを付け、未成熟なら理由付きでparking-lot / watchへ置く。
7. `draft_artifact`: Markdown仕様、work order、validator checklistのどれかへ落とす。
8. `human_review`: external writeや公開前に人間レビューを通す。
9. `optional_external_issue`: 承認後だけGitHub / Linear / Discordへ反映する。

## Worldbuilding Extraction Pipeline

worldbuilding extractionは、内容そのものではなく構造を抽出します。

| Step | Output | Gate |
| --- | --- | --- |
| `source_stub` | source categoryと公開可否 | private-source containment |
| `section_map` | section単位の役割 | quote containment |
| `world_layer` | physical / simulated / liminalなどのlayer候補 | Minimum World Packet |
| `claim_candidate` | 実装仮説として扱うclaim | evidence review |
| `concept_vocabulary` | public-safe term候補 | naming validator |
| `link_validation` | TODO / MVP / gateへの接続 | drift check |
| `orchestration_report` | FDE packetへ戻す要約 | human review |

public docsには、私的path、固有記事本文、外部投稿本文を載せません。local sourceから得た発想は、公開安全な抽象名とsource categoryだけで扱います。

## Public-safe Naming Validator

validatorは、docs-only PRでも実行できる軽いgateとして設計します。

- protected namesをimplementation IDに使っていないか。
- private pathsや個人環境の絶対pathが出ていないか。
- external post bodyを引用していないか。
- secret-like stringが混入していないか。
- accepted ideaにTODO IDがあるか。
- source categoryが設定されているか。
- Minimum World Packetが未充足のTODOをimplementation readyにしていないか。

## Add Request Intake Draft Flow

「追加して」依頼は、即時の外部writeではなくdraft flowで扱います。

- GitHub comment由来: draft candidateに変換し、public-safe nameとgateを付ける。
- Discord message由来: draft candidateに変換するが、GitHub / Linearへのauto-writeはしない。
- local note由来: private source contentを引用せず、source categoryだけを残す。
- chat由来: coverage matrixに落とし、acceptedならTODO IDを付ける。

外部writeは、draft artifact、review note、acceptanceが揃った後に、人間レビューを通してから別stepで実行します。

## Orphan / Stale / Heartbeat Tracking

orphan / stale / heartbeatは、運用監視のための状態であり、勝手な公開やcloseの理由にはしません。

- `orphan_threshold`: TODO、MVP、work order、artifactのどれにも紐づかないidea数を数える。しきい値超過時はreview alertにする。
- `stale_self_report`: stale候補は、まずowner / agentの自己申告として扱う。自動削除しない。
- `heartbeat`: read-only / draft-onlyで、最後に確認したartifact、未解決gate、次のreview pointを記録する。
- `recovery`: staleやorphanを検出したら、coverage matrixへ戻して分類し直す。

## Orchestration Pack接続

MVP-007のorchestration packに、次のpacketを追加します。

- `intake_packet`: source category、request class、public-safe name、TODO candidate。
- `world_packet`: layer、actor role、conflict、constraint、signal、transition、failure state。
- `validator_packet`: scan result、violations、required remediation。
- `lifecycle_packet`: orphan count、stale status、heartbeat timestamp、review point。
- `handoff_packet`: human decision needed、external write boundary、next artifact。

## 失敗状態

- `source_not_public_safe`: sourceを公開docsへ載せられない。
- `validator_hit`: protected/private/static scanに引っかかった。
- `world_packet_missing`: Minimum World Packetが足りない。
- `todo_classification_missing`: accepted / parking-lot / watch / out-of-scope分類がない。
- `external_write_blocked`: human review前の外部writeなので止めた。
- `heartbeat_missing`: lifecycle statusの最新確認がない。
- `stale_without_self_report`: stale扱いに必要な自己申告や根拠がない。
- `orphan_threshold_exceeded`: orphan候補が許容しきい値を超えた。

## Prototype API

- `GET /api/intake-lifecycle`
  - request class、source category、worldbuilding pipeline、public-safe validator、Minimum World Packet、lifecycle guardを返す。
- `POST /api/intake-lifecycle/draft`
  - 追加依頼を外部writeなしのdraft candidateとして評価する。
  - `accepted` は `XWORLD-TODO-*` のTODO IDを要求する。
  - private source content、protected/private/static scan hit、external write、Minimum World Packet不足、heartbeat不足、stale自己申告不足、orphan threshold超過を拒否する。

## Prototype UI

右パネルの `Intake` でrequest classを選び、source category、Minimum World Packet項目数、orphan / heartbeat boundary、draft candidateを確認できます。

このUIはGitHub issue、Linear issue、Discord投稿、外部APIへのwriteを行いません。すべてruntime-onlyのdraft candidate evaluationです。

## Acceptance

- `XWORLD-TODO-034`、`XWORLD-TODO-035`、`XWORLD-TODO-037`、`XWORLD-TODO-038` だけをMVP-008の対象にしている。
- `GET /api/intake-lifecycle` がintake pipeline、validator、world packet、lifecycle guardを返す。
- `POST /api/intake-lifecycle/draft` が公開安全なdraft candidateだけを受け入れる。
- worldbuilding extractionが、source内容ではなく構造抽出として定義されている。
- public-safe validatorがprotected names、private paths、external post body、secret-like stringsを検出対象にしている。
- 「追加して」依頼がdraft-only intake flowとして扱われ、GitHub / Linear / Discordへのauto-writeをしない。
- orphan threshold、stale self-report、heartbeatが自動closeや自動公開に使われない。
- Coverage Guaranteeへ、source category、public-safe name、TODO ID、gateを戻す。
- PR本文、handoff、review notesは日本語を基本にする。

## 次に進む条件

- work order `wo-urban-027-cross-world-intake-lifecycle-worldbuilding` がreviewされる。
- intakeからcoverage分類、TODO ID付与、gate確認までのdry-runが通る。
- public-safe validatorの検出対象と許容しきい値が説明できる。
- Linear本体への起票は、人間レビュー後の別stepとして扱う。
- human gate `G1` を通過する。
