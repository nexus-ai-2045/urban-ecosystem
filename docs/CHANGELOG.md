# 改訂サマリ — urban-ecosystem 仕様統合

対象: 5観点の提案を統合し、3ファイルを全面改訂 (+ 旧 video WO を Cloud Run WO へ置換)。
確定方針: 動画/音声/音声認識(STT)系を完全削除。実行基盤=Cloud Run / 地図=Google Maps JS API / 後段LLM=Vertex AI・Gemini (MVPはルールベース)。

## 全体方針 (3ファイル共通)

- 音声認識・動画取り込み・仕様自動生成に関する記述・出力ファイル・モジュール・CLI・検証・マイルストーン・WO・外部部品を全て除去した。将来機能としても残していない。
- 音声認識ベンダー名・関連 API キー名・出力名・関連モジュール名などの禁止語を出力ファイルから完全排除した。参照資料は元動画の URL・投稿日のみ残し、取り込み機能には触れていない。
- LLM プロバイダ列挙を Vertex AI / Gemini + ルールベースモックに統一。直接呼び出し禁止・Provider 抽象越し方針を明記した。

## ai-ecosystem-tool-spec.md

- 第一成果物を「Cloud Run 上の100体1日リプレイ」と明示。MVPスコープから動画系を削除し、合成データ生成・Cloud Run 配信・fallback 地図を追加。
- §5: Google Maps ロードフロー (importLibrary / Map ID 必須)、tick 位置更新のパフォーマンス方針、fallback 地図 (CI主経路)、フロント状態管理 (ViewerState / 一方向データフロー) を新設。リプレイ一次ソースを `agent_states.jsonl` に確定。
- §6: データモデルを GeoJSON Feature 構造に統一 (lat/lon は coordinates に一元化、座標2系統を明記)、必須/任意を data-contract と一致させ、正本を data-contract に降格。
- §7: STT系3出力ファイルを削除し、`relationships.jsonl` (任意) を追加。
- §9: 行動ルールを全面詳細化 (時間モデル / status 状態機械 / 時刻帯×role テーブル / 目的地選択 / 直線補間移動 / 滞在時間 / 近接判定 / interaction 発生確率 / relationship 遷移 / social_networks バイアス / 定数)。
- §10: 旧プロバイダ列挙 (汎用 LLM ベンダー4種) を削除し Vertex AI/Gemini + ルールベースに。Provider シグネチャを補強。
- §11/§12: 動画要件抽出モジュールとその CLI を削除。Cloud Run 向け構成 (app/ + environments/ + tools/ + Dockerfile) に再編。
- §13: 動画要件抽出検証を削除し、データ検証強化版 + デプロイ検証 (Cloud Run) を追加。
- §14/§15: 受け入れ基準から動画系2行を削除し Cloud Run 基準を追加。Milestone 4 を「Cloud Run デプロイ」に置換、旧M5/M6 を Vertex AI 前提でリナンバー。
- §16: 動画未決を削除。基盤系を回答済みに整理し、Map ID 発行・fallback 投影の2論点を追加。
- §17 デプロイ基盤 (Cloud Run Service/Job、データ経路、API、Secrets/IAM、Dockerfile)、§18 テスト戦略を新設。

## ai-ecosystem-implementation-orchestration.md

- 正本リストから音声認識出力・要件トレース系の参照を削除。
- Workstreams: S5 を「Video Requirements CLI」から「Cloud Run Deploy」(devops + quality-gate / depends on S3,S4) へ置換。S6 を Vertex AI/Gemini 前提に修正。
- 推奨実装順を S1-S5 に整理し、第一成果物を Cloud Run リプレイと定義。
- Architecture Guardrails を Cloud Run 単独デプロイ前提に書き換え (app→environments 依存、Secret Manager/Workload Identity、GCS)。
- Adopted Building Blocks の Speech-to-text 行を削除し、FastAPI / Cloud Run / Cloud Storage / Vertex AI 行を追加。
- Parallelization Rules / Human Gates (G1 に contract MAJOR、G4 に本番デプロイ) を整合。
- WO-URBAN-002/003/004 の acceptance を data-contract 参照で厳密化。WO-URBAN-005 を Cloud Run Deploy に全面置換。
- Definition of Done に E2E (fallback) を追加。

## wo-urban-005-cloud-run-deploy.yaml (旧 wo-urban-005-video-requirements-cli.yaml を置換)

- id を `wo-urban-005-cloud-run-deploy` に変更。音声認識ベンダー名・関連 API キー名・出力名・動画系の語を一切含まない。
- goal を「viewer+sim を Cloud Run Service にコンテナ化デプロイ、大規模 sim は同一イメージの Cloud Run Job」に再定義。
- allowed_write_paths を Dockerfile / cloudbuild.yaml / requirements.txt / app/* / docs/deploy.md / tests/app/test_main.py に。
- depends_on を WO-003 / WO-004 に設定。acceptance を health/fallback/secret/最小権限/デプロイ再現性/Service・Job 整合に。
- out_of_scope に「APIキーをイメージ・git・ログに焼かない」「GPU/メディア依存を含めない」「fallback はキー無しで動く」を明記。
