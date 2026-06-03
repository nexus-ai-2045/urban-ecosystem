# デプロイ手順書 — urban-ecosystem (Cloud Run)

> 対象プロジェクト: 各自の Google Cloud project (`DEPLOY_PROJECT`) / リージョン: `DEPLOY_REGION`
> 仕様根拠: `docs/ai-ecosystem-tool-spec.md` §16 / §17 / §13.4

---

## 0. 課金先と実行主体

この手順は、実行者が指定した Google Cloud project に Cloud Run / Secret Manager / Maps / Vertex AI などのリソースを作ります。

この手順は maintainer demo / 実機 smoke / advanced setup 用です。通常のリポジトリ参加者は、この手順を実行しなくても README の fallback viewer でレビューできます。

課金は `DEPLOY_PROJECT` に設定した project の請求先に発生します。Nexus の project を使う場合は Nexus に、各自の project を使う場合は各自の Google Cloud アカウント / 組織に課金されます。

```bash
# 各自の Google Cloud project ID を入れる
export DEPLOY_PROJECT="<YOUR_GCP_PROJECT>"
export DEPLOY_REGION="asia-northeast1"
export DEPLOY_BUCKET="${DEPLOY_PROJECT}-urban-data"
```

Nexus 管理の project を使う場合だけ、`DEPLOY_PROJECT` に Nexus の project ID を入れます。外部 contributor が自分で試す場合は、自分の Google Cloud project ID を使ってください。

---

## ⚠️ 要承認 — Nexus 管理 project での実行前に maintainer の明示承認を得ること

以下の操作は**外部影響・課金・公開リスク**を伴うため、Nexus 管理 project では auto mode での自動実行は禁止です。
Nexus 管理 project で実行する場合は、必ず maintainer が確認し、明示的に承認してから行ってください。

各自の Google Cloud project で試す場合も、課金・公開範囲・IAM 変更はその project の所有者責任です。コマンドを実行する前に、`DEPLOY_PROJECT` が自分の意図した project になっていることを確認してください。

| 操作 | リスク |
| --- | --- |
| GCP API 有効化 (`run`, `cloudbuild`, `artifactregistry`, `secretmanager`, Maps JS API) | `DEPLOY_PROJECT` で課金開始 |
| Secret Manager への Maps API キー格納 | `DEPLOY_PROJECT` への秘密値登録 |
| Cloud Run Service デプロイ | `DEPLOY_PROJECT` で外部公開 / 課金発生 |
| `--allow-unauthenticated` 付きデプロイ | インターネット全公開 |
| サービスアカウント作成 / IAM ロール付与 | `DEPLOY_PROJECT` の権限変更 |
| Cloud Run Job 実行 | `DEPLOY_PROJECT` で課金・コンテナ内一時出力 (GCS 書き込みはスケール対応実装後) |

---

## 0.5 ローカル preflight — GCP を実行しない確認

Cloud Run 実機確認の承認前に、ローカルだけで fallback viewer と deploy 前提を確認できます。
この preflight は NEX-29 の evidence 用であり、GCP API 有効化、Cloud Run deploy、Secret Manager、Google Maps / Places / Vertex AI、公開範囲変更、課金発生を行いません。

```bash
./.venv/bin/python tools/cloud_run_preflight.py --issue NEX-29 --format json
```

repo-local `.venv` がない場合は、先に一時 venv を作ってから実行してください。

```bash
python3 -m venv /tmp/urban-venv
/tmp/urban-venv/bin/python -m pip install -r requirements.txt
/tmp/urban-venv/bin/python tools/cloud_run_preflight.py --issue NEX-29 --format json
```

Linear に貼る短い evidence が必要な場合:

```bash
./.venv/bin/python tools/cloud_run_preflight.py --issue NEX-29 --format markdown \
  --evidence-file /tmp/urban-cloud-run-preflight-NEX-29.md
```

