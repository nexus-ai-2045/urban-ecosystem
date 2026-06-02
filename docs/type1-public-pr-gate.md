# TYPE1 public PR gate

この repo では、GitHub 上に public PR を作る行為を TYPE1 として扱います。

public PR は、本文、差分、commit、branch 名、Actions log、bot 通知の一部が外から見える可能性があります。そのため、PR を public にする前に人間レビューを必須にします。

## 対象

次はすべて TYPE1 gate 対象です。

- public repository に PR を作る。
- public repository に PR 用 branch を push する。
- public PR の本文、title、label、comment を公開する。
- public PR を draft から ready にする。
- public PR を merge する。

## 人間レビュー前にしないこと

- public PR を作らない。
- public branch を push しない。
- GitHub issue / PR / docs に内部 URL、個人 account、token、API key、`.env`、Webhook URL を貼らない。
- Discord webhook 作成、GitHub secret 設定、Actions 手動実行、Discord 投稿をしない。
- Google Cloud / Vertex AI / Google Maps / Google Places / Cloud Run を実行しない。

## 人間レビューで確認すること

- 公開名義が `nexus-ai-2045` である。
- 変更内容が public に出してよい範囲だけである。
- PR title / body / branch 名に内部情報がない。
- diff に secret、個人情報、内部 URL、未公開データがない。
- GCP / Cloud Run / Discord / Secret を実行していない。実行が必要な場合は別途 maintainer 承認がある。
- public SSOT は GitHub docs / issues / PRs、Linear は Nexus 内部管理のままである。

## Codex 運用

Codex は、この gate に触れる変更をまずローカル差分またはドラフト文として作ります。

人間レビューが終わるまで、Codex は public PR 作成、public branch push、PR ready 化、merge を行いません。

レビュー後に public PR を作る場合も、PR 本文に次を明記します。

```text
TYPE1 public PR gate:
- Human review before public PR: completed
- Public identity: nexus-ai-2045
- Secret / internal URL / personal data: not included
- GCP / Cloud Run / Discord / Secret execution: not performed
```
