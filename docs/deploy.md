# デプロイ手順書 — urban-ecosystem (Cloud Run)

> 対象プロジェクト: `nexus-ai-2045` / リージョン: `asia-northeast1`
> 仕様根拠: `docs/ai-ecosystem-tool-spec.md` §16 / §17 / §13.4

---

## ⚠️ Type1 警告 — 実行前に CEO 承認を得ること

以下の操作は**外部影響・課金・公開リスク**を伴うため、auto mode での自動実行は禁止です。
実行前に必ず CEO が確認し、明示的に承認してから行ってください。

| 操作 | リスク |
| --- | --- |
| GCP API 有効化 (`run`, `cloudbuild`, `artifactregistry`, `secretmanager`, Maps JS API) | 課金開始 |
| Secret Manager への Maps API キー格納 | 秘密値の外部登録 |
| Cloud Run Service デプロイ | 外部公開 / 課金発生 |
| `--allow-unauthenticated` 付きデプロイ | インターネット全公開 |
| サービスアカウント作成 / IAM ロール付与 | 権限変更 |
| Cloud Run Job 実行 | 課金・GCS 書き込み |

---

## 1. 前提条件

### 1.1 ローカル環境

```bash
# gcloud CLI がインストール済みであること
gcloud --version

# 認証
gcloud auth login
gcloud auth application-default login

# アクティブプロジェクトを nexus-ai-2045 に設定
gcloud config set project nexus-ai-2045

# 設定確認
gcloud config list
# project = nexus-ai-2045 であることを確認
```

### 1.2 必要 API の有効化

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  maps-backend.googleapis.com \
  --project nexus-ai-2045
```

> **注意**: Maps JavaScript API の API ID は `maps-backend.googleapis.com` です。
> Cloud Console → [APIとサービス] → [ライブラリ] で「Maps JavaScript API」を検索し有効化することも可能です。

---

## 2. Secret Manager — Maps API キーの格納

### 2.1 シークレット作成

```bash
# シークレットを作成する (値はここで指定しない)
gcloud secrets create urban-maps-key \
  --project nexus-ai-2045 \
  --replication-policy automatic
```

### 2.2 Maps API キーの格納

```bash
# キーの値は標準入力から流し込む (ファイルやコマンド引数に平文で書かない)
echo -n "<YOUR_MAPS_API_KEY>" | \
  gcloud secrets versions add urban-maps-key \
    --project nexus-ai-2045 \
    --data-file=-
```

> **禁止事項**: API キーをシェル履歴・スクリプトファイル・git・ログに平文で記録しないこと。
> コマンド引数 `--data-file=-` (標準入力) を使うか、Cloud Console の GUI から貼り付けること。

### 2.3 格納確認

```bash
# バージョン一覧 (値は表示しない)
gcloud secrets versions list urban-maps-key --project nexus-ai-2045
# STATE = enabled のバージョンが存在すること
```

---

## 3. 本番 Map ID の発行 (§16 #6)

`AdvancedMarkerElement` は Map ID が必須です。`DEMO_MAP_ID` は**開発・テスト専用**であり、
本番環境での使用は Google の利用規約で禁止されています。

### 3.1 発行手順

1. [Google Cloud Console](https://console.cloud.google.com/) → プロジェクト `nexus-ai-2045` を選択
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
  --project nexus-ai-2045 \
  --display-name "urban-ecosystem Cloud Run runtime SA"
```

### 4.2 最小権限ロールの付与

**MVP 必須 (Secret Manager アクセス)**:

```bash
gcloud projects add-iam-policy-binding nexus-ai-2045 \
  --member "serviceAccount:urban-run@nexus-ai-2045.iam.gserviceaccount.com" \
  --role "roles/secretmanager.secretAccessor"
```

**GCS 使用時 (スケール対応: 大規模リプレイ JSONL 読み取り)**:

```bash
# バケット単位で付与する (プロジェクト全体への付与は避ける)
gcloud storage buckets add-iam-policy-binding \
  gs://nexus-ai-2045-urban-data \
  --member "serviceAccount:urban-run@nexus-ai-2045.iam.gserviceaccount.com" \
  --role "roles/storage.objectViewer"
```

**Vertex AI 使用時 (Milestone 5 以降 / LLM 後段)**:

```bash
gcloud projects add-iam-policy-binding nexus-ai-2045 \
  --member "serviceAccount:urban-run@nexus-ai-2045.iam.gserviceaccount.com" \
  --role "roles/aiplatform.user"
```

