# Next Session Control Panel — urban-ecosystem

updated: 2026-05-29

目的:
- 都市地図上で 100 体の AI エージェントが 1 日を過ごす「人工生態系」アプリの MVP を作る。基盤=Google Cloud Run / 地図=Google Maps JS API / 後段LLM=Vertex AI・Gemini。第一成果物=「100体が Day0 を過ごす1日リプレイが Cloud Run で動く」。

現在地:
- 独立 git リポジトリ `~/Projects/urban-ecosystem`（branch=main / remote 未設定 / commit 4本）。
- 仕様確定: spec の解決可能 assumption は全て [事実] 化。残 [実装時確定] 2 件（再生fps / 完走時間 = 実測のみ）。
- WO-URBAN-001 Data Loader 実装済み（models + GeoJSON/JSONL loader + validation / pytest 78 passed）。
- gh active アカウント = `nexus-ai-2045`（事業用 / private-github-account は非アクティブ保持）。

待ち:
- なし（自走可）。唯一の保留 = GitHub push（Type1 / repo 名・public/private 未確認）。

次に読む（4 file に絞る）:
- `docs/spec-open-points.md`（解決済/残課題の追跡表）
- `docs/subagents/work-orders/wo-urban-002-sample-data.yaml`（次の実装対象）
- `docs/ai-ecosystem-tool-spec.md` §19 合成データ生成仕様 / §13.3.2 再現性
- `docs/subagents/contracts/urban-ecosystem-data-contract.md`（データ正本 v0.2）

次にやる（1-3 action）:
1. WO-URBAN-002 Sample Data Generator 実装（§19 仕様: 渋谷bbox / POI300 / 100体profile / Erdős-Rényi social / rng消費順序6step固定 / seed再現性テスト = 3 JSONL の sha256 一致）。
2. その後 WO-URBAN-003 Replay Viewer（FastAPI + Google Maps / fallback 地図）。
3. （並行可）GitHub push する場合は CEO に repo 名・public/private を確認してから。

証跡:
- commit: 78dd475(assumption解決) / ba27290(WO-001, 78 tests) / 55b6192(P1詰め) / a651046(scaffold)
- test: `python3 -m pytest tests/ -v -p no:cacheprovider` → 78 passed
- 仕様検証: spec grep [推測]0 / [不明]0 / [実装時確定]2 / [事実]37

禁止:
- GitHub push / remote 作成 = Type1（外部公開）。CEO 承認まで実行しない。
- commit 著者は `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` を使う（private-author で commit しない）。
- `data/*.db` 削除禁止 / API キーをコード・ログに出さない。

注意:
- git 操作は `git -C ~/Projects/urban-ecosystem` + commit は inline `-c user.name=nexus-ai-2045 -c user.email=nexus-ai-2045@users.noreply.github.com` + sandbox 解除（`git config` 直書きは hook deny される）。
- root commit `a651046` のみ著者 private-author（amend=履歴書換が deny。push 前に再著者化は任意）。
- pyproject.toml 未配置（pytest は `tests/conftest.py` で import 解決 / Pyright の import 警告は静的のみ・runtime は PASS）。urban 専用 pyproject を置くと rootdir が Projects に解決される問題を解消できる。
- urban-ecosystem は Projects monorepo 内にネストした独立 repo。Projects 側に commit を混入させない（過去に staging 誤混入あり → unstage 済み）。
