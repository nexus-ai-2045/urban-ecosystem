# メンテナー quick guide

このページは、公開協業を始める maintainer 向けの短い説明です。

## 何を作っているか

urban-ecosystem は、都市の地図上で AI エージェントの 1 日を再生するシミュレーションです。

公開協業では、いきなり大きな実装を募集しません。最初は、次のような低ハードルの参加から始めます。

- README を読んで分かるか見る
- API キーなしでローカル起動を試す
- fallback 地図ビューアの見やすさをレビューする
- 課金境界や秘密情報境界の説明をレビューする

## 4つの場所の使い分け

| 場所 | 使う目的 |
|---|---|
| Discord | 人を呼ぶ、軽く質問する、入口を案内する |
| GitHub issue | 作業内容、完了条件、質問を残す |
| GitHub PR | 実際の変更、review、merge 判断を残す |
| Linear | maintainer 側の milestone と運用状態を残す |

迷ったら、作業と判断の正本は GitHub / Linear に残します。Discord は流れてもよい入口です。

公開面の名義は Nexus に統一します。詳細は [`docs/public-identity-policy.md`](public-identity-policy.md) を見てください。

## いまの状態

- 公開協業 milestone: <https://github.com/nexus-ai-2045/urban-ecosystem/milestone/1>
- Linear project: <https://linear.app/nexus-ai-2045/project/urban-ecosystem-公開協業-e80014329275>
- Starter issues:
  - <https://github.com/nexus-ai-2045/urban-ecosystem/issues/10>
  - <https://github.com/nexus-ai-2045/urban-ecosystem/issues/11>
  - <https://github.com/nexus-ai-2045/urban-ecosystem/issues/12>
- Discord 通知 setup issue:
  - <https://github.com/nexus-ai-2045/urban-ecosystem/issues/13>

## 次にやること

1. #13 に沿って Discord webhook を GitHub Actions secret に入れる。
2. Actions の手動 test で Discord 通知を確認する。
3. 次の PR 作成時に自動投稿されることを確認する。
4. Discord に `docs/discord-start-here.md` の案内文を貼る。
5. 参加者には #10 / #11 / #12 のどれかを選んでもらう。

Discord webhook の詳しい設定手順は [`docs/discord-pr-notifications.md`](discord-pr-notifications.md) を見てください。

## Discord に貼るときの言い方

```text
urban-ecosystem の公開協業を始めます。
最初はコードを書かなくてもOKです。

見るだけ、README手順の再現性レビュー、fallback地図UIレビュー、課金境界の説明レビューから歓迎です。
APIキーなしで動くので、Google Cloud課金は発生しません。

はじめに読む:
https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/discord-start-here.md

公開協業 milestone:
https://github.com/nexus-ai-2045/urban-ecosystem/milestone/1

最初のissue:
https://github.com/nexus-ai-2045/urban-ecosystem/issues/10
https://github.com/nexus-ai-2045/urban-ecosystem/issues/11
https://github.com/nexus-ai-2045/urban-ecosystem/issues/12
```

## 注意する境界

- Webhook URL は秘密情報。Discord / GitHub issue / PR / commit に貼らない。
- 公開面は Nexus 名義に統一する。個人 account / email / workspace を公開協業の正本にしない。
- `.env`、API key、token は貼らない。
- Google Cloud / Vertex AI / Google Maps / Google Places は opt-in。勝手に実行しない。
- Cloud Run deploy は別判断。
- ライセンス未定なので、大きな外部実装 PR はまだ始めない。

## 完了したと言える状態

- 公開協業 milestone が GitHub にある。
- #13 が完了して Discord 通知が動く。
- Discord に案内文を投稿済み。
- #10 / #11 / #12 のどれかに参加者が反応できる。
- 参加者が「何から始めればいいか」を 1 分以内に理解できる。
