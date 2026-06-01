# Discord PR Notifications

GitHub PR を Discord に自動通知するには、Discord Webhook URL を GitHub Actions secret として保存します。

## 仕組み

- workflow: `.github/workflows/discord-pr-notify.yml`
- trigger: PR の `opened`、`reopened`、`ready_for_review`
- secret: `DISCORD_WEBHOOK_URL`
- 送信内容: PR title、URL、author、draft / ready 状態、本文 1 行目の要約

## 設定手順

1. Discord の対象 channel で webhook を作る。
2. GitHub repository の `Settings` → `Secrets and variables` → `Actions` を開く。
3. Repository secret として `DISCORD_WEBHOOK_URL` を追加する。
4. PR を作成し、Actions の `Discord PR notify` が成功することを確認する。

## Maintainer Checklist

PR #9 merge 後、maintainer は次の順に確認します。

1. Discord の投稿先 channel を決める。
2. channel settings から webhook を作成する。
3. webhook name は `urban-ecosystem PR bot` など、通知元だと分かる名前にする。
4. webhook URL をコピーする。
5. GitHub repo の `Settings` → `Secrets and variables` → `Actions` → `New repository secret` を開く。
6. name に `DISCORD_WEBHOOK_URL` を入れる。
7. secret に webhook URL を貼る。
8. `Add secret` を押す。
9. テスト用の小さな draft PR を作る、または既存 draft PR を ready にして、Discord に投稿されるか確認する。
10. 投稿されたら Discord に `docs/discord-start-here.md` の短文を貼り、#10 / #11 / #12 のどれから始めるか案内する。

## Test PR で見ること

- Discord に PR title と URL が出る。
- author が表示される。
- Draft / Ready の状態が表示される。
- mention が飛びすぎない。
- secret URL がログや投稿本文に出ていない。

## Rollback

通知がうるさい、投稿先を間違えた、または secret を漏らした可能性がある場合:

1. GitHub Actions secret `DISCORD_WEBHOOK_URL` を削除する。
2. Discord 側の webhook を削除または regenerate する。
3. 必要なら `.github/workflows/discord-pr-notify.yml` を一時 disable する PR を出す。
4. GitHub PR / issue を正本として、Discord には「通知停止中」とだけ案内する。

## 注意

- Webhook URL は秘密情報です。issue、PR、commit、ログに貼らないでください。
- Discord は通知先であり、議論と採否の正本は GitHub PR / issue に置きます。
- secret が未設定の場合、workflow は通知を送らずに skip します。
- まずは PR 作成通知だけに限定します。merge、comment、review への通知拡張は運用してから判断します。
