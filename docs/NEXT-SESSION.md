# Next Session Control Panel — urban-ecosystem

updated: 2026-05-29

目的:
- 都市地図上で 100 体の AI エージェントが 1 日を過ごす「人工生態系」アプリの MVP を作る。基盤=Google Cloud Run / 地図=Google Maps JS API / 後段LLM=Vertex AI・Gemini。第一成果物=「100体が Day0 を過ごす1日リプレイが Cloud Run で動く」。

現在地:
- 独立 git リポジトリ `~/Projects/urban-ecosystem`（branch=main / remote 未設定）。
- 仕様確定: spec の解決可能 assumption は全て [事実] 化。残 [実装時確定] 2 件（再生fps / 完走時間 = 実測のみ）。
- **WO-001〜004 実装 + commit 済み**（著者 nexus-ai-2045 / `2f9f308` WO-002 / `2581986` WO-004 / `c34b333` WO-003 / `560d416` WO-004 統合修正）。
  - WO-001 Data Loader: models + GeoJSON/JSONL loader + validation。
  - WO-002 Sample Data Generator（`tools/generate_urban_sample.py`）: 静的データのみ = §19 準拠（scope 2026-05-29 CEO 確定 / 挙動ログは WO-004）。同一 seed で静的 4 ファイル sha256 byte 一致。`data/` を .gitignore 追加。
  - WO-004 Rule Simulation（`environments/urban_2d/rules.py`+`simulation.py` / `tools/urban_simulation_cli.py`）: §9/§20 ルールベース。3 jsonl byte 一致 / §13.3.3 invariant 全件 / 100agent×192tick=0.43s。`--sample` は静的+挙動の 8 ファイルを 1 コマンドで出力（自己完結 replay run）。
  - WO-003 Replay Viewer（`tools/urban_viewer_server.py`+`tools/urban_viewer/`）: FastAPI + Google Maps / キー無し fallback 地図。/api allowlist + path traversal 三重防御。`requirements.txt` に fastapi/uvicorn/httpx 追加。
- **E2E 確認済み**: generate→simulate→viewer API で全レイヤー 200 配信（agent_states 2400 行 / interactions 395 / traversal 404・403）。
- gh active アカウント = `nexus-ai-2045`（事業用 / private-github-account は非アクティブ保持）。

待ち / 要 CEO 判断:
- GitHub push（Type1 / 外部公開・repo 名・public/private 未確認）。
- **§9.3「12:00-13:00 全員 lunch」vs §20.5「再評価契機=滞在消化のみ」が衝突**。WO-004 は §20.5 優先で実装 → office_worker/student は lunch に出ず、lunch は other 20 体のみ。リプレイで「会社員が昼に動かない」絵になる。§9.3 を厳密化するなら spec オーナー(manager)判断。現状は §20.5 優先で進行。

次に読む（WO-005 着手時 / GCP）:
- `docs/subagents/work-orders/wo-urban-005-cloud-run-deploy.yaml`
- `docs/ai-ecosystem-tool-spec.md` §17 デプロイ基盤 / §16#6 Map ID / §13.4 デプロイ検証
- `docs/subagents/contracts/urban-ecosystem-data-contract.md`（データ正本 v0.2）

次にやる（1-3 action）:
1. **WO-URBAN-005 Cloud Run Deploy**（GCP 連携の段）: Dockerfile / cloudbuild / `app/main.py` 化 → nexus-ai-2045 にデプロイ。Maps API 有効化・Map ID 発行 (Cloud Console)・Secret Manager 注入・公開範囲 (未認証/IAP) は **Type1（課金・外部公開）→ CEO 承認必須**。
2. （任意 / 品質）`pyproject.toml` を urban-ecosystem 直下に置き rootdir を urban に解決 → Pyright の import 警告（静的のみ・runtime PASS）を解消。
3. GitHub push する場合は CEO に repo 名・public/private を確認してから（著者 nexus-ai-2045）。

実行メモ:
- テストは fastapi が要る（WO-003）。venv 例: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`（homebrew python は PEP 668 で system pip 不可）。base 環境（fastapi 無し）では WO-003 テストは importorskip で skip され壊れない。

証跡:
- commit: 2f9f308(WO-002) / 2581986(WO-004) / c34b333(WO-003) / 560d416(WO-004 統合) — いずれも著者 nexus-ai-2045
- test: venv `pytest tests/ -q` → **161 passed** / base homebrew → **115 passed, 1 skipped**（WO-003 skip）
- E2E smoke: `urban_simulation_cli.py run --sample --out DIR` → viewer TestClient で全 6 種ファイル 200 / agent_states 2400 行

禁止:
- GitHub push / remote 作成 = Type1（外部公開）。CEO 承認まで実行しない。
- commit 著者は `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` を使う（private-author で commit しない）。
- `data/*.db` 削除禁止 / API キーをコード・ログに出さない。

注意:
- git 操作は `git -C ~/Projects/urban-ecosystem` + commit は inline `-c user.name=nexus-ai-2045 -c user.email=nexus-ai-2045@users.noreply.github.com` + sandbox 解除（`git config` 直書きは hook deny される）。
- root commit `a651046` のみ著者 private-author（amend=履歴書換が deny。push 前に再著者化は任意）。
- pyproject.toml 未配置（pytest は `tests/conftest.py` で import 解決 / Pyright の import 警告は静的のみ・runtime は PASS）。urban 専用 pyproject を置くと rootdir が Projects に解決される問題を解消できる。
- urban-ecosystem は Projects monorepo 内にネストした独立 repo。Projects 側に commit を混入させない（過去に staging 誤混入あり → unstage 済み）。