> MVP では `roles/secretmanager.secretAccessor` のみ付与し、Storage・Vertex AI は必要になった時点で追加してください。

---

## 5. デプロイ — Cloud Run Service

### 5.1 公開範囲の選択 (§16 #4 — **未確定 / CEO 判断が必要**)

**公開範囲はデプロイ時に決定します。以下の 2 パターンどちらを選ぶかは未確定です。
デプロイ実行前に CEO が判断してください。**

| パターン | 概要 | 追加フラグ |
| --- | --- | --- |
| A: インターネット全公開 | 誰でもアクセス可能 | `--allow-unauthenticated` |
| B: 認証必須 (IAP / IAM) | Google アカウント認証 / 特定ユーザーのみ | `--no-allow-unauthenticated` + IAP 設定 |

### 5.2 パターン A: インターネット全公開

```bash
gcloud run deploy urban-ecosystem \
  --project nexus-ai-2045 \
  --source . \
  --region asia-northeast1 \
  --service-account=urban-run@nexus-ai-2045.iam.gserviceaccount.com \
  --set-secrets=GOOGLE_MAPS_API_KEY=urban-maps-key:latest \
  --set-env-vars=GOOGLE_MAPS_MAP_ID=<本番 Map ID> \
  --allow-unauthenticated
```

### 5.3 パターン B: 認証必須 (IAP)

#### ステップ 1: 認証ありでデプロイ

```bash
gcloud run deploy urban-ecosystem \
  --project nexus-ai-2045 \
  --source . \
  --region asia-northeast1 \
  --service-account=urban-run@nexus-ai-2045.iam.gserviceaccount.com \
  --set-secrets=GOOGLE_MAPS_API_KEY=urban-maps-key:latest \
  --set-env-vars=GOOGLE_MAPS_MAP_ID=<本番 Map ID> \
  --no-allow-unauthenticated
```

#### ステップ 2: アクセスを許可するユーザー / グループへの IAM 付与

```bash
# 特定ユーザーにアクセスを許可する例
gcloud run services add-iam-policy-binding urban-ecosystem \
  --project nexus-ai-2045 \
  --region asia-northeast1 \
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

**用途**: 大規模シミュレーションの事前生成 (リプレイ用 JSONL を GCS へ書き出す)

Service と同一イメージを使い、`tools/urban_simulation_cli.py` をエントリポイントに差し替えます。

#### Job の作成

```bash
gcloud run jobs create urban-sim-job \
  --project nexus-ai-2045 \
  --image <Artifact Registry のイメージ URI> \
  --region asia-northeast1 \
  --service-account=urban-run@nexus-ai-2045.iam.gserviceaccount.com \
  --set-env-vars=DATA_SOURCE=gcs \
  --set-secrets=GOOGLE_MAPS_API_KEY=urban-maps-key:latest \
  --command="python" \
  --args="tools/urban_simulation_cli.py,--agents,1000,--ticks,288,--output-bucket,gs://nexus-ai-2045-urban-data/runs/run-001/"
```

> **注意**: Job 作成に使うイメージ URI は `gcloud run deploy --source .` 後に
> Artifact Registry に push されたものを参照してください。
> `gcloud artifacts docker images list` で確認できます。

#### Job の実行

```bash
gcloud run jobs execute urban-sim-job \
  --project nexus-ai-2045 \
  --region asia-northeast1
```

#### Job の実行ログ確認

```bash
gcloud run jobs executions list \
  --job urban-sim-job \
  --project nexus-ai-2045 \
  --region asia-northeast1
```

> **MVP 判断**: MVP は Service のみで動作します。Job は Milestone 6 (スケール対応) で追加してください。

---

## 7. デプロイ検証 (§13.4)

デプロイ後に以下をすべて確認してください。

### 7.1 ヘルスチェック

```bash
# SERVICE_URL は gcloud run deploy の出力 or 以下で取得
SERVICE_URL=$(gcloud run services describe urban-ecosystem \
  --project nexus-ai-2045 \
  --region asia-northeast1 \
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
  --project nexus-ai-2045 \
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
  --project nexus-ai-2045 \
  --region asia-northeast1

# 特定リビジョンにトラフィックを100%戻す
gcloud run services update-traffic urban-ecosystem \
  --project nexus-ai-2045 \
  --region asia-northeast1 \
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
