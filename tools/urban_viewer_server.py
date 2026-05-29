"""
urban_viewer_server.py — Urban Ecosystem リプレイビューア FastAPI サーバー。

正本: docs/ai-ecosystem-tool-spec.md §17.3 / §21

エンドポイント:
  GET /                 ビューア HTML (GOOGLE_MAPS_API_KEY 注入 or fallback)
  GET /static/{path}    静的アセット (JS/CSS)
  GET /api/health       ヘルスチェック
  GET /api/runs         利用可能 run_id 一覧
  GET /api/data/{run_id}/{file}  データファイル配信 (許可リスト 9 件)

セキュリティ:
  - GOOGLE_MAPS_API_KEY はサーバー env から読み、HTML に注入する。
    コード・git・ログに平文で出さない (§5.1.1)。
  - run_id / file のパストラバーサル防止: 許可リスト方式 (§21.3.1)。
  - CORS: 同一オリジン (§21.6)。CORSMiddleware は追加しない。

識別子は英語 / コメントは日本語。
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Generator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

# ─────────────────────────────────────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────────────────────────────────────

# 許可ファイル一覧 (§21.3.1 / data-contract §File Names)
ALLOWED_FILES: frozenset[str] = frozenset({
    "pois.geojson",
    "aois.geojson",
    "roadnet.geojson",
    "agent_profiles_N100.json",
    "agent_states.jsonl",
    "poi_visit_records.jsonl",
    "interaction_events.jsonl",
    "relationships.jsonl",
    "summary.json",
})

# ファイル拡張子 -> Content-Type
CONTENT_TYPES: dict[str, str] = {
    ".geojson": "application/geo+json",
    ".json":    "application/json",
    ".jsonl":   "application/x-ndjson",
}

# run_id バリデーション正規表現 (§21.1)
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")

# プレースホルダ文字列 (index.html 内のプレースホルダ)
_PLACEHOLDER_KEY     = "%%GOOGLE_MAPS_API_KEY%%"
_PLACEHOLDER_MAP_ID  = "%%GOOGLE_MAPS_MAP_ID%%"
_PLACEHOLDER_SCRIPT  = "%%MAPS_SCRIPT_TAG%%"

# ─────────────────────────────────────────────────────────────────────────────
# 設定 (環境変数)
# ─────────────────────────────────────────────────────────────────────────────

def _get_maps_api_key() -> str:
    """GOOGLE_MAPS_API_KEY を環境変数から取得する。未設定時は空文字列。"""
    return os.environ.get("GOOGLE_MAPS_API_KEY", "")


def _get_maps_map_id() -> str:
    """GOOGLE_MAPS_MAP_ID を環境変数から取得する。未設定時は空文字列。"""
    return os.environ.get("GOOGLE_MAPS_MAP_ID", "")


def _get_data_source() -> str:
    """DATA_SOURCE 環境変数 ('local' | 'gcs')。デフォルト 'local'。"""
    return os.environ.get("DATA_SOURCE", "local")


def _get_data_root() -> Path:
    """ローカルデータルートディレクトリ。DATA_DIR env or デフォルト data/。"""
    data_dir = os.environ.get("DATA_DIR", "")
    if data_dir:
        return Path(data_dir)
    # urban-ecosystem ルートの data/ ディレクトリ
    return Path(__file__).parent.parent / "data"

# ─────────────────────────────────────────────────────────────────────────────
# HTML 生成 (APIキー注入 / §5.1.1)
# ─────────────────────────────────────────────────────────────────────────────

_VIEWER_HTML_PATH = Path(__file__).parent / "urban_viewer" / "index.html"


def _build_viewer_html(api_key: str, map_id: str) -> str:
    """index.html のプレースホルダを置き換えてレスポンス HTML を生成する。

    api_key が空の場合:
      - %%GOOGLE_MAPS_API_KEY%% はそのまま残す → app.js が fallback を検出。
      - %%MAPS_SCRIPT_TAG%% は空文字に置き換える (Maps bootstrap loader を出力しない)。

    api_key が設定されている場合:
      - %%GOOGLE_MAPS_API_KEY%% を注入する。
      - %%MAPS_SCRIPT_TAG%% に bootstrap loader の <script> タグを注入する。
      - キー値はログに出力しない。
    """
    html = _VIEWER_HTML_PATH.read_text(encoding="utf-8")

    if api_key:
        # Maps JavaScript API bootstrap loader タグ (§5.1.3)。
        # Google 公式の inline bootstrap loader パターン。
        # バックティック文字列は JavaScript テンプレートリテラルなので
        # Python f-string ではなく str.format を使わずそのまま連結する。
        js_loader = (
            "(g=>{var h,a,k,"
            'p="The Google Maps JavaScript API",'
            'c="google",l="importLibrary",q="__ib__",'
            "m=document,b=window;"
            "b=b[c]||(b[c]={});"
            "var d=b.maps||(b.maps={}),"
            "r=new Set,"
            "e=new URLSearchParams,"
            "u=()=>h||(h=new Promise(async(f,n)=>{"
            'await (a=m.createElement("script"));'
            'e.set("libraries",[...r]+"");'
            "for(k in g)e.set(k.replace(/[A-Z]/g,t=>\"_\"+t[0].toLowerCase()),g[k]);"
            'e.set("callback",c+".maps."+q);'
            # JavaScript テンプレートリテラル (バックティック) をそのまま埋め込む
            "a.src=`https://maps.googleapis.com/maps/api/js?`+e;"
            "d[q]=f;"
            'a.onerror=()=>h=n(Error(p+" could not load."));'
            "a.nonce=m.querySelector(\"script[nonce]\")?.nonce||\"\";"
            "m.head.append(a)}));"
            'd[l]?console.warn(p+" only loads once. Ignoring:",g):'
            "(d[l]=(f,...n)=>r.add(f)&&u().then(()=>d[l](f,...n)))})"
        )
        js_config = "{key: \"" + api_key + "\"}"
        script_tag = (
            "<script>\n"
            "  " + js_loader + "(" + js_config + ");\n"
            "</script>"
        )
        html = html.replace(_PLACEHOLDER_SCRIPT, script_tag)
        html = html.replace(_PLACEHOLDER_KEY,    api_key)
        if not map_id:
            # API key 設定済みだが GOOGLE_MAPS_MAP_ID 未設定 → DEMO_MAP_ID が注入される。
            # DEMO_MAP_ID は Google 利用規約で本番禁止 (§16 #6) のため警告を出す。
            logging.getLogger(__name__).warning(
                "GOOGLE_MAPS_MAP_ID 未設定: DEMO_MAP_ID を使用します (本番非推奨 / §16 #6)"
            )
        map_id_val = map_id if map_id else "DEMO_MAP_ID"
        html = html.replace(_PLACEHOLDER_MAP_ID, map_id_val)
    else:
        # キー未設定: Maps スクリプトを出力しない / プレースホルダをそのまま残す
        # app.js はプレースホルダ文字列を検出して fallback アダプタに切り替える
        html = html.replace(_PLACEHOLDER_SCRIPT, "<!-- Maps API key not set: using fallback map -->")
        # _PLACEHOLDER_KEY と _PLACEHOLDER_MAP_ID はそのまま残す

    return html

# ─────────────────────────────────────────────────────────────────────────────
# run 列挙 (§21.1 / §21.2)
# ─────────────────────────────────────────────────────────────────────────────

def _list_runs() -> list[dict]:
    """data/ 配下で summary.json を持つディレクトリを run として列挙する。

    §21.1: summary.json の存在をマニフェスト代わりとする。
    §21.2: runs 配列は started_at 降順。
    """
    data_root = _get_data_root()
    runs = []

    if not data_root.is_dir():
        return runs

    for subdir in sorted(data_root.iterdir()):
        if not subdir.is_dir():
            continue
        summary_path = subdir / "summary.json"
        if not summary_path.exists():
            continue
        run_id = subdir.name
        if not RUN_ID_RE.match(run_id):
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        # summary.json の内容をそのまま返す (§21.2)
        runs.append({
            "run_id":      summary.get("run_id",      run_id),
            "seed":        summary.get("seed",         0),
            "ticks":       summary.get("ticks",        0),
            "agents":      summary.get("agents",       0),
            "pois":        summary.get("pois",         0),
            "interactions": summary.get("interactions", 0),
            **({} if "aois"       not in summary else {"aois":       summary["aois"]}),
            **({} if "roads"      not in summary else {"roads":      summary["roads"]}),
            **({} if "started_at" not in summary else {"started_at": summary["started_at"]}),
        })

    # started_at 降順 (§21.2)
    runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
    return runs

# ─────────────────────────────────────────────────────────────────────────────
# データファイル配信 (§21.3)
# ─────────────────────────────────────────────────────────────────────────────

def _validate_run_and_file(run_id: str, file: str) -> Path:
    """run_id / file を検証してファイルパスを返す。

    パストラバーサル防止:
    - run_id は RUN_ID_RE にマッチしなければ 403
    - file は ALLOWED_FILES にあれば 403 (なければ 403)
    - ファイルが存在しなければ 404

    §21.3.4 のエラーレスポンスに準拠する。
    """
    # パストラバーサル文字チェック (§21.3.4)
    if ".." in run_id or "/" in run_id or ".." in file or "/" in file:
        raise HTTPException(status_code=403, detail="invalid path")

    # run_id 形式チェック
    if not RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=403, detail="invalid path")

    # ファイル許可リストチェック (§21.3.1)
    if file not in ALLOWED_FILES:
        raise HTTPException(status_code=403, detail=f"file not allowed: {file}")

    # run ディレクトリ存在チェック
    data_root = _get_data_root()
    run_dir   = data_root / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")

    # ファイル存在チェック
    file_path = run_dir / file
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"file not found: {file}")

    return file_path


def _stream_jsonl(path: Path) -> Generator[str, None, None]:
    """JSONL ファイルを 1 行ずつ yield する (§21.3.2 raw stream)。"""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                yield stripped + "\n"


def _content_type_for(file: str) -> str:
    """ファイル名から Content-Type を返す。"""
    if file.endswith(".jsonl"):
        return "application/x-ndjson"
    if file.endswith(".geojson"):
        return "application/geo+json"
    return "application/json"

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI アプリ
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Urban Ecosystem Viewer", version="0.1.0")

# 静的アセット配信 (/static/* -> tools/urban_viewer/)
_STATIC_DIR = Path(__file__).parent / "urban_viewer"
_APP_JS_PATH = _STATIC_DIR / "app.js"


@app.get("/static/app.js")
async def _serve_app_js() -> Response:
    """app.js 配信時に Maps キー / Map ID プレースホルダを注入する (§5.1.1)。

    StaticFiles mount より前に登録し、app.js だけ templating する。
    キー未設定時はプレースホルダを残し、app.js 側が fallback アダプタを選ぶ。
    キー値はログに出力しない。
    """
    api_key = _get_maps_api_key()
    map_id  = _get_maps_map_id()
    js = _APP_JS_PATH.read_text(encoding="utf-8")
    if api_key:
        js = js.replace(_PLACEHOLDER_KEY, api_key)
        js = js.replace(_PLACEHOLDER_MAP_ID, map_id if map_id else "DEMO_MAP_ID")
    return Response(content=js, media_type="application/javascript")


# app.js 以外の静的アセット (CSS / 他 JS / colors.js 等) は raw 配信
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.middleware("http")
async def _security_headers(request, call_next):
    """最小のセキュリティヘッダを付与する (公開時のクリックジャッキング / MIME sniffing 緩和)。"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """ビューア HTML を返す (APIキー注入 or fallback)。

    §21 / §13.4: APIキー未設定でも 500 を返さない。
    """
    api_key = _get_maps_api_key()
    map_id  = _get_maps_map_id()
    html    = _build_viewer_html(api_key, map_id)
    return HTMLResponse(content=html)


@app.get("/api/health")
async def health() -> JSONResponse:
    """ヘルスチェック (§21.4)。

    maps_key フィールドはキーの present/absent のみ返す。キー値は返さない。
    """
    api_key     = _get_maps_api_key()
    data_source = _get_data_source()
    return JSONResponse({
        "status":      "ok",
        "maps_key":    "present" if api_key else "absent",
        "data_source": data_source,
    })


@app.get("/api/runs")
async def list_runs() -> JSONResponse:
    """利用可能な run 一覧を返す (§21.2)。

    run が 0 件でも 4xx/5xx は返さない。
    """
    runs = _list_runs()
    return JSONResponse({"runs": runs})


@app.get("/api/data/{run_id}/{file}", response_model=None)
async def get_data_file(run_id: str, file: str) -> StreamingResponse | JSONResponse:
    """データファイルを配信する (§21.3)。

    JSONL は raw stream / GeoJSON・JSON はそのまま転送。
    """
    file_path    = _validate_run_and_file(run_id, file)
    content_type = _content_type_for(file)

    if file.endswith(".jsonl"):
        # JSONL: StreamingResponse で raw stream (§21.3.2)
        return StreamingResponse(
            _stream_jsonl(file_path),
            media_type=content_type,
        )

    # GeoJSON / JSON: ファイルをそのまま転送 (§21.3.3)
    content = file_path.read_bytes()
    return JSONResponse(
        content=json.loads(content),
        media_type=content_type,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI エントリポイント (uvicorn 直起動用)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Urban Ecosystem Viewer サーバー")
    parser.add_argument("--host",    default="0.0.0.0",  help="bind host")
    parser.add_argument("--port",    type=int, default=8080, help="bind port")
    parser.add_argument("--data",    default="",         help="DATA_DIR 上書き")
    parser.add_argument("--reload",  action="store_true", help="開発モード自動リロード")
    args = parser.parse_args()

    if args.data:
        os.environ["DATA_DIR"] = args.data

    uvicorn.run(
        "tools.urban_viewer_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
