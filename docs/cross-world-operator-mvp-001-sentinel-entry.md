# MVP-001 Sentinel Operator Entry 実装前仕様

- Status: `implemented`
- Version: `0.2.0`
- Owner: `manager`
- Updated: `2026-06-08`
- Linear draft: [cross-world-operator-linear-drafts.md](cross-world-operator-linear-drafts.md)
- TODO正本: [cross-world-operator-todo.md](cross-world-operator-todo.md)
- Work order: [wo-urban-020-cross-world-sentinel-entry.yaml](subagents/work-orders/wo-urban-020-cross-world-sentinel-entry.yaml)
- Prototype work order: [wo-urban-028-cross-world-sentinel-entry-prototype.yaml](subagents/work-orders/wo-urban-028-cross-world-sentinel-entry-prototype.yaml)

## 目的

`UE-XWORLD-MVP-001 Sentinel Operator Entry` は、operatorが抽象agentを選び、inspection viewpointへ入り、通常replayへ戻る最小モードを定義するためのMVPです。

初回仕様PRでは実装コードを変更しませんでした。`0.2.0` では、entry、return、trigger boundary、failure stateを守ったtoy prototypeを追加します。

## Versioning

このprototype追加は、Cross-world Operator Mode docs package の `0.2.0` MINOR更新です。

data contract、cloud resource、永続stateは含まないため、Urban Ecosystem data contract `0.5.0` は変更しません。

## 対象TODO

- `XWORLD-TODO-001 Cross-world Operator Mode`
- `XWORLD-TODO-002 Sentinel MVP`
- `XWORLD-TODO-039 Operator-entry Trigger Boundary`

## MVP境界

### 入れるもの

- operatorがtoy/public-safe scenario上のagentを選択する。
- operatorが `inspection` viewpointへ入る。
- operatorが通常replay viewpointへ戻る。
- entry、return、ambiguous target、missing target、unsafe triggerの失敗状態を扱う。
- triggerはabstract classとして扱い、公開コードやdocsにprotected phraseをhard-codeしない。

### 入れないもの

- agentの人格再現。
- 外部作品名・キャラクター名・protected phraseのpublic implementation ID化。
- simulation stateを実際に変更するcontrol mode。
- data contract変更。
- cloud/API/Discord/Linear/GitHub issueの自動作成。

## 最小フロー

1. operatorはreplay上の抽象agentを選ぶ。
2. systemは対象agentが一意に解決できるか確認する。
3. entryが許可されると、viewpoint stateは `replay` から `inspection` に変わる。
4. `inspection` 中は、agent視点の観測情報だけを表示する。
5. operatorはreturn actionで `replay` に戻る。
6. どの段階でも失敗した場合は、replay viewpointを維持し、失敗理由を説明する。

## 状態モデル案

- `replay`: 通常の観測状態。
- `entry_pending`: agent解決とgate確認中。
- `inspection`: agent viewpointで観測している状態。
- `return_pending`: replay viewpointへ戻る確認中。
- `blocked`: entryまたはreturnが失敗し、安全な説明を返した状態。

この状態モデルは実装候補であり、このPRではdata contractへ追加しません。

## 失敗状態

- `target_not_found`: 指定agentが存在しない。
- `target_ambiguous`: 候補agentが複数ある。
- `entry_not_allowed`: gateによりentryできない。
- `trigger_not_allowed`: protected phraseやunsafe triggerに該当する。
- `return_failed`: return要求が処理できないが、viewpointはreplayへ安全に戻す。

## Trigger Boundary

- public codeにprotected phraseをhard-codeしない。
- 起動語句は、実装IDではなくhuman review後のlocal/private trigger候補として扱う。
- public docsでは `operator-entry trigger`、`wake phrase class`、`entry intent` のような抽象名だけを使う。
- triggerはentry permissionを表すだけで、agent人格や外部作品由来の振る舞いを再現しない。

## Acceptance

- `agent selection -> entry -> inspection -> return` がtoy scenarioで説明できる。
- 失敗状態がすべてreplay viewpointへ安全に戻る設計になっている。
- protected phrase、作品名、キャラクター名、私的path、外部投稿本文がpublic implementation IDに出ていない。
- data contract変更が必要な場合は、MVP-002以降の別work orderに切り出されている。
- PR本文、handoff、review notesは日本語を基本にする。

## 次に進む条件

- work order `wo-urban-020-cross-world-sentinel-entry` がreviewされる。
- 実装対象ファイル、UI/API境界、data contract影響の有無が次PRで確定する。
- human gate `G1` を通過する。
