# Discord PR 通知

> 現在、Discord PR 通知は一旦フリーズ中です。Discord webhook 作成、GitHub secret `DISCORD_WEBHOOK_URL` 設定、Actions 手動 test、Discord 投稿は行いません。再開する場合は issue #13 から続けます。

GitHub PR を Discord に自動通知するには、Discord Webhook URL を GitHub Actions secret として保存します。

## 仕組み

- workflow: `.github/workflows/discord-pr-notify.yml`
- trigger: PR の `opened`、`reopened`、`ready_for_review`、または手動実行
- secret: `DISCORD_WEBHOOK_URL`
- 送信内容: PR title、URL、author、draft / ready 状態、本文 1 行目の要約
- 手動テスト時の送信内容: test title、Actions run URL、実行者、test summary

## 再開時の設定手順

この手順は再開時のために残しています。現時点では実行しません。

1. Discord の対象 channel で webhook を作る。
2. GitHub repository の `Settings` → `Secrets and variables` → `Actions` を開く。
3. Repository secret として `DISCORD_WEBHOOK_URL` を追加する。
4. Actions の `Discord PR notify` を手動実行し、Discord に test 投稿されることを確認する。
5. 次の PR 作成時に自動投稿されることを確認する。

## 3 分 checklist

この checklist は、再開時に実際に webhook を作る人向けです。現時点では実行しません。

### Discord 側

1. 投稿したい channel を開く。
2. channel の `Edit Channel` を開く。
3. `Integrations` → `Webhooks` → `New Webhook` を押す。
4. 名前を `urban-ecosystem PR bot` にする。
5. 投稿先 channel が合っていることを確認する。
6. `Copy Webhook URL` を押す。

Webhook URL はコピーしたら、Discord や GitHub issue には貼らず、次の GitHub secret 入力欄にだけ貼ります。

### GitHub 側

1. `Settings` → `Secrets and variables` → `Actions` を開く。
2. `New repository secret` を押す。
3. Name に `DISCORD_WEBHOOK_URL` を入れる。
4. Secret に Discord webhook URL を貼る。
5. `Add secret` を押す。

### Test

1. `Actions` → `Discord PR notify` を開く。
2. `Run workflow` を押す。
3. title は `urban-ecosystem Discord notify test` にする。
4. summary は `GitHub Actions からの手動テストです。` にする。
5. Discord に test 投稿が出ることを確認する。

Actions page: <https://github.com/nexus-ai-2045/urban-ecosystem/actions/workflows/discord-pr-notify.yml>

## メンテナー checklist

maintainer は再開時に次の順に確認します。現時点では実行しません。

Tracking issue: <https://github.com/nexus-ai-2045/urban-ecosystem/issues/13>

1. Discord の投稿先 channel を決める。
2. channel settings から webhook を作成する。
3. webhook name は `urban-ecosystem PR bot` など、通知元だと分かる名前にする。
4. webhook URL をコピーする。
5. GitHub repo の `Settings` → `Secrets and variables` → `Actions` → `New repository secret` を開く。
6. name に `DISCORD_WEBHOOK_URL` を入れる。
7. secret に webhook URL を貼る。
8. `Add secret` を押す。
9. GitHub repo の `Actions` → `Discord PR notify` → `Run workflow` から手動 test を実行する。
10. Discord に test 投稿が出ることを確認する。
11. 次の PR 作成時に自動投稿されることを確認する。
12. 投稿されたら Discord に `docs/discord-start-here.md` の短文を貼り、#10 / #11 / #12 のどれから始めるか案内する。

## Test で見ること

現時点では手動 test を行いません。再開時に見る観点は次の通りです。

- 手動 test では Actions run URL が出る。
- PR test では PR title と URL が出る。
- author が表示される。
- Manual test / Draft / Ready の状態が表示される。
- mention が飛びすぎない。
- secret URL がログや投稿本文に出ていない。

## 設定できたかの確認

現時点では secret を作らないため、この確認も行いません。

GitHub CLI を使える場合は、次で secret 名だけを確認できます。値は表示されません。

```bash
gh secret list --repo nexus-ai-2045/urban-ecosystem
```

`DISCORD_WEBHOOK_URL` が表示されれば secret は保存済みです。

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
