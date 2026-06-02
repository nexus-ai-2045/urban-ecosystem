# Next Session Control Panel — urban-ecosystem

updated: 2026-06-03

## 2026-06-03 セッション最新状態

### GitHub / 公開協業

- **公開名義**: GitHub の公開面は `nexus-ai-2045` に統一する。個人アカウントの token / 名義を公開協業の正本にしない。
- **公開正本**: GitHub docs / issues / PRs。Linear は Nexus maintainer 側の内部管理。
- **現在の公開入口**: GitHub issue #11 の fallback viewer レビューのみ。#10 / #12 は baseline complete で close、#13 は Discord freeze 方針で close。
- **#11 の入口**: issue 本文先頭に「1分で反応する場合」を追加済み。コードを書かなくても、smoke 結果・分かりにくい場所・環境だけコメントできる。
- **fallback smoke 導線**: `README.md` / `docs/good-first-issues.md` / `docs/public-collaboration-status.md` / `docs/public-collaboration-runbook.md` / `docs/maintainer-quick-guide.md` に `python tools/smoke_fallback_viewer.py` を反映済み。
- **Discord**: 一旦フリーズ。webhook 作成、GitHub secret 設定、Actions 手動実行、Discord 投稿は行わない。
- **Discord docs**: `docs/discord-pr-notifications.md` は再開時参照であり、現時点の作業指示ではないと明記済み。
- **Repo subtitle**: GitHub repository description は「渋谷の街を舞台にした、決定論的な都市エージェント・シミュレーション。」に設定済み。
- **ローカル状態**: 2026-06-03 時点で `main` は `origin/main` と一致。open PR はなく、open issue は #11 のみ。

### 直近 merge 済み PR (公開協業入口)

- **#41**: `docs/good-first-issues.md` に #11 の API キーなし fallback smoke 導線を追加。
- **#42**: `docs/public-collaboration-status.md` に同じ smoke 導線を追加。
- **#43**: maintainer quick guide / public collaboration runbook に参加者向け smoke 導線を追加。
- **#44**: Discord 通知手順を、現在実行する手順ではなく再開時参照として明確化。

### 既存 batch (WO-011..013) — 完了済み (398 passed)
- **WO-011 (#1 roadnet)** `a86780c`: `_build_roads` を Prim法MST化。道路追従で interactions 0→976。rng消費位置保存で agent_profiles byte 不変。review: approve。
- **WO-012 (#3 contract v0.4.0)** `1cddf6d`: `relationship_reason` を optional 正式化 + `enable_summaries=False` 空文字バグを `if reason:` ガードで根本修正 + 回帰テスト。
- **WO-013 (#5 highlight)** `16758fe`: highlight解除で role別色復元。review: approve。既知 park-LOW: 既存マーカー更新パスは role色再保存しない (role不変前提で実害なし)。

### 課金安全性 (CEO 確認済 / 2026-05-31)
- **デフォルト = 完全無料 / Google Cloud 課金ゼロ**。第三者が clone しても opt-in しない限り課金経路に入らない。
  - Vertex: `--llm rule` 既定 (API 呼ばない)。`--llm vertex` + `GOOGLE_CLOUD_PROJECT` + `google-genai` の三重ゲート。
  - Maps: `hasApiKey=false` → FallbackMapAdapter (canvas/課金ゼロ)。Maps script 自体出力されない。
  - `.env` gitignore 済 (`git check-ignore .env`=0) / 追跡ファイルに env系なし。
- README に課金境界セクションを反映済み。

### 実 Vertex run (#2) — 未実施 (課金/G2)
- 私が試行した run は **CLI フラグ誤り (`--llm-summaries`/`--project`/`--model` は存在しない) で argparse 段階で失敗 → Gemini API 未到達 → 課金ゼロ**。
- 正しいコマンド: `GOOGLE_CLOUD_PROJECT=<proj> /tmp/urban-venv/bin/python tools/urban_simulation_cli.py run --llm vertex --pois data/sample/pois.geojson --profiles data/sample/agent_profiles_N10.json --aois data/sample/aois.geojson --roadnet data/sample/roadnet.geojson --ticks 24 --seed 42 --out data/run_vertex_check`
- ADC quota project = `windws-497319` (`~/.config/gcloud/application_default_credentials.json`)。実行は課金イベントなので CEO 明示 GO 後に。

### その他残
- #11 fallback viewer レビューを公開協業の現役入口として維持する。
- GCP / Cloud Run 実機確認は外部影響・課金・公開リスクを伴うため、maintainer 明示承認後に行う。
- #4 N100 再生成 = コード不要 (data は gitignore で都度生成)。
- WO-013 medium (将来 role 可変化時に既存パス同期追加)。

---

(以下は 2026-05-30 までの記録 / 旧 Control Panel は git 履歴参照)

## 方針 (2026-05-29 CEO 確定)
- ローカルオンリーで開発。Cloud Run 再デプロイ / 公開切替 = 要承認 (保留)。
- GitHub は PUBLIC 公開済み (`github.com/nexus-ai-2045/urban-ecosystem` / 著者 nexus-ai-2045)。push は都度 maintainer 確認。
- commit 著者は `nexus-ai-2045 <nexus-ai-2045@users.noreply.github.com>` 固定。private-author で commit しない。
- `data/*.db` 削除禁止 / API キーをコード・ログに出さない。
- git 操作は `cd ~/Projects/public/urban-ecosystem` 後に実行。commit は inline `-c user.name=nexus-ai-2045 -c user.email=nexus-ai-2045@users.noreply.github.com`。新規ファイルは先に `git add`。
