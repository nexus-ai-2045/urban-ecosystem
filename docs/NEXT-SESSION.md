# Next Session Control Panel — urban-ecosystem

updated: 2026-05-31

## 2026-05-31 セッション最新状態 (要対応あり)

### gh 認証 (CEO 指示 / 2026-05-31 完了)
- **CEO 方針**: push 認証も commit 名義も **`nexus-ai-2045`** に統一する。個人アカウントの token は使わない。
- 確認済 `[事実: gh api]`: 公開履歴に個人アカウント名は出ていない (commit author/committer.login=nexus-ai-2045 / contributors=nexus-ai-2045 のみ)。
- **対応済**: `gh auth login --web` で nexus-ai-2045 を追加 → `gh auth switch --user nexus-ai-2045`。gh active=nexus-ai-2045。`df5afb7..8776033` を nexus-ai-2045 認証で push 成功 (個人 token 不使用)。以降の push もこの認証。

### 未 push のローカル変更
- **未 commit (working tree)**:
  - `README.md` — 課金境界の明示追記 (デフォルト無料 / Vertex・Maps・Places は自分で env 設定したときのみ自分の GCP に課金 / opt-in 三重ゲート)。**staged 済み・commit 未実行**。
  - `tools/urban_viewer/colors.js` (未使用 ROLE_COLORS export = dead code) + `tools/urban_viewer/styles.css` (再生ボタン装飾) — 前回 viewer 作業の残骸。CEO 指示で保留中。
- **ローカル commit 済み / origin に push 済み (df5afb7 時点)**: WO-011/012/013 + 前回 viewer 装飾。origin/main=df5afb7 で local と一致 (push 完了確認済)。
  - ※ README 課金追記 commit を入れると origin より 1 commit 先行になる → 次の push 対象。

### 残論点 batch (WO-011..013) — 完了済み (398 passed)
- **WO-011 (#1 roadnet)** `a86780c`: `_build_roads` を Prim法MST化。道路追従で interactions 0→976。rng消費位置保存で agent_profiles byte 不変。review: approve。
- **WO-012 (#3 contract v0.4.0)** `1cddf6d`: `relationship_reason` を optional 正式化 + `enable_summaries=False` 空文字バグを `if reason:` ガードで根本修正 + 回帰テスト。
- **WO-013 (#5 highlight)** `16758fe`: highlight解除で role別色復元。review: approve。既知 park-LOW: 既存マーカー更新パスは role色再保存しない (role不変前提で実害なし)。

### 課金安全性 (CEO 確認済 / 2026-05-31)
- **デフォルト = 完全無料 / Google Cloud 課金ゼロ**。第三者が clone しても opt-in しない限り課金経路に入らない。
  - Vertex: `--llm rule` 既定 (API 呼ばない)。`--llm vertex` + `GOOGLE_CLOUD_PROJECT` + `google-genai` の三重ゲート。
  - Maps: `hasApiKey=false` → FallbackMapAdapter (canvas/課金ゼロ)。Maps script 自体出力されない。
  - `.env` gitignore 済 (`git check-ignore .env`=0) / 追跡ファイルに env系なし。
- README に課金境界セクションを追記 (上記 未commit)。

### 実 Vertex run (#2) — 未実施 (課金/G2)
- 私が試行した run は **CLI フラグ誤り (`--llm-summaries`/`--project`/`--model` は存在しない) で argparse 段階で失敗 → Gemini API 未到達 → 課金ゼロ**。
- 正しいコマンド: `GOOGLE_CLOUD_PROJECT=<proj> /tmp/urban-venv/bin/python tools/urban_simulation_cli.py run --llm vertex --pois data/sample/pois.geojson --profiles data/sample/agent_profiles_N10.json --aois data/sample/aois.geojson --roadnet data/sample/roadnet.geojson --ticks 24 --seed 42 --out data/run_vertex_check`
- ADC quota project = `windws-497319` (`~/.config/gcloud/application_default_credentials.json`)。実行は課金イベントなので CEO 明示 GO 後に。

### その他残
- #4 N100 再生成 = コード不要 (data は gitignore で都度生成)。
- WO-013 medium (将来 role 可変化時に既存パス同期追加)。

---

(以下は 2026-05-30 までの記録 / 旧 Control Panel は git 履歴参照)

## 方針 (2026-05-29 CEO 確定)
- ローカルオンリーで開発。Cloud Run 再デプロイ / 公開切替 = Type1 (保留)。
- GitHub は PUBLIC 公開済み (`github.com/nexus-ai-2045/urban-ecosystem` / 著者 nexus-ai-2045)。push は都度 CEO 確認 (Type1)。
- commit 著者は `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` 固定。private-author で commit しない。
- `data/*.db` 削除禁止 / API キーをコード・ログに出さない。
- git 操作は `cd ~/Projects/urban-ecosystem` 後に実行。commit は inline `-c user.name=nexus-ai-2045 -c user.email=nexus-ai-2045@users.noreply.github.com`。新規ファイルは先に `git add`。
