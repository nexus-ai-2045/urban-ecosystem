# 公開名義方針

公開協業で外から見える主体は Nexus に統一します。

## 原則

- GitHub repository / PR / issue / commit author は `nexus-ai-2045` を使う。
- 公開 docs では、maintainer / project owner を Nexus として扱う。
- Discord の公開通知 bot / webhook 名は Nexus または urban-ecosystem 名義にする。
- Linear を公開協業に使う場合は、Nexus の Linear account / workspace / project を使う。
- 個人名義の account、email、workspace は公開協業の正本にしない。

## 現在の状態

- GitHub remote: `https://github.com/nexus-ai-2045/urban-ecosystem`
- Git commit author: `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>`
- GitHub CLI active account: `nexus-ai-2045`
- 公開協業 docs / issue は GitHub に置く。
- Linear connector は再接続前なら個人側の可能性があるため、公開正本ではなく内部ミラーとして扱う。

## 使い分け

| 公開面 | 公開名義 |
|---|---|
| GitHub repo | `nexus-ai-2045/urban-ecosystem` |
| Git commit author | `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` |
| GitHub issue / PR | `nexus-ai-2045` |
| Discord 通知 | Nexus / urban-ecosystem 名義の bot 名 |
| Linear | 再接続後の Nexus Linear account |

## Linear 再接続後に確認すること

1. Linear connector の current user が Nexus である。
2. Nexus 側で urban-ecosystem project / milestone が見える。
3. 既存の個人側 Linear issue は、必要なら Nexus 側へ移すか、GitHub issue への pointer だけにする。
4. 公開協業者に見せる URL は GitHub issue / PR / docs を優先する。

## 禁止

- 公開協業者向けの正本を個人 Linear workspace だけに置く。
- Webhook URL、token、`.env`、個人メールを GitHub / Discord に貼る。
- personal account で public repo へ commit / push / PR 作成する。