この script は `tools/smoke_fallback_viewer.py` を child process として実行し、その child env から `GOOGLE_MAPS_API_KEY` / `GOOGLE_PLACES_API_KEY` / `GOOGLE_CLOUD_PROJECT` / `GOOGLE_APPLICATION_CREDENTIALS` / `DEPLOY_PROJECT` を外します。
そのため、手元の shell に GCP 関連 env が残っていても、preflight の確認範囲は local fallback に限定されます。

出力で確認する項目:

| 項目 | 期待値 |
| --- | --- |
| `scope.gcp_executed` | `false` |
| `scope.cloud_run_deployed` | `false` |
| `scope.secret_manager_accessed` | `false` |
| `scope.public_access_changed` | `false` |
| `scope.billing_scope_changed` | `false` |
| `checks[].name = fallback viewer smoke` | `ok` |

fallback smoke を飛ばして docs / env / file marker だけ確認する場合:

```bash
./.venv/bin/python tools/cloud_run_preflight.py --issue NEX-29 --skip-smoke --format json
```

> 注意: この preflight が `ok` でも、下の GCP 実行手順の承認を代替しません。
> Cloud Run 実機確認に進む場合は、NEX-29 で公開範囲・課金・Secret Manager 利用・実行コマンドを確認し、maintainer の明示承認を残してください。

---

## 1. 前提条件

### 1.1 ローカル環境

```bash
# gcloud CLI がインストール済みであること
gcloud --version

# 認証
gcloud auth login
gcloud auth application-default login

# アクティブプロジェクトを DEPLOY_PROJECT に設定
gcloud config set project "${DEPLOY_PROJECT}"

# 設定確認
gcloud config list
# project = ${DEPLOY_PROJECT} であることを確認
```

### 1.2 必要 API の有効化

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  maps-backend.googleapis.com \
  --project "${DEPLOY_PROJECT}"
```

> **注意**: Maps JavaScript API の API ID は `maps-backend.googleapis.com` です。
> Cloud Console → [APIとサービス] → [ライブラリ] で「Maps JavaScript API」を検索し有効化することも可能です。

---

## 2. Secret Manager — Maps API キーの格納

### 2.1 シークレット作成

```bash
# シークレットを作成する (値はここで指定しない)
gcloud secrets create urban-maps-key \
  --project "${DEPLOY_PROJECT}" \
  --replication-policy automatic
```

### 2.2 Maps API キーの格納

```bash
# キーの値は標準入力から流し込む (ファイルやコマンド引数に平文で書かない)
echo -n "<YOUR_MAPS_API_KEY>" | \
  gcloud secrets versions add urban-maps-key \
    --project "${DEPLOY_PROJECT}" \
    --data-file=-
```

> **禁止事項**: API キーをシェル履歴・スクリプトファイル・git・ログに平文で記録しないこと。
> コマンド引数 `--data-file=-` (標準入力) を使うか、Cloud Console の GUI から貼り付けること。

### 2.3 格納確認

```bash
# バージョン一覧 (値は表示しない)
gcloud secrets versions list urban-maps-key --project "${DEPLOY_PROJECT}"
# STATE = enabled のバージョンが存在すること
```

---

## 3. 本番 Map ID の発行 (§16 #6)

`AdvancedMarkerElement` は Map ID が必須です。`DEMO_MAP_ID` は**開発・テスト専用**であり、
本番環境での使用は Google の利用規約で禁止されています。

Map ID は、通常の参加者レビューには不要です。Map ID が未設定の場合、viewer は通常 Marker で Google Maps を表示します。この場合、Google Maps 側から Marker 非推奨の warning が出ることがありますが、表示停止エラーではありません。warning zero / Advanced Marker 運用にしたい場合だけ、本節で本番用 Map ID を発行します。

### 3.1 発行手順

1. [Google Cloud Console](https://console.cloud.google.com/) → プロジェクト `<YOUR_GCP_PROJECT>` を選択
2. [Google Maps Platform] → [地図の管理] → [地図の作成]
3. 地図タイプ: **JavaScript** を選択し、任意の名前 (例: `urban-ecosystem-prod`) を付けて作成
4. 発行された Map ID (例: `abc123def456...`) をコピーする

### 3.2 Map ID の環境変数注入

デプロイコマンドに `--set-env-vars=GOOGLE_MAPS_MAP_ID=<発行した Map ID>` を追加します
(後述のデプロイコマンド例を参照)。

> **注意**: Map ID は秘密値ではありませんが、本番とテストの混用を防ぐため、
> 環境ごとに別の Map ID を発行してください。

---

## 4. ランタイム サービスアカウント (最小権限)

### 4.1 サービスアカウント作成

```bash
gcloud iam service-accounts create urban-run \
  --project "${DEPLOY_PROJECT}" \
  --display-name "urban-ecosystem Cloud Run runtime SA"
