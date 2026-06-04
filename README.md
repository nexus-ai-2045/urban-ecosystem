# 都市 AI エージェント人工生態系 (urban-ecosystem)

渋谷の街を舞台にした、決定論的な都市エージェント・シミュレーション。

都市の地図上で、多数の AI エージェントが一日を過ごす「人工生態系」シミュレーションです。
渋谷の実在スポットを舞台に、住人エージェントが通勤・昼食・買い物・交流・帰宅を行い、
その 1 日を地図ビューアでリプレイできます。

## はじめて触る人へ

最初から Google Cloud や API キーを用意する必要はありません。まずは API キーなしで動く代替地図ビューアを見て、「分かりにくいところ」「見やすくしたいところ」をコメントしてもらえるだけで助かります。

このプロジェクトはまだ実験段階です。完成品として評価するよりも、「ここが変に見える」「住人の動きが不自然」「LLM を使った時の理由や会話がそれっぽくない」「説明を読んでも何を見ればいいか分からない」といった素朴な違和感を集めたいです。

一方で、起動できない、主要画面が崩れる、ボタンが押せない、といった基本的な不具合は、公開協力者に見てもらう前に管理者側で直す対象です。

```bash
unset GOOGLE_MAPS_API_KEY GOOGLE_PLACES_API_KEY GOOGLE_CLOUD_PROJECT
python tools/smoke_fallback_viewer.py
```

起動できたら、表示された URL を開いてください。

見るポイント:

- 左側の状態表示が分かりやすいか。
- 地図上の地点、範囲、住人の意味が伝わるか。
- 右側のライブ概要で、いま何が起きているか追えるか。
- 下部の再生、ステップ、速度操作が初見で使えるか。
- 住人の行動や、LLM を使った時の説明・会話が不自然すぎないか。
- README や仕様書を読んで、どこで迷うか。

コードを書かなくても大丈夫です。「ここが分からない」「この文言が不親切」「このボタンが見つけにくい」みたいなコメントも歓迎です。

現在の最初の入口:

