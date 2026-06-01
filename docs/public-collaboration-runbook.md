# 公開協業 runbook

この runbook は、maintainer が Discord から人を案内し、GitHub で協業を進めるための最短手順です。

## 役割分担

| 場所 | 役割 |
|---|---|
| Discord | 人を呼ぶ、軽い質問、入口案内、通知 |
| GitHub issue | 作業の正本、質問、done 条件 |
| GitHub PR | 変更内容、review、merge 判断 |
| Linear | maintainer 向けの milestone / 運用状態 |

Discord は入口です。決定や採否は GitHub / Linear に残します。

公開面の名義は Nexus に統一します。GitHub / Discord 通知 / Linear の扱いは [`docs/public-identity-policy.md`](public-identity-policy.md) に従います。

## 初回の流れ

1. 公開協業 milestone を確認する。
2. #13 に沿って GitHub Actions secret `DISCORD_WEBHOOK_URL` を設定する。
3. テスト PR で Discord 通知を確認する。
4. Discord に `docs/discord-start-here.md` の短文を貼る。
5. 参加者には #10 / #11 / #12 のどれかを選んでもらう。

公開協業 milestone: <https://github.com/nexus-ai-2045/urban-ecosystem/milestone/1>

## Discord に貼る案内

```text
urban-ecosystem の公開協業入口を作りました。
まずは「見るだけ」「README手順を試す」「fallback地図UIを見る」から歓迎です。
APIキーなしで動くので、Google Cloud課金は発生しません。

はじめに読む:
https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/discord-start-here.md

最初のissue:
https://github.com/nexus-ai-2045/urban-ecosystem/issues/10
https://github.com/nexus-ai-2045/urban-ecosystem/issues/11
https://github.com/nexus-ai-2045/urban-ecosystem/issues/12
```

## 参加者に伝える禁止事項

- API キー、トークン、`.env` を貼らない。
- Google Cloud / Vertex AI / Google Maps / Google Places を勝手に実行しない。
- Cloud Run deploy をしない。
- `data/` の生成物や大きな実験結果を commit しない。
- ライセンス未定のまま大きな実装 PR を始めない。

## 初回 review 観点

- README だけで何をするプロジェクトか分かるか。
- API キーなしで動くことが伝わるか。
- 課金境界が怖くなく、かつ誤解されないか。
- issue の done 条件が小さく明確か。
- Discord の通知が多すぎないか。

## 完了の見方

初回公開協業の準備ができたと言える条件:

- 公開協業 milestone が GitHub にある。
- `DISCORD_WEBHOOK_URL` secret が設定済み。
- テスト PR が Discord に投稿済み。
- Discord に案内文を投稿済み。
- #10 / #11 / #12 のどれかに外部参加者が反応できる状態。

未完のままでも進めてよい条件:

- ライセンスは未定でも、小さな docs / review 協力から始める。
- Discord 通知が未設定でも、手動で PR URL と issue URL を貼って案内する。
- 最初の参加者がコードを書かなくても、README の分かりやすさ feedback だけでよい。