```

### 4.2 最小権限ロールの付与

**MVP 必須 (Secret Manager アクセス)**:

```bash
gcloud projects add-iam-policy-binding "${DEPLOY_PROJECT}" \
  --member "serviceAccount:urban-run@${DEPLOY_PROJECT}.iam.gserviceaccount.com" \
  --role "roles/secretmanager.secretAccessor"
```

**GCS 使用時 (スケール対応: 大規模リプレイ JSONL 読み取り)**:

```bash
# バケット単位で付与する (プロジェクト全体への付与は避ける)
gcloud storage buckets add-iam-policy-binding \
  "gs://${DEPLOY_BUCKET}" \
  --member "serviceAccount:urban-run@${DEPLOY_PROJECT}.iam.gserviceaccount.com" \
  --role "roles/storage.objectViewer"
```

**Vertex AI 使用時 (Milestone 5 以降 / LLM 後段)**:

```bash
gcloud projects add-iam-policy-binding "${DEPLOY_PROJECT}" \
  --member "serviceAccount:urban-run@${DEPLOY_PROJECT}.iam.gserviceaccount.com" \
  --role "roles/aiplatform.user"
```

> MVP では `roles/secretmanager.secretAccessor` のみ付与し、Storage・Vertex AI は必要になった時点で追加してください。

### 4.3 SA ハードニング — 運用ノート

#### ビルド SA と実行 SA の分離

Cloud Build (ビルド時) と Cloud Run (実行時) は**別の SA を使う**ことを推奨します。

| SA | 推奨名 | 役割 |
| --- | --- | --- |
| ビルド SA | `urban-builder@${DEPLOY_PROJECT}.iam.gserviceaccount.com` | ソースビルド・イメージ push のみ |
| 実行 SA | `urban-run@${DEPLOY_PROJECT}.iam.gserviceaccount.com` | Cloud Run コンテナの実行のみ |

ビルド SA に付与するロールは `roles/artifactregistry.writer`（イメージ push）に限定し、Secret へのアクセスは与えません。

```bash
# ビルド SA 作成 (まだ存在しない場合)
gcloud iam service-accounts create urban-builder \
  --project "${DEPLOY_PROJECT}" \
  --display-name "urban-ecosystem Cloud Build SA"

# ビルド SA への最小ロール付与 (Artifact Registry への push 権限のみ)
gcloud projects add-iam-policy-binding "${DEPLOY_PROJECT}" \
  --member "serviceAccount:urban-builder@${DEPLOY_PROJECT}.iam.gserviceaccount.com" \
  --role "roles/artifactregistry.writer"
