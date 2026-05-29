# Next Session Control Panel — urban-ecosystem

updated: 2026-05-29

目的:
- 都市地図上で 100 体の AI エージェントが 1 日を過ごす「人工生態系」アプリの MVP を作る。基盤=Google Cloud Run / 地図=Google Maps JS API / 後段LLM=Vertex AI・Gemini。第一成果物=「100体が Day0 を過ごす1日リプレイが Cloud Run で動く」。

現在地:
- 独立 git リポジトリ `~/Projects/urban-ecosystem`（branch=main / remote 未設定）。
- 仕様確定: spec の解決可能 assumption は全て [事実] 化。残 [実装時確定] 2 件（再生fps / 完走時間 = 実測のみ）。
- WO-URBAN-001 Data Loader 実装済み（models + GeoJSON/JSONL loader + validation / pytest 78 passed）。
- WO-URBAN-002 Sample Data Generator 実装済み（`tools/generate_urban_sample.py` / 静的データのみ = §19 準拠 / pytest 17 passed / 全体 95 passed）。**未 commit**。
  - scope 確定（2026-05-29 CEO）: WO-002 は静的データ（pois/aois/roadnet/agent_profiles/summary）のみ。挙動ログ（agent_states/visit/interaction）は WO-004 の責務。orchestration doc / wo-yaml の acceptance を §19 整合に修正済み。
  - 再現性: 同一 seed で静的 4 ファイル sha256 byte 一致を smoke 確認。`data/` を .gitignore 追加。
- gh active アカウント = `nexus-ai-2045`（事業用 / private-github-account は非アクティブ保持）。

待ち:
- なし（自走可）。唯一の保留 = GitHub push（Type1 / repo 名・public/private 未確認）。

次に読む（WO-003 着手時）:
- `docs/subagents/work-orders/wo-urban-003-replay-viewer.yaml`（次の実装対象）
- `docs/ai-ecosystem-tool-spec.md` §5 画面仕様 / §5.1.5 fallback 地図 / §21 API schema
- `docs/subagents/contracts/urban-ecosystem-data-contract.md`（データ正本 v0.2）

次にやる（1-3 action）:
1. WO-002 を commit（著者 = nexus-ai-2045 / 下記「注意」の inline -c 方式）。変更: `tools/generate_urban_sample.py` / `tests/tools/` / `.gitignore` / docs acceptance 3 件 / NEXT-SESSION。
2. WO-URBAN-004 Rule Simulation（§9 行動ルール / §20 境界ケース / 挙動 3 jsonl 生成 + §13.3.2 再現性）。または先に WO-URBAN-003 Replay Viewer（FastAPI + Google Maps / fallback 地図）。S3 は S2 完了で着手可、S4 と並列可。
3. （並行可）GitHub push / Cloud Run は GCP 連携（nexus-ai-2045）の段で CEO に repo 名・public/private を確認してから。

証跡:
- commit (WO-002 着手前): 78dd475(assumption解決) / ba27290(WO-001, 78 tests) / 55b6192(P1詰め) / a651046(scaffold)
- test: `python3 -m pytest tests/ -q -p no:cacheprovider` → 95 passed（WO-001:78 + WO-002:17）
- 再現性 smoke: `generate_urban_sample.py --seed 42` を 2 回 → pois/aois/roadnet/agent_profiles の sha256 一致

禁止:
- GitHub push / remote 作成 = Type1（外部公開）。CEO 承認まで実行しない。
- commit 著者は `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` を使う（private-author で commit しない）。
- `data/*.db` 削除禁止 / API キーをコード・ログに出さない。

注意:
- git 操作は `git -C ~/Projects/urban-ecosystem` + commit は inline `-c user.name=nexus-ai-2045 -c user.email=nexus-ai-2045@users.noreply.github.com` + sandbox 解除（`git config` 直書きは hook deny される）。
- root commit `a651046` のみ著者 private-author（amend=履歴書換が deny。push 前に再著者化は任意）。
- pyproject.toml 未配置（pytest は `tests/conftest.py` で import 解決 / Pyright の import 警告は静的のみ・runtime は PASS）。urban 専用 pyproject を置くと rootdir が Projects に解決される問題を解消できる。
- urban-ecosystem は Projects monorepo 内にネストした独立 repo。Projects 側に commit を混入させない（過去に staging 誤混入あり → unstage 済み）。