- [GitHub issue #11: 代替地図ビューアの見やすさ確認](https://github.com/nexus-ai-2045/urban-ecosystem/issues/11)
- [GitHub issue #65: どんな街データを入れると面白そうか](https://github.com/nexus-ai-2045/urban-ecosystem/issues/65)
- [GitHub issue #66: 設定画面で分かりにくいところ](https://github.com/nexus-ai-2045/urban-ecosystem/issues/66)
- [GitHub issue #67: README や仕様書で迷うところ](https://github.com/nexus-ai-2045/urban-ecosystem/issues/67)
- 公開協業の現在地: [`docs/public-collaboration-status.md`](docs/public-collaboration-status.md)

公開協業で見せる作業・判断・採否の正本は GitHub のドキュメント / issue / PR です。Linear は管理者側の内部管理で、公開協力者向けの正本ではありません。

Google Maps、Google Places、Vertex AI、Cloud Run などは、使いたい人だけが自分の Google Cloud プロジェクトで試す任意設定です。最初の参加に Google Cloud は不要です。管理者側で用意するプロジェクトや公開デモ環境を使う作業は、管理者が範囲を切ってから進めます。API キー、`.env`、トークン、Webhook URL は公開 issue / PR / コメントに貼らないでください。

参加ルートの切り分け:

| 立場 | まず使うもの | Google Cloud / Google Maps | 期待すること |
|---|---|---|---|
| 初回参加者 | API キーなしの代替地図ビューア | 不要 | 画面の分かりにくさ、README の迷いどころをコメントする |
| 自分の Google Cloud で試す人 | 自分のプロジェクト / API キー | 任意。課金・公開範囲は自分で管理 | Google Maps / Places / Vertex AI を任意で試す |
| 管理者 | 管理用プロジェクト / Cloud Run | 承認した範囲だけ使う | 非公開の動作確認、公開デモ、Secret Manager、IAM を管理する |

このため、リポジトリ参加の正規ルートは代替地図ビューアです。Cloud Run の公開 URL、管理者側の Google Cloud プロジェクト、Map ID、実 Google Maps 表示は、参加の前提ではなくデモ環境 / 発展的な設定として扱います。

## 特徴

- 🗺️ **実 Google Maps + 実渋谷 POI**。API キーが無くても代替地図で動く（CI / テスト主経路）。
- 🎲 **決定論シミュレーション**。同一 seed で出力がバイト一致で再現する。
- 🛣️ **道路追従の移動**。道路ネットワークをグラフ化し最短経路で移動するため、建物や道路を直線で貫通しない。
- 👥 **リッチプロフィール**。姓名・職業・性格・趣味・1 日の行動傾向を持つ。
- 🏷️ **苗字ベースのキャラ表示と日本語ラベル**。マーカーは姓（例「井上」）、カテゴリ/役割/交流は日本語表示。
- 🤖 **LLM 連携（Vertex AI Gemini / 任意）**。会話要約・行動決定・関係変化の理由文を生成。既定はルールベースで LLM 不要でも完動。

## アーキテクチャ

| ディレクトリ | 役割 |
|---|---|
| `app/` | FastAPI web サーバー（リプレイ配信 / API / LLM プロバイダ抽象） |
| `environments/urban_2d/` | シミュレーション中核（データモデル・行動ルール・道路グラフ） |
| `tools/` | データ生成・シミュレーション CLI・地図ビューア |
| `docs/` | 仕様書・データ契約・作業指示書 |
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

LLM（Vertex Gemini）を使う場合だけ、明示的に `--llm vertex` を付与:

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

`GOOGLE_MAPS_API_KEY` が未設定なら代替地図、設定済みなら実 Google Maps タイルで表示されます。
リポジトリ直下の `.env` は既定では読み込みません。ローカル開発で `.env` を使う場合だけ、`URBAN_ECOSYSTEM_LOAD_DOTENV=1` を明示してください。
API キーなしの再現性確認では、`GOOGLE_MAPS_API_KEY` / `GOOGLE_PLACES_API_KEY` / `GOOGLE_CLOUD_PROJECT` を未設定にした状態で起動してください。

## テスト

```bash
pip install -r requirements.txt
python -m pytest tests -q -m "not requires_api"
```

代替地図フロント E2E もローカルで走らせる場合:

```bash
python -m playwright install chromium
unset GOOGLE_MAPS_API_KEY GOOGLE_PLACES_API_KEY GOOGLE_CLOUD_PROJECT
python -m pytest tests/e2e -q
```

GitHub Actions の CI も同じく API キーなしで Chromium を入れ、代替地図経路を検証します。

公開協業の入口だけを短く確認する場合:

```bash
unset GOOGLE_MAPS_API_KEY GOOGLE_PLACES_API_KEY GOOGLE_CLOUD_PROJECT
python tools/smoke_fallback_viewer.py
```

この簡易確認は一時ディレクトリにサンプル実行結果を作り、`/api/health` が `maps_key: absent`、`/api/runs` が `sample` を返すことを確認します。Google Cloud、Secret Manager、Discord は使いません。

## 課金について（重要）

**このリポジトリはデフォルトで完全無料です。Google Cloud の課金は一切発生しません。**

課金が発生するのは、**あなた自身が明示的に Google Cloud の API キー / プロジェクトを設定した場合のみ**です。設定すると、その課金は**あなた自身の Google Cloud アカウント**に対して発生します（リポジトリ作者には課金されません）。

| 機能 | デフォルト（無料） | 課金が発生する明示操作 | 課金先 |
|---|---|---|---|
| シミュレーション | ルールベース（LLM 呼び出しなし） | `--llm vertex` + `GOOGLE_CLOUD_PROJECT` を**自分で**設定 | 自分の Google Cloud |
| 地図表示 | 代替地図（canvas 描画） | `GOOGLE_MAPS_API_KEY` を**自分で**設定 | 自分の Google Cloud |
| POI 取得 | 同梱データ / 合成データ | `GOOGLE_PLACES_API_KEY` を**自分で**設定し `fetch_places_sample.py` を実行 | 自分の Google Cloud |

- API キー / 環境変数を**設定しない限り**、Google Cloud には接続せず、課金経路には一切入りません（代替地図 / ルールベースで完動）。
- `--llm vertex` は環境変数 `GOOGLE_CLOUD_PROJECT` と `google-genai` パッケージの両方が無ければエラーで停止します（誤って課金 API を叩かないための二重ゲート）。
- **環境変数を設定する = その API の課金に同意する、とみなしてください。** 料金は各 Google Cloud サービスの公式料金体系に従います。

## 環境変数（`.env` / gitignore 済み）

> ⚠️ 下記はすべて **任意（設定すると自分の Google Cloud に課金が発生し得る）**。未設定がデフォルトで、無料の代替地図 / ルールベースで動きます。

| 変数 | 用途 | 設定時の課金 |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | 実 Google Maps タイル表示（未設定なら代替地図） | あり（自分の Google Cloud） |
| `GOOGLE_MAPS_MAP_ID` | Advanced Markers 用 Map ID | 単体では課金なし |
| `GOOGLE_PLACES_API_KEY` | 実 POI 取得（`fetch_places_sample.py`） | あり（自分の Google Cloud） |
| `GOOGLE_CLOUD_PROJECT` | Vertex AI Gemini（`--llm vertex`） | あり（自分の Google Cloud） |

> API キー・トークンはコードや git にコミットしないでください（`.env` は gitignore 済み）。

## Google Cloud / Cloud Run での実機確認

Cloud Run での実機確認は、使いたい人だけが自分の Google Cloud プロジェクトで実行する任意設定です。その場合の課金、公開範囲、Secret Manager、IAM 変更は、そのプロジェクトの所有者側で管理してください。初回参加や README / 画面確認のために Cloud Run を用意する必要はありません。

管理者側のプロジェクトを使う場合だけ、管理者の承認後に実行します。手順は [`docs/deploy.md`](docs/deploy.md) を参照してください。まずは非公開 Cloud Run Service で `/api/health` と代替地図ビューアを確認し、公開 URL 化や Google Maps API キー注入は別判断で進めます。

非公開 Cloud Run Service は、ブラウザで URL を直に開くと 403 になります。これは故障ではなく、公開範囲を閉じているためです。参加者に見せる公開デモにする場合は、管理者が課金・公開範囲・API キー制限を確認してから `allow-unauthenticated` や IAP などを選びます。

## ドキュメント

### 初めて読む

- 仕様書: [`docs/ai-ecosystem-tool-spec.md`](docs/ai-ecosystem-tool-spec.md)
- データ契約: [`docs/subagents/contracts/urban-ecosystem-data-contract.md`](docs/subagents/contracts/urban-ecosystem-data-contract.md)
- 実装計画 / 作業指示: [`docs/ai-ecosystem-implementation-orchestration.md`](docs/ai-ecosystem-implementation-orchestration.md)

### 協力したい人向け

- 協力ガイド: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- 公開協業の現在地: [`docs/public-collaboration-status.md`](docs/public-collaboration-status.md)
- 初回協力候補: [`docs/good-first-issues.md`](docs/good-first-issues.md)
- README・仕様書の改善についての議論: <https://github.com/nexus-ai-2045/urban-ecosystem/issues/67>

### 管理者向け

- 管理者向け早見表: [`docs/maintainer-quick-guide.md`](docs/maintainer-quick-guide.md)
- 公開協業の運用手順: [`docs/public-collaboration-runbook.md`](docs/public-collaboration-runbook.md)
- リリース方針: [`docs/release-policy.md`](docs/release-policy.md)
- 変更履歴: [`docs/CHANGELOG.md`](docs/CHANGELOG.md)

### 方針・背景

- 公開名義方針: [`docs/public-identity-policy.md`](docs/public-identity-policy.md)
- ライセンス決定メモ: [`docs/license-decision.md`](docs/license-decision.md)
- Discord 再開時向け案内: [`docs/discord-start-here.md`](docs/discord-start-here.md)
- Discord PR 通知: [`docs/discord-pr-notifications.md`](docs/discord-pr-notifications.md)

## ライセンス

MIT License です。詳細は [`LICENSE`](LICENSE) を参照してください。

ライセンス決定の経緯: [`docs/license-decision.md`](docs/license-decision.md)