```

#### 実行 SA に付与すべき最小ロール

| ロール | 目的 | 付与タイミング |
| --- | --- | --- |
| `roles/secretmanager.secretAccessor` | Maps API キーの取得 | MVP 必須 |
| `roles/storage.objectViewer` (バケット単位) | GCS リプレイ JSONL 読み取り | Milestone 6 以降 |
| `roles/aiplatform.user` | Vertex AI 呼び出し | Milestone 5 以降 |

> **`roles/run.invoker` は実行 SA に付与しません。**
> `roles/run.invoker` はサービスを呼び出す側 (人間・別サービス) に付与するロールです。
> 実行 SA (コンテナ内プロセス) に付けると自己呼び出しを可能にし、
> 攻撃面が広がるため不要です。

#### 広域ロールを付けない

以下のロールは便利に見えますが、権限過剰になるため**付与禁止**です。

| 禁止ロール | 理由 |
| --- | --- |
| `roles/editor` / `roles/owner` | プロジェクト全体への書き込み権限を与えてしまう |
| `roles/secretmanager.admin` | シークレットの作成・削除まで可能になる |
| `roles/storage.admin` | バケット全体への書き込み権限を与えてしまう |
| `roles/iam.serviceAccountTokenCreator` | 他 SA へのなりすましが可能になる |

必要なロールが増えた場合は、**バケット単位・シークレット単位**などリソースレベルで絞って付与してください。

---

## 5. デプロイ — Cloud Run Service

### 5.1 公開範囲の選択 (§16 #4)

**公開範囲はデプロイ時に決定します。以下の 2 パターンどちらを選ぶかは未確定です。
各自の Google Cloud project では project owner が判断してください。Nexus 管理 project では maintainer が判断してください。**

| パターン | 概要 | 追加フラグ |
| --- | --- | --- |
| A: インターネット全公開 | 誰でもアクセス可能 | `--allow-unauthenticated` |
| B: 認証必須 (IAP / IAM) | Google アカウント認証 / 特定ユーザーのみ | `--no-allow-unauthenticated` + IAP 設定 |

### 5.1.1 インスタンス数・同時実行数の推奨指針 (コスト暴走防止)

urban-ecosystem は **100体・1日リプレイのデモ用途** であり、高トラフィックは想定していません。
意図しないスケールアウトによる課金暴走を防ぐため、デプロイ時に以下のフラグを付与することを推奨します。

| フラグ | 推奨レンジ | 理由 |
| --- | --- | --- |
| `--max-instances` | `1〜3` (推奨例: `2`) | インスタンス上限を小さく抑えてコスト上限を予測可能にする |
| `--concurrency` | `40〜80` (推奨例: `80`) | 1インスタンスあたりの同時リクエスト数。デモ規模では80で十分で、無駄な複製を減らせる |

> **注意**: これらはデモ規模向けの「コスト優先」設定です。将来的にトラフィックが増加した場合は
> 実負荷に合わせて引き上げてください。断定的な上限値ではなく、出発点としての推奨レンジです。

### 5.2 パターン A: インターネット全公開

```bash
gcloud run deploy urban-ecosystem \
  --project "${DEPLOY_PROJECT}" \
  --source . \
  --region "${DEPLOY_REGION}" \
  --service-account="urban-run@${DEPLOY_PROJECT}.iam.gserviceaccount.com" \
  --set-secrets=GOOGLE_MAPS_API_KEY=urban-maps-key:latest \
  --set-env-vars=GOOGLE_MAPS_MAP_ID=<本番 Map ID> \
  --max-instances=2 \
  --concurrency=80 \
  --allow-unauthenticated
```

### 5.3 パターン B: 認証必須 (IAP)

#### ステップ 1: Secret なしで fallback viewer を確認する

最初の実機 smoke では、Maps API キーや Map ID を注入せず、fallback viewer が Cloud Run 上で
起動することだけを確認します。この段階では Secret Manager の secret 作成や Maps API キー登録は不要です。

```bash
gcloud run deploy urban-ecosystem \
  --project "${DEPLOY_PROJECT}" \
  --source . \
  --region "${DEPLOY_REGION}" \
  --service-account="urban-run@${DEPLOY_PROJECT}.iam.gserviceaccount.com" \
  --max-instances=1 \
  --concurrency=80 \
  --no-allow-unauthenticated
