# urban-ecosystem — Cloud Run Service / Job 共用イメージ
# ベース: python:3.12-slim (GPU・メディア処理依存なし / spec §17.6)
# 正本: docs/ai-ecosystem-tool-spec.md §17 / wo-urban-005-cloud-run-deploy.yaml

FROM python:3.12-slim

WORKDIR /app

# --- 依存インストール (ソースより先にコピーしてキャッシュを活かす) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- アプリケーションソースのコピー ---
# app/ : FastAPI サーバ (WO-003 / WO-005 で実装)
# tools/ : シミュレーション CLI (urban_simulation_cli.py 等)
# environments/ : ルールベースシミュレーションコア (urban_2d/)
# docs/ : 公開ロードマップ / TODO preview (/docs/*)
COPY app/ ./app/
COPY tools/ ./tools/
COPY environments/ ./environments/
COPY docs/ ./docs/

# --- デモデータ同梱 (Cloud Run 起動直後に /api/runs から取得可能にする) ---
# WO-004 の --sample フラグで seed=42 固定サンプルを 8 ファイル生成。
# 秘密情報は渡さない。LLM API は呼ばない (ルールベースのみ)。
# 生成ファイルは data/urban_demo/ 以下に展開される。
# ローカルの data/ ディレクトリは .dockerignore で除外済み (重複持ち込み防止)。
RUN python tools/urban_simulation_cli.py run --sample --seed 42 --out data/urban_demo

# Cloud Run は $PORT を注入する。未設定時のデフォルトは 8080 (spec §17 / WO ノート)。
EXPOSE 8080

# shell 形式で $PORT 変数を展開する (exec 形式は $ 解決不可)。
# $PORT が未設定なら 8080 にフォールバック。
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
