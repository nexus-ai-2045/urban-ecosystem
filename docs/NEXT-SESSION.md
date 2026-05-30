# Next Session Control Panel — urban-ecosystem

updated: 2026-05-30

方針 (2026-05-29 CEO 確定 / 2026-05-30 更新):
- **ローカルオンリーで開発を進める**。Cloud Run への再デプロイ / 公開切替 / 実 Maps 化 (= Type1) は、公開が必要になった節目まで保留。
- **2026-05-30: GitHub に公開済み** — PUBLIC リポジトリ `github.com/nexus-ai-2045/urban-ecosystem` (著者 nexus-ai-2045)。日本語 README も公開済み。今後の push は**都度 CEO 確認** (Type1)。
- 理由: コアは local だけで完動。実 Google Maps も Vertex/Gemini も local からキー/認証を入れれば使える。Cloud Run の本質価値は「公開URL・常時稼働」だけで開発速度には寄与せず、毎デプロイの Type1 承認ゲートが開発ループを遅くするため。
- Cloud Run 限定デプロイ (revision 00001-t48 / Ready) は最小で完了済みなので捨てない。節目で再デプロイすればよい。

目的:
- 都市地図上で 100 体の AI エージェントが 1 日を過ごす「人工生態系」アプリの MVP。基盤=(将来) Google Cloud Run / 地図=Google Maps JS API / 後段LLM=Vertex AI・Gemini。第一成果物=「100体が Day0 を過ごす 1 日リプレイが動く」← **local で達成済み**。

現在地:
- 🆕 **2026-05-30 realism batch (WO-006..010) 実装・公開済み** (workflow / TDD / 全体 393 passed / 回帰ゼロ):
  - **WO-006 リッチプロフィール**: `AgentProfile` に surname/given + occupation/personality/hobbies/day_pattern を optional 追加。data-contract を v0.3.0 に MINOR 改訂。`generate_urban_sample.py` 拡張 (`--agents 10` 対応)。苗字表示と行動決定LLMの共通土台。
  - **WO-007 苗字キャラ表示**: viewer マーカー glyph = 姓、詳細パネル「姓 名 さん」。`upsertAgents` の tick/run 跨ぎ更新漏れ (既知LOW) も解消。
  - **WO-008 行動決定LLM本体 + 関係理由文**: `choose_destination_category` の context に profile/time を注入。`relationship_reason` を simulation に配線し Gemini 生成。RuleBased 既定で決定論 (byte 一致) 維持 / Vertex は `--llm vertex` opt-in。
  - **WO-009 道路追従移動**: roadnet をルーティンググラフ化 (新規 `environments/urban_2d/road_graph.py`)、最短経路で道路追従。直線貫通を廃止。建物 footprint は取得しない (CEO 確定)。
  - **WO-010 ラベル日本語化**: POIカテゴリ/役割/交流イベント/行動理由を日本語表示 (新規 `tools/urban_viewer/labels.py` / `labels.js`)。内部 JSONL/contract の値は英語コード維持。
  - **10体 viewer fix**: `urban_viewer_server.py` の許可ファイルを `agent_profiles_N*.json` glob 対応 (10体運用の 403 解消 / パストラバーサルは別ガード維持)。
  - commit: `cfc15d2` (realism batch) / `640d07d` (README) — origin/main へ push 済み。
- 🤖 **2026-05-29 LLM エージェント化 (会話生成) 稼働**: spec §10 の `LLMProvider` 抽象。`RuleBasedProvider`(既定/決定論) + `VertexGeminiProvider`(`gemini-2.5-flash` / ADC)。
  - **学び**: (1) Vertex GA は `gemini-2.5-flash`(`2.0-flash` は 404)。(2) 2.5-flash は思考モデル → `thinking_config(thinking_budget=0)` 必須 (無いと max_output_tokens を思考が食い summary が途中切れ)。
  - 実行: `GOOGLE_CLOUD_PROJECT=nexus-ai-2045 python tools/urban_simulation_cli.py run --llm vertex --pois ... --out data/<run>` (ADC + Vertex AI API 有効化済 / SDK `google-genai` venv 導入済)。
- 🚀 **2026-05-29 実データ + 実 Google Maps (CEO 目視「でた」)**: Google Places API (New) で渋谷の実在 POI **435件** → ルールシミュ → **実 Google Maps** (DEMO_MAP_ID / Advanced Markers) で local 表示。commit `a23d3b5`。
  - fetcher: `tools/fetch_places_sample.py` (urllib / key=env / 渋谷 bbox 4タイル searchNearby / cache `data/.places_cache/`)。Places API + Maps JS API は nexus-ai-2045 で有効化済。
  - 環境: `.env` (gitignore) に GOOGLE_PLACES_API_KEY / GOOGLE_MAPS_API_KEY / GOOGLE_MAPS_MAP_ID=DEMO_MAP_ID。`app/main.py` が __main__ で .env を自動 load。
  - 実データ run = `urban_real` (POI 435 / 100 agents)。合成 run = `urban_demo` も併存。
- 独立 git リポジトリ `~/Projects/urban-ecosystem` (branch=main / **remote=origin → github.com/nexus-ai-2045/urban-ecosystem (公開済み)** / 著者 nexus-ai-2045)。
- Cloud Run 限定デプロイ (revision `urban-ecosystem-00001-t48` / Ready / 非公開 / **旧ビューア** / 再デプロイ保留)。
- **ローカル稼働**: `localhost:8080` (BG)。fallback 地図 (Maps key 未設定) で 100 体リプレイ閲覧可。

