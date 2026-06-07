# MVP-006 Governance And Fractal Decision 実装前仕様

- Status: `draft`
- Version: `0.1.7`
- Owner: `manager`
- Updated: `2026-06-08`
- Linear draft: [cross-world-operator-linear-drafts.md](cross-world-operator-linear-drafts.md)
- TODO正本: [cross-world-operator-todo.md](cross-world-operator-todo.md)
- Work order: [wo-urban-025-cross-world-governance-fractal-decision.yaml](subagents/work-orders/wo-urban-025-cross-world-governance-fractal-decision.yaml)

## 目的

`UE-XWORLD-MVP-006 Governance And Fractal Decision` は、Cross-world Operator Modeで出てきた評価結果、TODO、PR判断を、単一agentの独断ではなく、proposal、review、execution、oversightに分けて扱うための実装前仕様です。

このPRでは実装コードとdata contractを変更しません。MVP-005までに定義した評価結果を、FDE packet、三権分立風の役割分離、user oversight、three AI branches + meta-user構造へ接続するための公開安全な意思決定枠だけを固定します。

## Versioning

この仕様追加は、Cross-world Operator Mode docs package の `0.1.7` PATCH更新です。

data contract、主要API、runtime実装は含まないため、Urban Ecosystem data contract `0.5.0` は変更しません。

## 対象TODO

- `XWORLD-TODO-024 Future-Known Implementation Frame`
- `XWORLD-TODO-025 Human Time-Sense Boundary Benchmark`
- `XWORLD-TODO-026 Numeric Operating Protocol`
- `XWORLD-TODO-027 FDE Packet Router Benchmark`
- `XWORLD-TODO-029 User Oversight Fourth-Power Layer`
- `XWORLD-TODO-030 Deliberative Separation-of-Powers Layer`

## MVP境界

### 入れるもの

- future imageを予言ではなく、old future image、current local capacity、implementation gapの比較として扱う。
- human time-senseを、wait value、progress、stuck state、next return pointとして報告する。
- Numeric Operating Protocolを `parking-lot` のまま保持し、実装根拠が成熟するまで採用しない。
- FDE packetを `entry -> packet -> evidence -> decision -> closure` として定義する。
- userをagentではなくexternal monitor / fourth-power oversightとして定義する。
- proposal、review、execution、oversightを分離する。

### 入れないもの

- userを自動agentとして扱うこと。
- human approvalを省略するclosed-loop automation。
- prophecy、inevitable future、未検証の未来断定。
- numeric meaningを実装根拠として確定すること。
- single-agent unilateral decisionによるmajor change。
- cloud/API/Discord/Linear/GitHub issueの自動作成。

## Governance Layer

| Layer | 主責任 | 入力 | 出力 | Gate |
| --- | --- | --- | --- | --- |
| `proposal` | 変更案を作る | TODO、benchmark result、operator intent | proposal packet | source category review |
| `review` | 証拠とriskを確認する | proposal packet、tests、drift checks | review note | governance review |
| `execution` | 承認済み作業だけ実行する | reviewed proposal、allowed write paths | PR / docs / work order | human gate |
| `oversight` | 公開境界と異議申し立てを保持する | PR state、release state、user instruction | approval / stop / rollback request | user oversight |

`oversight` はuserの役割です。systemやagentがuserの承認権を代替しません。

## FDE Packet

FDE packetは、意思決定を次の5段階に分けます。

1. `entry`: 何を判断するかを明確にする。
2. `packet`: source category、scope、allowed write paths、gateを束ねる。
3. `evidence`: tests、CI、static scan、human review statusを集める。
4. `decision`: proceed、revise、watch、parking-lot、rejectを選ぶ。
5. `closure`: merge、handoff、next MVP、rollback conditionを記録する。

recursive expansionが必要な場合は、maximum depthとstop conditionを必ず持ちます。

## Human Time-Sense Boundary

作業報告では、次を分けます。

- `wait value`: 待つ意味がある外部処理か。
- `progress`: 実際に進んだこと。
- `stuck state`: 判断待ち、tool待ち、auth待ち、policy gateのどれか。
- `next return point`: 次に人間が判断すべき位置。

「止まっている」ように見える場合でも、CI待ち、人間レビュー待ち、実装ブロッカーを分けて報告します。

## Future-Known Implementation Frame

未来像は次の比較として扱います。

- `old future image`: 以前に想定した未来像。
- `current local capacity`: いまrepoやtoolで実行できること。
- `implementation gap`: まだ足りない設計、権限、検証、合意。

これをprophecyやinevitable futureとして扱いません。

## Numeric Operating Protocol

`XWORLD-TODO-026 Numeric Operating Protocol` は、このMVPでも `parking-lot` を維持します。

- 理由: numeric meaningはcreative hypothesisであり、実装根拠として未成熟。
- 再確認条件: concrete operator workflow、decision packet、testable behaviorに接続できた時。
- 禁止: 数字の意味を確定仕様、権威、hidden ruleとして扱うこと。

## 失敗状態

- `single_agent_decision`: major changeがsingle-agentの独断になっている。
- `oversight_bypassed`: user approvalやhuman gateを省略している。
- `future_claim_overreach`: 未来像を予言や確定事項として扱っている。
- `numeric_rule_overreach`: numeric hypothesisを実装根拠として確定している。
- `packet_missing_evidence`: decision packetにtests、CI、scan、review statusがない。
- `recursive_loop_unbounded`: recursive expansionにdepth limitやstop conditionがない。

## Acceptance

- proposal、review、execution、oversightが分離されている。
- userはagentではなくexternal monitor / fourth-power oversightとして定義されている。
- FDE packetが `entry -> packet -> evidence -> decision -> closure` を持つ。
- Future-Known Implementation Frameがprophecyではなく比較frameになっている。
- Human Time-Sense Boundaryがwait value、progress、stuck state、next return pointを扱う。
- Numeric Operating Protocolは `parking-lot` のまま、理由と再確認条件を持つ。
- protected phrase、作品名、キャラクター名、私的path、外部投稿本文がpublic implementation IDに出ていない。
- PR本文、handoff、review notesは日本語を基本にする。

## 次に進む条件

- work order `wo-urban-025-cross-world-governance-fractal-decision` がreviewされる。
- MVP-005の評価結果をFDE packetに渡せる。
- MVP-007のrepo-as-skill / distributed opsへ、loop guardとoversight boundaryを渡せる。
- human gate `G1` を通過する。
