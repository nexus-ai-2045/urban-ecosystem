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

## 注意

- Webhook URL は秘密情報です。issue、PR、commit、ログに貼らないでください。
- Discord は通知先であり、議論と採否の正本は GitHub PR / issue に置きます。
- secret が未設定の場合、workflow は通知を送らずに skip します。
- まずは PR 作成通知だけに限定します。merge、comment、review への通知拡張は運用してから判断します。
