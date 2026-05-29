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
  - WO-003 Replay Viewer（`tools/urban_viewer_server.py`+`tools/urban_viewer/`）: FastAPI + Google Maps / キー無し fallback 地図。/api allowlist + path traversal 三重防御 + security headers。`requirements.txt` に fastapi/uvicorn/httpx 追加。
  - **WO-005 Cloud Run（デプロイ可能な状態まで完成 / live gcloud は未実行）**（`a???` 直近 commit）: `app/main.py`(entrypoint・$PORT bind)+`config.py`+`data_access.py`(local実装+GCS stub) / `Dockerfile`(slim・GPU無し・デモrun同梱・秘密非焼込)+`.dockerignore`+`cloudbuild.yaml` / `docs/deploy.md`(gcloud手順・Secret Manager・最小権限SA・Map ID・公開範囲両論併記・Type1警告) / `tests/app/test_main.py`(14)。
- **E2E 確認済み**: generate→simulate→viewer API で全レイヤー 200 配信（agent_states 2400 行 / interactions 395 / traversal 404・403）。
- gh active アカウント = `nexus-ai-2045`（事業用 / private-github-account は非アクティブ保持）。

待ち / 要 CEO 判断:
- **【最重要】WO-005 live デプロイ = Type1（課金・外部公開）**。コード/手順は完成済。実行に要るのは: ① 公開範囲 `--allow-unauthenticated`(公開) か IAP(限定) ② Maps API 有効化 + Map ID 発行(Cloud Console) + Secret 作成 ③ Artifact Registry 作成 + SA 作成 ④ `gcloud run deploy`。手順は `docs/deploy.md`。docker はローカル未インストール（build は Cloud Build / `--source .` で実行）。
- GitHub push（Type1 / 外部公開・repo 名・public/private 未確認）。
- **§9.3「12:00-13:00 全員 lunch」vs §20.5「再評価契機=滞在消化のみ」が衝突**。WO-004 は §20.5 優先で実装 → office_worker/student は lunch に出ず、lunch は other 20 体のみ。§9.3 を厳密化するなら spec オーナー(manager)判断。現状は §20.5 優先で進行。

次にやる（1-3 action）:
1. **WO-005 live デプロイ（Type1 / CEO 承認後）**: `docs/deploy.md` の順で API 有効化→Secret→SA→`gcloud run deploy --source . --region asia-northeast1`→公開 URL で 100 体リプレイ確認（§13.4）。
2. （follow-up / 品質）requirements 分離: runtime に未使用の `Pillow`/`anthropic` を `requirements-dev.txt` 等へ分離しイメージ軽量化（security review MEDIUM/LOW）。`deploy.md` に `--max-instances`/`--concurrency` 追記（公開時の課金防護）。
3. （任意）`pyproject.toml` を urban 直下に置き Pyright の import 警告（静的のみ・runtime PASS）を解消 / GitHub push は CEO に repo 名・public/private 確認後。

実行メモ:
- テストは fastapi が要る。venv: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`（homebrew python は PEP 668）。base 環境では WO-003/005 テストは importorskip で skip。
- docker はローカル未インストール → `docker build` ローカル検証は不可。Cloud Build / `gcloud run deploy --source .` でビルドする。

証跡:
- commit: 2f9f308(WO-002) / 2581986(WO-004) / c34b333(WO-003) / 560d416(WO-004統合) / (WO-005) — 著者 nexus-ai-2045
- test: venv `pytest tests/ -q` → **175 passed** / base homebrew → WO-003/005 skip で残り pass
- E2E smoke: `urban_simulation_cli.py run --sample --out DIR` → viewer TestClient で全レイヤー 200 / agent_states 2400 行 / security headers(nosniff/DENY) 付与

禁止:
- GitHub push / remote 作成 = Type1（外部公開）。CEO 承認まで実行しない。
- commit 著者は `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` を使う（private-author で commit しない）。
- `data/*.db` 削除禁止 / API キーをコード・ログに出さない。

注意:
- git 操作は `git -C ~/Projects/urban-ecosystem` + commit は inline `-c user.name=nexus-ai-2045 -c user.email=nexus-ai-2045@users.noreply.github.com` + sandbox 解除（`git config` 直書きは hook deny される）。
- root commit `a651046` のみ著者 private-author（amend=履歴書換が deny。push 前に再著者化は任意）。
- pyproject.toml 未配置（pytest は `tests/conftest.py` で import 解決 / Pyright の import 警告は静的のみ・runtime は PASS）。urban 専用 pyproject を置くと rootdir が Projects に解決される問題を解消できる。
- urban-ecosystem は Projects monorepo 内にネストした独立 repo。Projects 側に commit を混入させない（過去に staging 誤混入あり → unstage 済み）。