ローカル起動 (SSOT):
```bash
# venv (初回のみ): python3 -m venv /tmp/urban-venv && /tmp/urban-venv/bin/pip install -r requirements.txt
cd ~/Projects/urban-ecosystem

# (任意) 合成データ 10 体生成:
/tmp/urban-venv/bin/python tools/generate_urban_sample.py --agents 10 --seed 42 --out-dir data/sample

# (任意) 実データ再取得 (.env にキー必須 / 既に data/urban_real があれば不要):
/tmp/urban-venv/bin/python tools/fetch_places_sample.py --out-dir data/urban_real --run-id urban_real

# シミュレーション (合成 10 体の例):
/tmp/urban-venv/bin/python tools/urban_simulation_cli.py run \
  --pois data/sample/pois.geojson --profiles data/sample/agent_profiles_N10.json \
  --aois data/sample/aois.geojson --roadnet data/sample/roadnet.geojson --out data/sample

# サーバー起動 (app/main.py が .env を自動 load → 実 Google Maps):
DATA_DIR="$HOME/Projects/urban-ecosystem/data" PORT=8080 /tmp/urban-venv/bin/python -m app.main
# → http://localhost:8080 で run を選択
# テスト: /tmp/urban-venv/bin/pytest tests/ -q  → 393 passed
```

残論点 (realism batch 後 / 次回):
1. 🛣️ **合成 roadnet が一筆書き (Hamilton chain)**: 道路追従を有効化すると合成データでは迂回が長すぎ 24tick で interaction≈0 (**実 roadnet.geojson では問題なし**)。`generate_urban_sample.py:_build_roads` を距離順スパニングツリー (Prim 等) 化すると改善するが §19.6.2 の rng 消費順が変わり WO-002 byte 一致の再定義が要る → **別 WO 起票推奨**。
2. 🔑 **実 Vertex run の目視確認** (G2 / 課金 / ADC): 実装は mock テスト済み、実 Gemini 出力 (行動決定/関係理由文/会話) は未目視。`GOOGLE_CLOUD_PROJECT=nexus-ai-2045 ... run --llm vertex --agents 10`。
3. 📋 **data-contract に `relationship_reason` 正式追加** (v0.4.0 相当 / 今は未定義フィールド保持で互換)。
4. 🔄 **既存 `agent_profiles_N100.json` 再生成**: profile 拡張で rng 消費順が変わり byte 一致が崩れる (同 seed 再生成で決定論的に復元可)。
5. 🟡 (park / LOW) google adapter `highlight()` の選択解除時、ロール別色 (office_worker=#3498db / student=#f1c40f) に戻さず DEFAULT_ROLE_COLOR にリセットする UX 退行。

次にやる:
1. 残論点 1-4 から選択。優先候補: **roadnet 一筆書き改善** (道路追従でも交流が見えるように) または **実 Vertex run 確認**。
2. その他 local 機能拡張 (viewer UX / 人数可変 UI 露出 / #4 Places フィールド拡充 等)。

実行メモ:
- テストは fastapi が要る。venv: `/tmp/urban-venv`。base 環境では一部テストは importorskip で skip。
- docker はローカル未インストール → 節目の再デプロイ時のみ `gcloud run deploy --source .`。
- viewer の static JS はリクエスト毎に disk から読むため、JS 編集はサーバー再起動不要でブラウザ再読込で反映。
- §9.3「12:00-13:00 全員 lunch」vs §20.5「再評価契機=滞在消化のみ」が衝突。WO-004 は §20.5 優先で実装。厳密化は spec オーナー判断。

証跡:
- commit (2026-05-30): `cfc15d2`(realism batch WO-006..010 + 10体 viewer fix) / `640d07d`(日本語 README) — 著者 nexus-ai-2045 / **origin/main へ push 済み**
- commit (既存): `a6d46dd`(viewer 仕上げ) / `c5ce2fa`(deps+pyproject) / `44abeac`(deploy docs) / `2f9f308`(WO-002) / `2581986`(WO-004) / `c34b333`(WO-003) / `560d416`(WO-004 統合) / `8c6397c`(viewer UX)
- test: venv `pytest tests/ -q` → **393 passed**
- PII チェック (2026-05-30 push 前): 個人情報 / API キー / token / 秘密鍵 = **ゼロ**確認済み。GCP project id `nexus-ai-2045` は事業識別子として露出 (CEO 許容 / 秘密情報ではない)。

禁止:
- Cloud Run 公開切替 = Type1。GitHub push は公開済みだが**都度 CEO 確認** (Type1 / 外部公開)。
- commit 著者は `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` を使う (private-author で commit しない)。
- `data/*.db` 削除禁止 / API キーをコード・ログに出さない。

注意:
- git 操作は `git -C ~/Projects/urban-ecosystem` + commit は inline `-c user.name=nexus-ai-2045 -c user.email=nexus-ai-2045@users.noreply.github.com` (`git config` 直書きは hook deny)。**新規 (untracked) ファイルは先に `git add <path>` が要る** (`commit --` で拾えない)。
- root commit `a651046` のみ別著者 (private-author)。amend (履歴書換) は deny。
- urban-ecosystem は Projects monorepo 内にネストした独立 repo。Projects 側に commit を混入させない (`git -C` で分離操作)。
- README.md は日本語で公開済み。pyproject.toml 配置済み (pytest rootdir 固定 + pyright source roots)。
