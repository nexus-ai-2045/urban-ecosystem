# Next Session Control Panel — urban-ecosystem

updated: 2026-05-29

方針 (2026-05-29 CEO 確定):
- **ローカルオンリーで開発を進める**。Cloud Run への再デプロイ / 公開 / 実 Maps 化 (= Type1) は、公開が必要になった節目まで保留。
- 理由: コアは local だけで完動。実 Google Maps も Vertex/Gemini も local からキー/認証を入れれば使える。Cloud Run の本質価値は「公開URL・常時稼働」だけで開発速度には寄与せず、毎デプロイの Type1 承認ゲートが開発ループを遅くするため。
- Cloud Run 限定デプロイ (revision 00001-t48 / Ready) は最小で完了済みなので捨てない。節目で再デプロイすればよい。

目的:
- 都市地図上で 100 体の AI エージェントが 1 日を過ごす「人工生態系」アプリの MVP。基盤=(将来) Google Cloud Run / 地図=Google Maps JS API / 後段LLM=Vertex AI・Gemini。第一成果物=「100体が Day0 を過ごす 1 日リプレイが動く」← **local で達成済み**。

現在地:
- 🤖 **2026-05-29 LLM エージェント化 (会話生成) 稼働**: spec §10 の `LLMProvider` 抽象を実装。`RuleBasedProvider`(既定/決定論) + `VertexGeminiProvider`(Gemini `gemini-2.5-flash` / ADC)。interaction の会話要約を実 Gemini 生成 → run `urban_real_llm` (POI 435 / interactions 184 / 全 summary が Gemini フル文)。commit `46b1396`/`cc1eedd`/`96b104d`。
  - **学び**: (1) Vertex の GA は `gemini-2.5-flash`(`2.0-flash` は 404)。(2) 2.5-flash は思考モデル → `thinking_config(thinking_budget=0)` 必須 (無いと max_output_tokens を思考が食い summary が ~16字で途中切れ)。
  - 決定論維持: RuleBased 既定で agent_states/interaction_events byte 一致 (249 passed)。Gemini は `--llm vertex` opt-in。実 LLM はテスト非経路 (mock)。
  - 実行: `GOOGLE_CLOUD_PROJECT=nexus-ai-2045 python tools/urban_simulation_cli.py run --llm vertex --pois ... --out data/<run>` (ADC + Vertex AI API 有効化済 / SDK `google-genai` venv 導入済)。
  - 残 LLM 対象 (§10.2): 行動決定 / 関係理由文の Gemini 化は未着手 (会話生成のみ稼働)。
- 🚀 **2026-05-29 実データ + 実 Google Maps 反映 (CEO 目視確認済「でた」)**: Google Places API (New) で渋谷の実在 POI **435件**取得 → ルールシミュ (interactions 184) → **実 Google Maps** (DEMO_MAP_ID / Advanced Markers) 上で local 表示。commit `a23d3b5` + app.js durable 化。
  - fetcher: `tools/fetch_places_sample.py` (urllib stdlib / key=env / 渋谷 bbox 4タイル searchNearby / cache `data/.places_cache/` / `--dry-run`)。Places API + Maps JS API は nexus-ai-2045 で有効化済。
  - 配線 fix: `/static/app.js` を StaticFiles mount より前の templating route にしてキー/Map ID を注入 (旧: raw 配信で placeholder 残り fallback 固定だった)。
  - 環境: `.env` (gitignore) に GOOGLE_PLACES_API_KEY / GOOGLE_MAPS_API_KEY (同値1本 / Places+MapsJS に API 制限) / GOOGLE_MAPS_MAP_ID=DEMO_MAP_ID。`app/main.py` が __main__ で .env を自動 load (Cloud Run は no-op)。
  - 実データ run = `urban_real` (POI 435 / interactions 184 / 100 agents)。合成 run = `urban_demo` も併存。
  - 既知 LOW: `fetch_places_sample.py` に未使用 helper (`_poi_feature` / `_places_type_to_category`) が残存 (Pyright)。動作影響なし / 次回削除候補。
- 独立 git リポジトリ `~/Projects/urban-ecosystem` (branch=main / remote 未設定 / 著者 nexus-ai-2045)。
- **2026-05-29 仕上げ session (workflow)**: 3 commit 追加。
  - `a6d46dd` refactor(viewer): CATEGORY_COLORS を `colors.js` (ES module SSOT / Object.freeze) に集約し 3 ファイル重複を解消 / google adapter の `highlight()` 実装・`upsertAgents` await・`_waitForGoogleMaps` 10s timeout / **HIGH bug fix** = 非表示後に再出現した agent が永続非表示になる問題を修正 (`marker.map` 復元 + pin 参照保持)。
  - `c5ce2fa` chore(deps): 未使用依存 (Pillow/anthropic/numpy/matplotlib/pyyaml/requests/python-dotenv) 削除 / runtime=fastapi・uvicorn・httpx + dev=pytest のみ / `pyproject.toml` 追加 (pytest rootdir 固定 + pyright source roots)。
  - `44abeac` docs(deploy): `--max-instances`/`--concurrency` 推奨レンジ + SA ハードニング (build/run SA 分離・最小権限) 追記。
  - workflow 検証: venv pytest **175 passed** (回帰なし) / 並列レビュー = deps・docs は adopt / viewer-js の HIGH 指摘は本 session で修正済み。
