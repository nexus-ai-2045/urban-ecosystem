# 都市 AI エージェント人工生態系 (urban-ecosystem)

渋谷の街を舞台にした、決定論的な都市エージェント・シミュレーション。

都市の地図上で、多数の AI エージェントが一日を過ごす「人工生態系」シミュレーションです。
渋谷の実在スポットを舞台に、住人エージェントが通勤・昼食・買い物・交流・帰宅を行い、
その 1 日を地図ビューアでリプレイできます。

## 特徴

- 🗺️ **実 Google Maps + 実渋谷 POI**。API キーが無くても fallback 地図で動く（CI / テスト主経路）。
- 🎲 **決定論シミュレーション**。同一 seed で出力がバイト一致で再現する。
- 🛣️ **道路追従の移動**。道路ネットワークをグラフ化し最短経路で移動するため、建物や道路を直線で貫通しない。
- 👥 **リッチプロフィール**。姓名・職業・性格・趣味・1 日の行動傾向を持つ。
- 🏷️ **苗字ベースのキャラ表示と日本語ラベル**。マーカーは姓（例「井上」）、カテゴリ/役割/交流は日本語表示。
- 🤖 **LLM 連携（Vertex AI Gemini / opt-in）**。会話要約・行動決定・関係変化の理由文を生成。既定はルールベースで LLM 不要でも完動。

## アーキテクチャ

| ディレクトリ | 役割 |
|---|---|
| `app/` | FastAPI web サーバー（リプレイ配信 / API / LLM プロバイダ抽象） |
| `environments/urban_2d/` | シミュレーション中核（データモデル・行動ルール・道路グラフ） |
| `tools/` | データ生成・シミュレーション CLI・地図ビューア |
| `docs/` | 仕様書（spec）・データ契約・作業指示書（WO） |
| `tests/` | pytest（ユニット / 統合 / API） |

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

依存は最小構成（runtime = fastapi / uvicorn / httpx、dev = pytest）。
Vertex AI Gemini を使う場合のみ `pip install google-genai`（遅延 import のため通常は不要）。

## 使い方

### 1. データ生成

合成データ（API キー不要）:

```bash
python tools/generate_urban_sample.py --agents 10 --seed 42 --out-dir data/sample
```

このコマンドで、次のシミュレーション手順に使う `data/sample/agent_profiles_N10.json` も生成されます。`--agents` の値を変えた場合は、生成される profile file 名の `N10` 部分も変わります。

実渋谷データ（Google Places API / `.env` にキーが必要）:

```bash
python tools/fetch_places_sample.py --out-dir data/urban_real --run-id urban_real
```

### 2. シミュレーション

```bash
python tools/urban_simulation_cli.py run \
  --pois data/sample/pois.geojson \
  --profiles data/sample/agent_profiles_N10.json \
  --aois data/sample/aois.geojson \
  --roadnet data/sample/roadnet.geojson \
  --out data/sample
```

LLM（Vertex Gemini）を使う場合は opt-in で `--llm vertex` を付与:

```bash
GOOGLE_CLOUD_PROJECT=<your-project> python tools/urban_simulation_cli.py run --llm vertex \
  --pois data/sample/pois.geojson \
  --profiles data/sample/agent_profiles_N10.json \
  --aois data/sample/aois.geojson \
  --roadnet data/sample/roadnet.geojson \
  --out data/sample
```

### 3. ビューア起動

```bash
DATA_DIR="$PWD/data" PORT=8080 python -m app.main
# → http://localhost:8080 で run を選択してリプレイ
```

`GOOGLE_MAPS_API_KEY` が未設定なら fallback 地図、設定済みなら実 Google Maps タイルで表示されます。
リポジトリ直下の `.env` は既定では読み込みません。ローカル開発で `.env` を使う場合だけ、`URBAN_ECOSYSTEM_LOAD_DOTENV=1` を明示してください。
API キーなしの再現性レビューでは、`GOOGLE_MAPS_API_KEY` / `GOOGLE_PLACES_API_KEY` / `GOOGLE_CLOUD_PROJECT` を未設定にした状態で起動してください。

## テスト

```bash
pip install -r requirements.txt
python -m pytest tests -q -m "not requires_api"
```

fallback フロント E2E もローカルで走らせる場合:

```bash
python -m playwright install chromium
unset GOOGLE_MAPS_API_KEY GOOGLE_PLACES_API_KEY GOOGLE_CLOUD_PROJECT
python -m pytest tests/e2e -q
```

GitHub Actions の CI も同じく API キーなしで Chromium を入れ、fallback 地図経路を検証します。

## 課金について（重要）

**このリポジトリはデフォルトで完全無料です。Google Cloud の課金は一切発生しません。**

課金が発生するのは、**あなた自身が明示的に Google Cloud の API キー / プロジェクトを設定した場合のみ**です。設定すると、その課金は**あなた自身の Google Cloud アカウント**に対して発生します（リポジトリ作者には課金されません）。

