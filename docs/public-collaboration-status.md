# 公開協業の現在地

このページは、公開協業を始める前後に「いま何が決まっていて、何がまだ未決か」を確認するための棚卸しです。

最終更新: 2026-06-02

## まず見る場所

- GitHub repository: <https://github.com/nexus-ai-2045/urban-ecosystem>
- 公開協業 milestone: <https://github.com/nexus-ai-2045/urban-ecosystem/milestone/1>
- Discord から来た人向け入口: [`docs/discord-start-here.md`](discord-start-here.md)
- 初回協力候補: [`docs/good-first-issues.md`](good-first-issues.md)
- 協力ガイド: [`CONTRIBUTING.md`](../CONTRIBUTING.md)

## 場所の使い分け

| 場所 | 役割 |
|---|---|
| GitHub issue | 公開作業の正本、質問、完了条件 |
| GitHub PR | 変更内容、review、merge 判断 |
| Discord | 入口案内、軽い質問。現在は一旦フリーズ |
| Linear | Nexus maintainer 側の内部管理 |

公開協業者に見せる作業と判断は GitHub に残します。Discord は流れる入口で、現在は一旦フリーズ中です。Linear は内部管理です。

## いま参加してよいもの

最初は大きな実装ではなく、レビューと再現性確認から始めます。

| issue | 内容 | 参加のしかた |
|---|---|---|
| #10 | README のローカル起動手順を再現性レビューする | 手元で試して、成功/失敗/詰まった点を書く |
| #11 | fallback 地図ビューアの見やすさをレビューする | API キーなしの画面を見て、左パネル・地図・右ライブ概要・下部操作で分かりにくい点を書く |
| #12 | 課金境界と秘密情報境界の説明をレビューする | README / CONTRIBUTING の怖さや不足を指摘する |

## 運用者側で進めるもの

| issue | 内容 | 状態 |
|---|---|---|
| #13 | Discord PR 通知を有効化してテスト投稿する | 一旦フリーズ。webhook / secret / Actions test / 投稿は行わず、再開入口として open 維持 |
| #21 | ライセンス方針を決めて LICENSE を追加する | MIT License として解消済み |

## まだ広く募集しないもの

- issue で目的と範囲を共有していない大きな機能実装
- Google Cloud / Vertex AI / Google Maps / Google Places を実際に呼ぶ作業
- Cloud Run deploy
- シミュレーションモデルの前提変更

## 既存 PR から分かった実装境界

PR #1〜#7 を古い順に見て、初回参加者に伝えるべき現在地だけを残します。

| PR | 参加者向けに拾うこと |
|---|---|
| #1 | `DATA_SOURCE=gcs` は未対応です。local に黙って切り替わらず、未対応として分かるようにしています。 |
| #2 | POI、profile、interaction などの入力データは検証が入ります。サンプルや修正 PR では、形式エラーを見落とさない前提です。 |
| #3 | viewer と LLM 周辺の既知不具合を修正済みです。過去 PR 本文に残っている未対応メモは、必要なら別 issue に切り出して扱います。 |
| #4 | viewer の run ID は API で読み込める ID に揃っています。起動確認では `/api/runs` から選べる run を使います。 |
| #5 | Cloud Run Job 手順は現在の CLI に合わせています。ただし GCS replay 出力や GCS 読み込みはまだ通常の参加入口ではありません。 |
| #6 | 小さすぎる POI 数は読みやすいエラーになります。サンプル生成は README の既定手順から始めます。 |
| #7 | API キーなしで動く CI / fallback E2E があります。初回レビューはこの範囲を基準にします。 |

このため、Discord から来た人にはまず API キーなしの local / fallback viewer / docs review を案内します。GCS、Cloud Run、Vertex AI、Google Maps、Google Places は maintainer が範囲を切ってから扱います。

## fallback viewer レビューの現在地

PR #28 で、Google Maps が表示されない場合でも fallback 地図が使える状態を維持しつつ、左側にマップ状態と設定、右側にライブ概要を追加しました。

API キーなしのレビューでは、次を見ます。

- 左側のマップ状態が fallback / Maps API absent として分かりやすいか。
- 設定ボタンからデータ source と Map ID の状態を確認しやすいか。
- 中央の fallback 地図で、POI / AOI / 住人の意味が分かるか。
- 右側のライブ概要で、run、tick、時刻、住人数、移動中人数、選択中 agent が追えるか。
- 下部の再生、ステップ、速度、スライダーが初見で操作できるか。

このレビューでは Google Maps API、Google Places、Vertex AI、Cloud Run deploy は使いません。

## 既存 PR から分かった協業導線

PR #8〜#20 を見て、公開協業の進め方に関係する現在地だけを残します。

| PR | 参加者向けに拾うこと |
|---|---|
| #8 | 次回作業用の handoff 更新で、公開協業の入口には載せません。 |
| #9 | CONTRIBUTING、issue template、PR template、Discord 入口、good first issue 候補、runbook の土台です。 |
| #14 | 取り下げ済みです。公開名義方針は #15 で扱います。 |
| #15 | 公開面の名義は Nexus に統一します。公開協業者向けの正本は GitHub issue / PR / docs です。 |
| #16 | Discord から来た人向けの案内は、milestone と #10 / #11 / #12 を中心に整理済みです。 |
| #17 | Discord PR 通知は Actions から手動 test できます。Webhook secret がなければ安全に skip します。 |
| #18 | Discord webhook 設定の checklist があります。ただし webhook URL は GitHub Actions secret にだけ保存します。 |
| #19 | 公開 issue / PR / docs には、外に出してよい情報だけを書く方針に整理済みです。 |
| #20 | 公開 docs から内部向けの言葉を外し、外から見ても自然な表現に直しています。 |

Discord 通知は便利な補助ですが、現在は一旦フリーズ中です。通知が未設定でも、GitHub の現在地ページと #10 / #11 / #12 だけで協業は始められます。

## 公開面の安全境界

- 公開 issue / PR / docs には、外に出してよい情報だけを書く。
- API キー、token、`.env`、Webhook URL を貼らない。
- 個人メール、内部 URL、内部コメントを貼らない。
- 公開面の名義は Nexus に統一する。
- 迷ったら GitHub issue に「ここは公開してよい範囲か」を確認する。

## Discord 再開時に貼る短文

現在は Discord 導線を一旦フリーズしています。下記は再開時の文面候補であり、現時点では投稿しません。

```text
urban-ecosystem の公開協業入口を整理しました。
最初はコードを書かなくてもOKです。

まずは README の再現性レビュー、fallback 地図UIレビュー、課金境界の説明レビューから歓迎です。
APIキーなしで動く範囲から始めるので、Google Cloud課金は発生しません。

現在地:
https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/public-collaboration-status.md

はじめに読む:
https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/discord-start-here.md

最初のissue:
https://github.com/nexus-ai-2045/urban-ecosystem/issues/10
https://github.com/nexus-ai-2045/urban-ecosystem/issues/11
https://github.com/nexus-ai-2045/urban-ecosystem/issues/12
```

## 完了の見方

初回公開協業の準備ができたと言える条件:

- 公開協業者が 1 分以内に「最初に読む場所」と「最初に触る issue」を見つけられる。
- #10 / #11 / #12 のどれかに、コードを書かない人でも反応できる。
- #13 が Discord 再開入口として open のまま残っている。
- MIT License が README と `LICENSE` file から確認できる。
- 公開面に内部語、秘密情報、個人情報、内部 URL が出ていない。