```

デプロイ後は §7 の `/api/health` と viewer 表示を確認します。Google Maps API キーを注入していないため、
表示は fallback 地図になることが期待値です。

`--no-allow-unauthenticated` の service は、ブラウザで URL を直接開くと 403 になります。これは故障ではなく、認証必須にしているためです。実機 smoke は identity token 付きの request で確認します。参加者に見せる公開 demo にする場合は、課金・公開範囲・API key 制限を確認してから `--allow-unauthenticated` または IAP 構成を選びます。

#### ステップ 2: Maps API キーありでデプロイ

```bash
gcloud run deploy urban-ecosystem \
  --project "${DEPLOY_PROJECT}" \
  --source . \
  --region "${DEPLOY_REGION}" \
  --service-account="urban-run@${DEPLOY_PROJECT}.iam.gserviceaccount.com" \
  --set-secrets=GOOGLE_MAPS_API_KEY=urban-maps-key:latest \
  --set-env-vars=GOOGLE_MAPS_MAP_ID=<本番 Map ID> \
  --max-instances=2 \
  --concurrency=80 \
  --no-allow-unauthenticated
```

#### ステップ 3: アクセスを許可するユーザー / グループへの IAM 付与

```bash
# 特定ユーザーにアクセスを許可する例
gcloud run services add-iam-policy-binding urban-ecosystem \
  --project "${DEPLOY_PROJECT}" \
  --region "${DEPLOY_REGION}" \
  --member "user:<your-email>@example.com" \
  --role "roles/run.invoker"
```

#### ステップ 3: IAP の有効化 (任意 / Google アカウント認証 UI が必要な場合)

IAP (Identity-Aware Proxy) を使用する場合は Cloud Console → [セキュリティ] → [Identity-Aware Proxy] から設定してください。Cloud Run への IAP 適用は Load Balancer 経由が必要です。詳細は[公式ドキュメント](https://cloud.google.com/iap/docs/cloud-run-tutorial)を参照してください。

---

## 6. Service と Job の使い分け (§17.1)

### 6.1 Cloud Run Service (常駐 Web サーバー)

**用途**: 地図ビューア配信 + リプレイデータ API + 任意の小規模 sim 実行 API

エントリポイント: `app/main.py` の `app` (FastAPI アプリ)

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- `$PORT` 環境変数で起動ポートが渡されます。`app/main.py` は `0.0.0.0:$PORT` でバインドしてください。
- MVP はこの Service のみで成立します (同梱サンプルデータでリプレイ)。

### 6.2 Cloud Run Job (バッチ処理)

**用途**: 大規模シミュレーションの事前生成。

Service と同一イメージを使い、`tools/urban_simulation_cli.py run` をエントリポイントとして実行します。
現行 CLI は `--out <dir>` へのローカルファイル出力のみ対応しています。Cloud Run Job のコンテナ内
ファイルシステムは実行後に破棄されるため、以下の例は大規模 run の smoke / benchmark 用です。
永続化されたリプレイ成果物を Cloud Run Service から読むには、Milestone 6 で GCS 書き出しと
`DATA_SOURCE=gcs` 読み取りを実装してから使用してください。

#### Job の作成

```bash
gcloud run jobs create urban-sim-job \
  --project "${DEPLOY_PROJECT}" \
  --image <Artifact Registry のイメージ URI> \
  --region "${DEPLOY_REGION}" \
  --service-account="urban-run@${DEPLOY_PROJECT}.iam.gserviceaccount.com" \
  --command="python" \
  --args="tools/urban_simulation_cli.py,run,--sample,--agents,1000,--ticks,288,--out,/tmp/urban_runs/run-001"
```

> **注意**: Job 作成に使うイメージ URI は `gcloud run deploy --source .` 後に
> Artifact Registry に push されたものを参照してください。
> `gcloud artifacts docker images list` で確認できます。

#### Job の実行

```bash
gcloud run jobs execute urban-sim-job \
  --project "${DEPLOY_PROJECT}" \
  --region "${DEPLOY_REGION}"
```

#### Job の実行ログ確認

```bash
gcloud run jobs executions list \
  --job urban-sim-job \
  --project "${DEPLOY_PROJECT}" \
  --region "${DEPLOY_REGION}"