| 機能 | デフォルト（無料） | 課金が発生する明示操作 | 課金先 |
|---|---|---|---|
| シミュレーション | ルールベース（LLM 呼び出しなし） | `--llm vertex` + `GOOGLE_CLOUD_PROJECT` を**自分で**設定 | 自分の GCP |
| 地図表示 | fallback 地図（canvas 描画） | `GOOGLE_MAPS_API_KEY` を**自分で**設定 | 自分の GCP |
| POI 取得 | 同梱データ / 合成データ | `GOOGLE_PLACES_API_KEY` を**自分で**設定し `fetch_places_sample.py` を実行 | 自分の GCP |

- API キー / 環境変数を**設定しない限り**、Google Cloud には接続せず、課金経路には一切入りません（fallback / ルールベースで完動）。
- `--llm vertex` は環境変数 `GOOGLE_CLOUD_PROJECT` と `google-genai` パッケージの両方が無ければエラーで停止します（誤って課金 API を叩かないための二重ゲート）。
- **環境変数を設定する = その API の課金に同意する、とみなしてください。** 料金は各 Google Cloud サービスの公式料金体系に従います。

## 環境変数（`.env` / gitignore 済み）

> ⚠️ 下記はすべて **任意（設定すると自分の Google Cloud に課金が発生し得る）**。未設定がデフォルトで、無料の fallback / ルールベースで動きます。

| 変数 | 用途 | 設定時の課金 |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | 実 Google Maps タイル表示（未設定なら fallback 地図） | あり（自分の GCP） |
| `GOOGLE_MAPS_MAP_ID` | Advanced Markers 用 Map ID | 単体では課金なし |
| `GOOGLE_PLACES_API_KEY` | 実 POI 取得（`fetch_places_sample.py`） | あり（自分の GCP） |
| `GOOGLE_CLOUD_PROJECT` | Vertex AI Gemini（`--llm vertex`） | あり（自分の GCP） |

> API キー・トークンはコードや git にコミットしないでください（`.env` は gitignore 済み）。

## 公開協業の入口

公開協業で見せる作業・判断・採否の正本は GitHub の docs / issues / PR です。まずは [`docs/public-collaboration-status.md`](docs/public-collaboration-status.md) と [`docs/good-first-issues.md`](docs/good-first-issues.md) を見てください。

| 場所 | 役割 |
|---|---|
| GitHub PR #9 | 協業入口を repository に入れた土台 |
| GitHub issue #11 | 現在 open の初回協力入口。fallback 地図ビューアの見やすさレビュー |
| GitHub issue #10 / #12 | maintainer baseline 済みで close。再現性・課金境界の追加 feedback は新しい小さい issue に分ける |
| GitHub issue #13 | Discord PR 通知はフリーズ方針により close。再開時は新しい判断で扱う |
| Linear | Nexus maintainer 側の内部マイルストーン / 運用管理。公開正本ではない |
| Discord | 呼び込みと軽い案内。現在は一旦フリーズ中で、決定や採否の正本ではない |

## GCP / Cloud Run での実機確認

Cloud Run での実機確認は、外部公開・課金・Secret Manager を伴う可能性があるため maintainer 承認後に行います。手順は [`docs/deploy.md`](docs/deploy.md) を参照してください。

まずは非公開 Cloud Run Service で `/api/health` と fallback viewer を確認し、公開 URL 化や Google Maps API キー注入は別判断で進めます。

## ドキュメント

- 仕様書: [`docs/ai-ecosystem-tool-spec.md`](docs/ai-ecosystem-tool-spec.md)
- データ契約: [`docs/subagents/contracts/urban-ecosystem-data-contract.md`](docs/subagents/contracts/urban-ecosystem-data-contract.md)
- 実装計画 / 作業指示: [`docs/ai-ecosystem-implementation-orchestration.md`](docs/ai-ecosystem-implementation-orchestration.md)
- 協力ガイド: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Discord 再開時向け guide: [`docs/discord-start-here.md`](docs/discord-start-here.md)
- Maintainer quick guide: [`docs/maintainer-quick-guide.md`](docs/maintainer-quick-guide.md)
- 公開協業の現在地: [`docs/public-collaboration-status.md`](docs/public-collaboration-status.md)
- 初回協力候補: [`docs/good-first-issues.md`](docs/good-first-issues.md)
- 公開協業 runbook: [`docs/public-collaboration-runbook.md`](docs/public-collaboration-runbook.md)
- 公開名義方針: [`docs/public-identity-policy.md`](docs/public-identity-policy.md)
- ライセンス決定メモ: [`docs/license-decision.md`](docs/license-decision.md)
- Discord PR 通知: [`docs/discord-pr-notifications.md`](docs/discord-pr-notifications.md)

## ライセンス

MIT License です。詳細は [`LICENSE`](LICENSE) を参照してください。

ライセンス決定の経緯: [`docs/license-decision.md`](docs/license-decision.md)
