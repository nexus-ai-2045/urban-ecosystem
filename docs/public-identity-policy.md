# 公開名義方針

公開協業で外から見える主体は Nexus に統一します。

## 原則

- GitHub repository / PR / issue / commit author は `nexus-ai-2045` を使う。
- 公開 docs では、maintainer / project owner を Nexus として扱う。
- Discord の公開通知 bot / webhook 名は Nexus または urban-ecosystem 名義にする。
- Linear を使う場合は Nexus の Linear アカウント / workspace / project を使う。
- 個人名義のアカウント、メールアドレス、workspace は公開協業の正本にしない。

## 現在の状態

- GitHub remote: `https://github.com/nexus-ai-2045/urban-ecosystem`
- Git commit author: `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>`
- GitHub CLI active account: `nexus-ai-2045`
- Linear connector の現在ユーザー: `ai nexus <nexus_ai@nexusai2045.com>`
- Linear team: `Nexus_ai_2045`
- Linear project: `urban-ecosystem 公開協業`
- 公開協業 docs / issue は GitHub に置く。

## 使い分け

| 公開面 | 公開名義 |
|---|---|
| GitHub repo | `nexus-ai-2045/urban-ecosystem` |
| Git commit author | `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` |
| GitHub issue / PR | `nexus-ai-2045` |
| Discord 通知 | Nexus / urban-ecosystem 名義の bot 名 |
| Linear | `ai nexus` / `Nexus_ai_2045` |

## 公開正本

公開協業者が見る正本は GitHub です。

- 作業内容: GitHub issue
- 変更内容: GitHub PR
- 手順・方針: リポジトリ内 docs
- Discord: 通知と入口案内
- Linear: Nexus 内部のマイルストーン / 担当管理

## Linear 運用

Nexus Linear project は内部管理に使います。

- project: `urban-ecosystem 公開協業`
- マイルストーン: `公開名義をNexusに統一`
- マイルストーン: `Discord導線を有効化`
- マイルストーン: `初回協力者を受け入れる`

ただし、公開協業者に見せる URL は GitHub issue / PR / docs を優先します。

## 禁止

- 公開協業者向けの正本を個人 Linear workspace だけに置く。
- Webhook URL、token、`.env`、個人メールを GitHub / Discord に貼る。
- 個人アカウントで public repo へ commit / push / PR 作成する。
