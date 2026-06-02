# メンテナー quick guide

このページは、公開協業を始める maintainer 向けの短い説明です。

## 何を作っているか

urban-ecosystem は、都市の地図上で AI エージェントの 1 日を再生するシミュレーションです。

公開協業では、いきなり大きな実装を募集しません。最初は、次のような低ハードルの参加から始めます。

- README を読んで分かるか見る
- API キーなしでローカル起動を試す
- fallback 地図ビューアの見やすさをレビューする
- 課金境界や秘密情報境界の分かりにくさが残っていれば、小さい docs issue に分けて報告する

## 4つの場所の使い分け

| 場所 | 使う目的 |
|---|---|
| Discord | 人を呼ぶ、軽く質問する、入口を案内する |
| GitHub issue | 作業内容、完了条件、質問を残す |
| GitHub PR | 実際の変更、review、merge 判断を残す |
| Linear | maintainer 側の milestone と運用状態を残す |

迷ったら、公開協業者に見せる作業と判断の正本は GitHub に残します。Discord は流れてもよい入口です。Linear は Nexus 内部管理です。

公開面の名義は Nexus に統一します。詳細は [`docs/public-identity-policy.md`](public-identity-policy.md) を見てください。

## いまの状態

- 公開協業 milestone: <https://github.com/nexus-ai-2045/urban-ecosystem/milestone/1>
- 現在地の棚卸し:
  - <https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/public-collaboration-status.md>
- Starter issues:
  - <https://github.com/nexus-ai-2045/urban-ecosystem/issues/11>
- Closed baseline issues:
  - #10 README ローカル起動手順レビュー
  - #12 課金境界・秘密情報境界レビュー
  - #13 Discord PR 通知 setup

## 次にやること

1. #11 に沿って fallback viewer の UI レビューを集める。
2. コメントには実行環境、画面サイズ、分かりにくかった点を書いてもらう。
3. 修正が必要なら、小さな docs / UI PR に分ける。
4. README 再現性や課金境界の追加 feedback は、新しい小さい issue に分ける。
5. Discord 再開は別判断にし、webhook / secret / Actions test は今は行わない。

Discord webhook の詳しい設定手順は [`docs/discord-pr-notifications.md`](discord-pr-notifications.md) を見てください。

## Discord に貼るときの言い方

```text
urban-ecosystem の公開協業を始めます。
最初はコードを書かなくてもOKです。

見るだけ、fallback地図UIレビューから歓迎です。
APIキーなしで動くので、Google Cloud課金は発生しません。

はじめに読む:
https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/discord-start-here.md

現在地:
https://github.com/nexus-ai-2045/urban-ecosystem/blob/main/docs/public-collaboration-status.md

公開協業 milestone:
https://github.com/nexus-ai-2045/urban-ecosystem/milestone/1

最初のissue:
https://github.com/nexus-ai-2045/urban-ecosystem/issues/11
```

## 注意する境界

- 公開 issue / PR / docs には、外に出してよい情報だけを書く。
- Linear の内部 URL、内部コメント、個人 account 情報は公開 issue / PR / docs に貼らない。
- Webhook URL は秘密情報。Discord / GitHub issue / PR / commit に貼らない。
- 公開面は Nexus 名義に統一する。個人 account / email / workspace を公開協業の正本にしない。
- `.env`、API key、token は貼らない。
- Google Cloud / Vertex AI / Google Maps / Google Places は opt-in。勝手に実行しない。
- Cloud Run deploy は別判断。
- 大きな外部実装 PR は、先に issue で目的と範囲を共有してもらう。

## 完了したと言える状態

- 公開協業 milestone が GitHub にある。
- #11 に参加者が反応できる。
- #10 / #12 / #13 が完了または停止理由つきで close されている。
- 参加者が「何から始めればいいか」を 1 分以内に理解できる。