```

> **MVP 判断**: MVP は Service のみで動作します。Job は Milestone 6 (スケール対応) で追加してください。
> 現時点の viewer API は `DATA_SOURCE=local` のみ実装済みです。
> `DATA_SOURCE=gcs` を Service に設定すると `/api/runs` と `/api/data/...` は 501 を返します。
> GCS からの run 列挙・ファイル配信は、GCS 実装を追加するPRで有効化してください。

---

## 7. デプロイ検証 (§13.4)

デプロイ後に以下をすべて確認してください。

### 7.1 ヘルスチェック

```bash
# SERVICE_URL は gcloud run deploy の出力 or 以下で取得
SERVICE_URL=$(gcloud run services describe urban-ecosystem \
  --project "${DEPLOY_PROJECT}" \
  --region "${DEPLOY_REGION}" \
  --format "value(status.url)")

# ヘルスチェック: 200 を返すこと
curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/api/health"
# 期待値: 200
```

### 7.2 リプレイ表示の確認

```bash
# ブラウザでルート URL を開く
echo "ビューアURL: ${SERVICE_URL}/"
# 確認事項:
# - 地図が表示される
# - 100体のエージェントマーカーが表示される
# - タイムスライダーで Day 0 のリプレイが動作する
```

### 7.3 キー未設定フォールバックの確認

ローカルでキーなし起動を確認します (`--set-secrets` を外した状態で `docker run` で確認):

```bash
docker build -t urban-ecosystem:local .
docker run --rm -p 8080:8080 urban-ecosystem:local
# GOOGLE_MAPS_API_KEY を設定しない状態で起動する

curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/health
# 期待値: 200 (500 を返してはならない)

curl -s http://localhost:8080/ | grep -i "fallback\|leaflet\|canvas"
# fallback 地図アダプタが読み込まれていること
```

### 7.4 秘密値の漏洩チェック

```bash
# イメージ内に Maps API キーが平文で含まれていないことを確認
docker run --rm urban-ecosystem:local \
  sh -c "grep -r 'AIza' /app || echo 'OK: no key found in image'"

# git 履歴に API キーが含まれていないことを確認
git log -p | grep -c 'AIza'
# 期待値: 0

# Cloud Run のログに API キーが出力されていないことを確認
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=urban-ecosystem AND textPayload=~AIza" \
  --project "${DEPLOY_PROJECT}" \
  --limit 10
# 期待値: 0 件
```

### 7.5 run_id 一覧 API の確認

```bash
curl -s "${SERVICE_URL}/api/runs"
# 期待値: JSON 配列 (利用可能な run_id 一覧)
# 例: ["sample-run-001"]
```

---

## 8. ロールバック

Cloud Run はリビジョン単位でロールバックできます。

```bash
# リビジョン一覧を確認
gcloud run revisions list \
  --service urban-ecosystem \
  --project "${DEPLOY_PROJECT}" \
  --region "${DEPLOY_REGION}"

# 特定リビジョンにトラフィックを100%戻す
gcloud run services update-traffic urban-ecosystem \
  --project "${DEPLOY_PROJECT}" \
  --region "${DEPLOY_REGION}" \
  --to-revisions <リビジョン名>=100
```

---

## 9. 参照セクション

| 内容 | 参照先 |
| --- | --- |
| 未決事項 #4 (公開範囲) / #6 (Map ID) | `docs/ai-ecosystem-tool-spec.md` §16 |
| Service / Job 使い分け | `docs/ai-ecosystem-tool-spec.md` §17.1 |
| Secrets / IAM 詳細 | `docs/ai-ecosystem-tool-spec.md` §17.5 |
| Dockerfile / cloudbuild 方針 | `docs/ai-ecosystem-tool-spec.md` §17.6 |
| デプロイ検証チェックリスト | `docs/ai-ecosystem-tool-spec.md` §13.4 |
| WO 受け入れ基準 | `docs/subagents/work-orders/wo-urban-005-cloud-run-deploy.yaml` |
