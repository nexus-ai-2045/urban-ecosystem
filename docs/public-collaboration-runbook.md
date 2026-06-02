# 公開協業 runbook

この runbook は、maintainer が GitHub を正本として公開協業を進めるための最短手順です。

> 現在、Discord 導線は一旦フリーズ中です。Webhook 作成、GitHub secret 設定、Actions 手動 test、Discord 投稿は行いません。旧 issue #13 は close 済みです。

## 役割分担

| 場所 | 役割 |
|---|---|
| Discord | 人を呼ぶ、軽い質問、入口案内。現在は一旦フリーズ |
| GitHub issue | 作業の正本、質問、done 条件 |
| GitHub PR | 変更内容、review、merge 判断 |
| Linear | Nexus maintainer 向けの内部 milestone / 運用状態 |

Discord は入口候補です。公開協業者に見せる決定や採否は GitHub issue / PR に残します。Linear は Nexus maintainer 側の内部管理です。

公開面の名義は Nexus に統一します。GitHub / Discord 通知 / Linear の扱いは [`docs/public-identity-policy.md`](public-identity-policy.md) に従います。

public PR を作る行為は TYPE1 です。PR 公開前に人間レビューを必須とし、[`docs/type1-public-pr-gate.md`](type1-public-pr-gate.md) の確認を通します。

## 初回の流れ

1. 公開協業 milestone を確認する。
2. `docs/public-collaboration-status.md` の現在地を確認する。
3. 参加者には #11 の fallback viewer レビューを案内する。
4. コメントには実行環境、試したこと、分かりにくかった点を書いてもらう。
5. 修正が必要なら、小さな docs / UI PR に分ける。
6. PR を public にする前に TYPE1 gate の人間レビューを通す。
7. Discord 再開が必要になった場合だけ、新しい判断で webhook / secret / Actions test を扱う。

参加者に短く試してもらう場合は、README と同じ smoke を案内します。

```bash
unset GOOGLE_MAPS_API_KEY GOOGLE_PLACES_API_KEY GOOGLE_CLOUD_PROJECT
python tools/smoke_fallback_viewer.py
```

この smoke は #11 の入口確認用です。Google Cloud、Secret Manager、Discord は使いません。

公開協業 milestone: <https://github.com/nexus-ai-2045/urban-ecosystem/milestone/1>
現在地の棚卸し: [`docs/public-collaboration-status.md`](public-collaboration-status.md)
Discord 通知設定 (現在フリーズ): [`docs/discord-pr-notifications.md`](discord-pr-notifications.md)

## Discord 再開時に貼る案内

現在は Discord 導線を一旦フリーズしています。下記は再開時の文面候補であり、現時点では投稿しません。

```text
urban-ecosystem の公開協業入口を作りました。
まずは「見るだけ」「README手順を試す」「fallback地図UIを見る」から歓迎です。
APIキーなしで動くので、Google Cloud課金は発生しません。

はじめに読む:
https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/discord-start-here.md

現在地:
https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/public-collaboration-status.md

最初のissue:
https://github.com/nexus-ai-2045/urban-ecosystem/issues/11
```

## 参加者に伝える禁止事項

- API キー、トークン、`.env` を貼らない。
- public PR に出す前に、人間レビューを受ける。
- Google Cloud / Vertex AI / Google Maps / Google Places を勝手に実行しない。
- Cloud Run deploy をしない。
- `data/` の生成物や大きな実験結果を commit しない。
- 大きな実装 PR は、先に issue で目的と範囲を共有する。

## 初回 review 観点

- README だけで何をするプロジェクトか分かるか。
- API キーなしで動くことが伝わるか。
- 課金境界が怖くなく、かつ誤解されないか。
- issue の done 条件が小さく明確か。
- Discord を再開する場合、通知が多すぎないか。

## 完了の見方

初回公開協業の準備ができたと言える条件:

- 公開協業 milestone が GitHub にある。
- #11 に外部参加者が反応できる状態。
- #10 / #12 / #13 は完了または停止理由つきで close されている。

未完のままでも進めてよい条件:

- Discord 通知が未設定でも、GitHub issue / PR / docs だけで案内する。
- 最初の参加者がコードを書かなくても、README の分かりやすさ feedback だけでよい。