- WO-001〜005 実装 + commit 済み (既存)。E2E: generate→simulate→viewer 全レイヤー 200 (agent_states 2400 行 / interactions 395)。
- Cloud Run 限定デプロイ (revision `urban-ecosystem-00001-t48` / Ready / 非公開 / fallback 地図) は live 稼働中だが **旧ビューア** (今回の仕上げは未反映 = local-only 方針で再デプロイ保留)。
- **ローカル稼働中**: `localhost:8080` (BG)。fallback 地図 (Maps key 未設定) で 100 体リプレイ閲覧可。

ローカル起動 (SSOT):
```bash
# venv (初回のみ): python3 -m venv /tmp/urban-venv && /tmp/urban-venv/bin/pip install -r requirements.txt
cd ~/Projects/urban-ecosystem

# (任意) 実データ再取得 + シミュ (.env にキー必須 / 既に data/urban_real があれば不要):
/tmp/urban-venv/bin/python tools/fetch_places_sample.py --out-dir data/urban_real --run-id urban_real
/tmp/urban-venv/bin/python tools/urban_simulation_cli.py run \
  --pois data/urban_real/pois.geojson --profiles data/urban_real/agent_profiles_N100.json \
  --aois data/urban_real/aois.geojson --roadnet data/urban_real/roadnet.geojson --out data/urban_real

# サーバー起動 (app/main.py が .env を自動 load → 実 Google Maps):
DATA_DIR="$HOME/Projects/urban-ecosystem/data" PORT=8080 /tmp/urban-venv/bin/python -m app.main
# → http://localhost:8080 で run_id=urban_real を選択 = 実渋谷 Google Maps + 実 POI 435
# テスト: /tmp/urban-venv/bin/pytest tests/ -q  → 214 passed
```

待ち / 保留 (local-only 方針で当面やらない):
- 実 Google Maps 化: local で見たいだけなら `GOOGLE_MAPS_API_KEY` を env に入れれば実タイル表示 (Cloud Run 不要)。Maps API 有効化 + Map ID 発行 (Cloud Console) が前提。
- Cloud Run 再デプロイ / 公開切替 / GitHub push: いずれも Type1 / 公開が必要になった節目で CEO 実行。手順は `docs/deploy.md`。
- **§9.3「12:00-13:00 全員 lunch」vs §20.5「再評価契機=滞在消化のみ」が衝突**。WO-004 は §20.5 優先で実装 (office_worker/student は lunch に出ず、lunch は other 20 体のみ)。厳密化は spec オーナー (manager) 判断。現状は §20.5 優先で進行。

次にやる (local-first):
1. (優先軸 = ローカル主で開発加速) 次の機能/調整を local で回す。候補: LLM エージェント化 (Vertex/Gemini で WO-004 のルールベース挙動を拡張) / 実 Maps を local キーで確認 / viewer UX の追加改善。
2. (park / LOW) google adapter `highlight()` の選択解除時、ロール別色 (office_worker=#3498db / student=#f1c40f) に戻さず DEFAULT_ROLE_COLOR にリセットしている UX 退行。`upsertAgents` 時の role を pin に保持する設計で対処 (次スプリント)。

実行メモ:
- テストは fastapi が要る。venv: `/tmp/urban-venv`。base 環境では WO-003/005 テストは importorskip で skip。
- docker はローカル未インストール → 節目の再デプロイ時のみ Cloud Build / `gcloud run deploy --source .` でビルド。
- viewer の static JS はリクエスト毎に disk から読むため、JS 編集はサーバー再起動不要でブラウザ再読込で反映。

証跡:
- commit (今回): `a6d46dd`(viewer 仕上げ) / `c5ce2fa`(deps+pyproject) / `44abeac`(deploy docs) — 著者 nexus-ai-2045
- commit (既存): `2f9f308`(WO-002) / `2581986`(WO-004) / `c34b333`(WO-003) / `560d416`(WO-004 統合) / `8c6397c`(viewer UX)
- test: venv `pytest tests/ -q` → **175 passed**
- local live: `curl localhost:8080/api/health` = `{"status":"ok","maps_key":"absent","data_source":"local"}` / `/api/runs` = urban_demo (100 agents / 24 ticks / interactions 395)

禁止:
- GitHub push / remote 作成 / Cloud Run 公開切替 = Type1 (外部公開)。CEO 承認まで実行しない。
- commit 著者は `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` を使う (private-author で commit しない)。
- `data/*.db` 削除禁止 / API キーをコード・ログに出さない。

注意:
- git 操作は `git -C ~/Projects/urban-ecosystem` + commit は inline `-c user.name=nexus-ai-2045 -c user.email=nexus-ai-2045@users.noreply.github.com` (`git config` 直書きは hook deny)。**新規 (untracked) ファイルは `commit --` で拾えないため、先に `git add <path>` が要る**。
- root commit `a651046` のみ著者 private-author (amend=履歴書換が deny。push 前に再著者化は任意)。
- urban-ecosystem は Projects monorepo 内にネストした独立 repo。Projects 側に commit を混入させない (status -s に出ず分離済み)。
- pyproject.toml 配置済み (pytest rootdir を urban-ecosystem に固定)。
