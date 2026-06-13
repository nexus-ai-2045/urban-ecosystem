# gcloud / Nexus 管理 Google Cloud 利用方針

status: accepted
owner: nexus_ai
updated: 2026-06-14

この文書は、希望者が Nexus 管理の Google Cloud / Cloud Run 環境を使いたい場合の安全な入口を定義します。

結論: **使ってよいが、token や広い権限を共有しない。目的つき・最小権限・期限つき・監査つきで使う。**

## 基本方針

- 初回参加者の正規入口は、API キーなしの fallback viewer です。Nexus 管理 Cloud Run は maintainer 用の非公開 smoke / demo 環境として扱います。
- 各自の Google Cloud project で試す場合は、その project の所有者が課金、公開範囲、IAM、Secret を管理します。
- Nexus 管理 project を使う場合は、maintainer が目的、期間、権限、予算上限、rollback 条件を確認してから許可します。
- OAuth token、service account key、`.env`、Webhook URL、API key は Discord、GitHub issue、PR、コメントに貼りません。
- gcloud 実行、Cloud Run deploy、Secret Manager、IAM、billing / quota 変更は human gate 対象です。

## 使ってよい範囲

| 区分 | 既定 | 条件 |
|---|---|---|
| fallback viewer のレビュー | 許可 | API key なし。issue で感想や詰まりを共有する |
| Nexus 管理 Cloud Run URL の閲覧 | maintainer のみ | 現在は非公開 smoke 環境。認証なし 403 が正常 |
| Nexus 管理 project の一時利用 | 申請制 | 目的、期間、権限、予算上限、rollback を明記 |
| Cloud Run deploy | maintainer のみ | PR / CI / smoke / rollback plan が揃った場合 |
| Secret Manager / IAM 変更 | maintainer のみ | 変更内容と復旧方法を明記 |
| billing / quota 変更 | 原則不可 | 別途明示承認がある場合のみ |

## 申請テンプレート

GitHub issue または maintainer が指定した review surface に、次を記入します。

```md
## gcloud 利用申請

- 目的:
- 使いたい機能:
- 対象環境:
  - fallback viewer の利用のみ / Nexus 管理 project の一時利用 / 自分の GCP project
- 必要な期間:
- 必要な権限:
- 想定するコマンド:
- 想定する上限:
  - 実行回数:
  - おおよその処理量:
  - 予算上限:
- secret / token / 個人情報を扱うか:
- 外部公開や第三者送信が発生するか:
- rollback / stop 条件:
- 結果をどこに残すか:
```

## 最小権限の目安

原則として、人に広い IAM を付与せず、短命の作業単位で権限を切ります。

| 用途 | 推奨境界 |
|---|---|
| fallback viewer を見る | 権限付与なし。API key なし |
| Nexus 管理 Cloud Run の smoke を見る | maintainer が認証付きで実行し、結果だけ issue / PR に残す |
| smoke / 動作確認 | maintainer が実行し、結果だけ issue / PR に残す |
| Cloud Run service の閲覧 | 必要な場合だけ `roles/run.viewer` 相当 |
| Cloud Run deploy | maintainer または専用 deploy automation。利用者へ直接付与しない |
| Secret Manager | 原則 maintainer のみ。secret 値は共有しない |
| Logs 確認 | 必要なら読み取り専用か、maintainer が抜粋を共有 |

## 禁止事項

- token、service account key、API key、`.env` を共有する。
- 個人アカウントに広い Owner / Editor 権限を付ける。
- 目的が曖昧なまま Cloud Run deploy や Job 実行を許可する。
- 予算上限や停止条件なしに長時間実行を許可する。
- Discord や issue に secret、内部 URL、個人情報、認証済みログを貼る。
- Nexus 管理 project を、個人実験用の自由な sandbox として扱う。

## 運用フロー

1. まず fallback viewer で試す。
2. 足りない場合は申請テンプレートで目的を出す。
3. maintainer が、目的、権限、期間、予算、公開範囲、rollback を確認する。
4. 許可する場合は、最小権限または maintainer 実行で進める。
5. 実行結果、失敗、停止条件、次の判断を GitHub docs / issue / PR に残す。
6. 作業後、不要な権限を外し、残った secret / resource / cost を確認する。

## 参加者への案内文

```md
gcloud / Cloud Run は希望者に使えるようにしますが、token や広い権限は共有しません。
まずは API キーなし fallback viewer を触ってください。Nexus 管理 Cloud Run は現在 maintainer 用の非公開 smoke 環境です。
Nexus 管理 project を使いたい場合は、目的、期間、必要権限、予算上限、rollback 条件を書いて申請してください。
maintainer が範囲を切って、最小権限または maintainer 実行で対応します。
```

## 関連文書

- [README](../README.md)
- [公開協業ステータス](public-collaboration-status.md)
- [デプロイ手順書](deploy.md)
- [Type1 Public PR Gate](type1-public-pr-gate.md)
