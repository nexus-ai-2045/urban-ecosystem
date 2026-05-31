# Next Session Control Panel — urban-ecosystem

updated: 2026-06-01

## 2026-06-01 セッション最新状態 (UE-TECH tracker handoff)

### Current git state

- `origin/main` / `origin/HEAD`: `3cf0319` (`Merge pull request #3 from nexus-ai-2045/codex/code-review-fixes`)。
- local `main`: `df5afb7` で `origin/main` より 11 commits behind。新規作業は `origin/main` 起点にするか、先に local `main` を更新する。
- working tree: UE-TECH-008 更新前は tracked change なし。
- push / PR / Cloud Run 再デプロイは Type1。CEO 明示 GO なしに実行しない。

### Local branch inventory

| Branch | Head | Base / stack | State |
| --- | --- | --- | --- |
| `codex/ue-tech-002-run-id-consistency` | `26ef55f` | `origin/main` + 1 | pushed to fork; draft PR #4: https://github.com/nexus-ai-2045/urban-ecosystem/pull/4 |
| `codex/ue-tech-004-doc-cli-alignment` | `525c3c3` | `origin/main` + 1 | pushed to fork; draft PR #5: https://github.com/nexus-ai-2045/urban-ecosystem/pull/5 |
| `codex/ue-tech-005-ci-e2e` | `1c5e5a1` | `origin/main` + 1 | pushed to fork; draft PR #7: https://github.com/nexus-ai-2045/urban-ecosystem/pull/7 |
| `codex/ue-tech-006-sample-pois-validation` | `199e4cc` | `origin/main` + 1 | pushed to fork; draft PR #6: https://github.com/nexus-ai-2045/urban-ecosystem/pull/6 |
| `codex/ue-tech-007-dependency-split` | `8d6ab5b` | `ue-tech-005` の上に 1 commit | pushed to fork; upstream PR は `UE-TECH-005` merge 後に作成する。 |
| `codex/ue-tech-008-refresh-handoff` | current branch | `origin/main` + docs refresh | pushed to fork; draft PR #8: https://github.com/nexus-ai-2045/urban-ecosystem/pull/8 |

Older local branches `codex/ue-tech-001-disable-gcs` and `codex/ue-tech-003-data-contract-validation` も残っているが、どちらも `origin/main` に merge 済み。`UE-TECH-002` は未mergeのため、fresh `origin/main` 起点に rebase 済み。

### Recommended integration order

1. Review/merge independent draft PRs: `UE-TECH-002` #4, `UE-TECH-004` #5, `UE-TECH-006` #6.
2. Review/merge `UE-TECH-005` #7 before `UE-TECH-007`, because `UE-TECH-007` updates the CI workflow introduced by `UE-TECH-005`.
3. After #7 lands, rebase or refresh `codex/ue-tech-007-dependency-split` onto the updated `origin/main`, then create its upstream PR.
4. `UE-TECH-008` #8 is docs-only and should be refreshed again if branch heads or PR URLs change before merge.

### UE-TECH completed in this batch

- **UE-TECH-002** `26ef55f`: `/api/runs` が返す run ID と `/api/data/{run_id}` で読める ID を揃える。
- **UE-TECH-004** `525c3c3`: `docs/deploy.md` の Cloud Run Job command を current CLI (`run --sample ... --out`) に合わせ、GCS output は future scale work と明記。
- **UE-TECH-005** `1c5e5a1`: `.github/workflows/ci.yml` 追加。Playwright Chromium + fallback E2E を API keys なしで CI 実行。E2E は一時 `DATA_DIR` に `urban_demo` を生成。
- **UE-TECH-006** `199e4cc`: `pois >= 3` validation。`--sample-pois 1/2` は readable error + exit code 2、`3` は成功。
- **UE-TECH-007** `8d6ab5b`: `requirements.txt` を runtime-only にし、`requirements-dev.txt` に pytest/playwright を分離。Dockerfile は runtime deps のみ。

### Still gated / not run

- 実 Vertex run は未実施。課金/G2 対象なので CEO 明示 GO 後のみ実行する。
- Cloud Run 再デプロイ / 公開切替も Type1 のまま。
- `data/` は gitignore で、N100/N10 などの run data は必要時に再生成する。

---

(以下は 2026-05-30 までの記録 / 旧 Control Panel は git 履歴参照)

## 方針 (2026-05-29 CEO 確定)
- ローカルオンリーで開発。Cloud Run 再デプロイ / 公開切替 = Type1 (保留)。
- GitHub は PUBLIC 公開済み (`github.com/nexus-ai-2045/urban-ecosystem` / 著者 nexus-ai-2045)。push は都度 CEO 確認 (Type1)。
- commit 著者は `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` 固定。private-author で commit しない。
- `data/*.db` 削除禁止 / API キーをコード・ログに出さない。
- git 操作は `cd ~/Projects/urban-ecosystem` 後に実行。commit は inline `-c user.name=nexus-ai-2045 -c user.email=nexus-ai-2045@users.noreply.github.com`。新規ファイルは先に `git add`。
