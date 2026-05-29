"""
test_urban_viewer_server.py — urban_viewer_server のサーバーエンドポイントテスト。

正本: docs/subagents/work-orders/wo-urban-003-replay-viewer.yaml §テスト
仕様参照: docs/ai-ecosystem-tool-spec.md §21 / §13.4 / §18.1 ビューアサーバー

テスト対象:
  - GET /api/health : ステータス・maps_key フィールド・キー平文非公開
  - GET /api/runs   : ゼロ件 / 1 件
  - GET /api/data/{run_id}/{file}: 許可リスト 9 ファイル通過 / 未許可ファイル 403 / 不在 run 404 / ファイル未存在 404
  - GET /           : APIキー未設定時 fallback HTML / キー平文非公開
  - パストラバーサル 403

注意:
  - WO-004 (agent_states.jsonl 生成) は並列実装中で未完のため、
    agent_states.jsonl のみ最小 fixture をテスト内で自作する。
  - 他のファイルは tools/generate_urban_sample.py を tmp に呼んで生成する。
  - FastAPI TestClient を使う (uvicorn 起動不要)。

識別子は英語 / コメントは日本語。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# fastapi 未インストール環境では本テストモジュールを skip する
# (DoD「pytest tests/」を fastapi 無し環境でも collection error にしない)。
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

# ─── import path を通す ────────────────────────────────────────────────────

# プロジェクトルートを sys.path に追加 (conftest.py と同様)
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# サーバーモジュールを import
from tools.urban_viewer_server import app, ALLOWED_FILES

# ─────────────────────────────────────────────────────────────────────────────
# fixture: 最小 agent_states.jsonl (contract §Agent State JSONL 準拠)
# ─────────────────────────────────────────────────────────────────────────────

# contract §Agent State JSONL で必須: tick/day/time/agent_id/lat/lon/action/status
_MIN_AGENT_STATES = [
    {"tick": 0, "day": 0, "time": "08:00:00", "agent_id": 0,
     "lat": 35.660, "lon": 139.700, "action": "commute", "status": "moving"},
    {"tick": 0, "day": 0, "time": "08:00:00", "agent_id": 1,
     "lat": 35.661, "lon": 139.701, "action": "commute", "status": "moving"},
    {"tick": 1, "day": 0, "time": "08:05:00", "agent_id": 0,
     "lat": 35.662, "lon": 139.702, "action": "commute", "status": "moving"},
    {"tick": 1, "day": 0, "time": "08:05:00", "agent_id": 1,
     "lat": 35.663, "lon": 139.703, "action": "commute", "status": "moving"},
]

_MIN_INTERACTION_EVENTS: list[dict] = []

_MIN_SUMMARY = {
    "run_id":       "test_run",
    "seed":         42,
    "ticks":        2,
    "agents":       2,
    "pois":         10,
    "interactions": 0,
}


@pytest.fixture(scope="module")
def sample_run_dir(tmp_path_factory):
    """generate_urban_sample.py で静的データを生成し、agent_states.jsonl を手作りして
    テスト用 run ディレクトリを作る。

    WO-004 未完のため agent_states.jsonl は最小 fixture で自作する。
    """
    tmp_root = tmp_path_factory.mktemp("urban_data")
    run_dir  = tmp_root / "test_run"
    run_dir.mkdir()

    # generate_urban_sample.py を呼んでゼロから静的データを生成。
    # --agents は小さい値で高速化するが、ファイル名は contract §File Names の
    # 固定名 agent_profiles_N100.json を使うためリネームが必要。
    gen_script = _PROJECT_ROOT / "tools" / "generate_urban_sample.py"
    result = subprocess.run(
        [sys.executable, str(gen_script),
         "--seed", "42",
         "--agents", "2",
         "--pois", "10",
         "--out-dir", str(run_dir)],
        capture_output=True,
        text=True,
    )
    # スクリプト実行に失敗した場合は最小ファイルを手作りする
    if result.returncode != 0:
        _create_minimal_static_files(run_dir)
    else:
        # generate_urban_sample.py は --agents N に応じて agent_profiles_NN.json を
        # 出力する (例: --agents 2 -> agent_profiles_N2.json)。
        # contract §File Names は agent_profiles_N100.json を期待するため、
        # 固定ファイル名にコピーする。
        import shutil
        for p in run_dir.glob("agent_profiles_N*.json"):
            target = run_dir / "agent_profiles_N100.json"
            if p.name != "agent_profiles_N100.json":
                shutil.copy(p, target)

    # agent_states.jsonl: 最小 fixture を手作り (WO-004 は並列実装中 / §テスト仕様)
    agent_states_path = run_dir / "agent_states.jsonl"
    with open(agent_states_path, "w", encoding="utf-8") as fh:
        for state in _MIN_AGENT_STATES:
            fh.write(json.dumps(state, ensure_ascii=False) + "\n")

    # interaction_events.jsonl: 空ファイル
    interaction_path = run_dir / "interaction_events.jsonl"
    with open(interaction_path, "w", encoding="utf-8") as fh:
        for ev in _MIN_INTERACTION_EVENTS:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")

    # summary.json を上書き (generate が出力するものと件数を合わせる)
    summary = {
        "run_id":       "test_run",
        "seed":         42,
        "ticks":        2,
        "agents":       2,
        "pois":         _count_pois(run_dir),
        "interactions": 0,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False), encoding="utf-8"
    )

    return tmp_root


def _count_pois(run_dir: Path) -> int:
    """pois.geojson の feature 数を数える。"""
    poi_path = run_dir / "pois.geojson"
    if not poi_path.exists():
        return 0
    try:
        data = json.loads(poi_path.read_text(encoding="utf-8"))
        return len(data.get("features", []))
    except Exception:
        return 0


def _create_minimal_static_files(run_dir: Path) -> None:
    """generate_urban_sample.py が失敗した場合の最小 fallback ファイル生成。"""
    poi_features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [139.700 + i * 0.001, 35.660]},
            "properties": {"id": f"poi_{i:03d}", "category": "amenity-cafe"},
        }
        for i in range(1, 11)
    ]
    (run_dir / "pois.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": poi_features}),
        encoding="utf-8",
    )

    aoi_features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[139.695, 35.655], [139.705, 35.655],
                                  [139.705, 35.665], [139.695, 35.665],
                                  [139.695, 35.655]]],
            },
            "properties": {"id": "aoi_001", "name": "Test Area", "category": "district"},
        }
    ]
    (run_dir / "aois.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": aoi_features}),
        encoding="utf-8",
    )

    road_features = [
        {
            "type": "Feature",
            "geometry": {"type": "LineString",
                          "coordinates": [[139.700, 35.660], [139.701, 35.661]]},
            "properties": {"id": "road_001", "walkable": True},
        }
    ]
    (run_dir / "roadnet.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": road_features}),
        encoding="utf-8",
    )

    agent_profiles = [
        {
            "id": 0,
            "name": "Tanaka Ken",
            "initial_position": {"lat": 35.660, "lon": 139.700},
            "role": "office_worker",
        },
        {
            "id": 1,
            "name": "Sato Makoto",
            "initial_position": {"lat": 35.661, "lon": 139.701},
            "role": "student",
        },
    ]
    (run_dir / "agent_profiles_N100.json").write_text(
        json.dumps(agent_profiles, ensure_ascii=False),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────────
# TestClient fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def client_no_key(sample_run_dir, monkeypatch):
    """GOOGLE_MAPS_API_KEY 未設定のクライアント。"""
    monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def client_with_key(sample_run_dir, monkeypatch):
    """GOOGLE_MAPS_API_KEY が設定されたクライアント (テスト用ダミーキー)。"""
    monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "TEST_DUMMY_KEY_NOT_REAL")
    return TestClient(app, raise_server_exceptions=True)


# ─────────────────────────────────────────────────────────────────────────────
# /api/health テスト (§21.4)
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_200(self, client_no_key):
        """ヘルスチェックは常に 200 を返す。"""
        res = client_no_key.get("/api/health")
        assert res.status_code == 200

    def test_status_ok(self, client_no_key):
        """status フィールドは 'ok'。"""
        body = client_no_key.get("/api/health").json()
        assert body["status"] == "ok"

    def test_maps_key_absent_when_no_key(self, client_no_key):
        """APIキー未設定時 maps_key == 'absent'。"""
        body = client_no_key.get("/api/health").json()
        assert body["maps_key"] == "absent"

    def test_maps_key_present_when_key_set(self, client_with_key):
        """APIキー設定時 maps_key == 'present'。"""
        body = client_with_key.get("/api/health").json()
        assert body["maps_key"] == "present"

    def test_health_does_not_expose_key_value(self, client_with_key):
        """ヘルスチェックレスポンスにキー値が含まれない。"""
        text = client_with_key.get("/api/health").text
        assert "TEST_DUMMY_KEY_NOT_REAL" not in text


# ─────────────────────────────────────────────────────────────────────────────
# /api/runs テスト (§21.2)
# ─────────────────────────────────────────────────────────────────────────────

class TestRuns:
    def test_returns_200(self, client_no_key):
        res = client_no_key.get("/api/runs")
        assert res.status_code == 200

    def test_runs_is_list(self, client_no_key):
        body = client_no_key.get("/api/runs").json()
        assert "runs" in body
        assert isinstance(body["runs"], list)

    def test_run_has_required_fields(self, client_no_key):
        """run エントリは run_id / seed / ticks / agents / pois / interactions を持つ。"""
        body = client_no_key.get("/api/runs").json()
        assert len(body["runs"]) >= 1
        run = body["runs"][0]
        for field in ("run_id", "seed", "ticks", "agents", "pois", "interactions"):
            assert field in run, f"必須フィールド {field!r} が欠けている"

    def test_zero_runs_returns_empty_list(self, tmp_path, monkeypatch):
        """data ディレクトリが空でも 200 で空リストを返す。"""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        res = TestClient(app).get("/api/runs")
        assert res.status_code == 200
        assert res.json()["runs"] == []


# ─────────────────────────────────────────────────────────────────────────────
# /api/data/{run_id}/{file} テスト (§21.3)
# ─────────────────────────────────────────────────────────────────────────────

class TestDataEndpoint:

    # 許可ファイルが 200 で返ること
    @pytest.mark.parametrize("filename", [
        "pois.geojson",
        "aois.geojson",
        "roadnet.geojson",
        "agent_profiles_N100.json",
        "agent_states.jsonl",
        "interaction_events.jsonl",
        "summary.json",
    ])
    def test_allowed_file_returns_200(self, client_no_key, filename):
        """許可リスト内のファイルは 200 で返る。"""
        res = client_no_key.get(f"/api/data/test_run/{filename}")
        assert res.status_code == 200, f"{filename}: {res.text}"

    def test_geojson_content_type(self, client_no_key):
        """pois.geojson は application/geo+json で返る。"""
        res = client_no_key.get("/api/data/test_run/pois.geojson")
        assert res.status_code == 200
        assert "geo+json" in res.headers.get("content-type", "")

    def test_jsonl_content_type(self, client_no_key):
        """agent_states.jsonl は application/x-ndjson で返る。"""
        res = client_no_key.get("/api/data/test_run/agent_states.jsonl")
        assert res.status_code == 200
        ct = res.headers.get("content-type", "")
        assert "ndjson" in ct or "x-ndjson" in ct, f"unexpected content-type: {ct}"

    def test_jsonl_is_raw_stream_not_array(self, client_no_key):
        """JSONL は JSON 配列ではなく NDJSON 形式で返る (§21.3.2)。"""
        res = client_no_key.get("/api/data/test_run/agent_states.jsonl")
        assert res.status_code == 200
        # ボディは '[' で始まらない (JSON 配列ではない)
        assert not res.text.strip().startswith("["), "JSONL が JSON 配列として返っている"
        # 各行がパース可能な JSON オブジェクトである
        lines = [l for l in res.text.strip().split("\n") if l.strip()]
        assert len(lines) >= 1
        for line in lines:
            obj = json.loads(line)
            assert isinstance(obj, dict)

    def test_agent_states_has_required_fields(self, client_no_key):
        """agent_states.jsonl の各行に contract 必須フィールドが含まれる。"""
        res = client_no_key.get("/api/data/test_run/agent_states.jsonl")
        assert res.status_code == 200
        lines = [l for l in res.text.strip().split("\n") if l.strip()]
        for line in lines:
            obj = json.loads(line)
            for field in ("tick", "day", "time", "agent_id", "lat", "lon", "action", "status"):
                assert field in obj, f"必須フィールド {field!r} が欠けている: {obj}"

    # 未許可ファイル -> 403 (パストラバーサル文字を含む場合は FastAPI が 404 を先に返すことも許容)
    @pytest.mark.parametrize("filename", [
        "secrets.json",
        "config.py",
        ".env",
        "agent_states.jsonl.bak",
    ])
    def test_disallowed_file_returns_403(self, client_no_key, filename):
        """許可リスト外のファイルは 403 を返す (存在確認しない)。"""
        res = client_no_key.get(f"/api/data/test_run/{filename}")
        assert res.status_code == 403, f"{filename}: 403 expected, got {res.status_code}"

    @pytest.mark.parametrize("filename", [
        "../../etc/passwd",
        "../summary.json",
    ])
    def test_path_traversal_file_is_blocked(self, client_no_key, filename):
        """パストラバーサル文字を含むファイル指定は 200 を返さない (403 または 404)。

        FastAPI のルーティング層が先に 404 を返す場合もあるが、
        重要なのは 200 を返さないことである (§21.3.4)。
        """
        import urllib.parse
        url = f"/api/data/test_run/{urllib.parse.quote(filename, safe='')}"
        res = client_no_key.get(url)
        assert res.status_code in (403, 404), (
            f"パストラバーサル {filename!r} が {res.status_code} を返した (200 は不可)"
        )

    def test_nonexistent_run_returns_404(self, client_no_key):
        """存在しない run_id は 404 を返す。"""
        res = client_no_key.get("/api/data/no_such_run/summary.json")
        assert res.status_code == 404

    def test_missing_file_in_existing_run_returns_404(self, client_no_key, sample_run_dir):
        """run は存在するがファイルが無い場合は 404 を返す。"""
        # relationships.jsonl は生成されていない
        res = client_no_key.get("/api/data/test_run/relationships.jsonl")
        assert res.status_code == 404

    def test_path_traversal_run_id_returns_403(self, client_no_key):
        """run_id にパストラバーサル文字が含まれていれば 403 を返す。"""
        res = client_no_key.get("/api/data/../etc/summary.json")
        # FastAPI が 404 にする場合もある (path パラメータとして解釈しない)
        # 重要なのは 200 を返さないこと
        assert res.status_code in (403, 404, 422), (
            f"パストラバーサル run_id が 200 を返してはならない: {res.status_code}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET / (ビューア HTML) テスト (§5.1.1 / §13.4)
# ─────────────────────────────────────────────────────────────────────────────

class TestViewerHTML:

    def test_returns_200(self, client_no_key):
        """ルートは 200 を返す。"""
        res = client_no_key.get("/")
        assert res.status_code == 200

    def test_content_type_html(self, client_no_key):
        """レスポンスは text/html。"""
        res = client_no_key.get("/")
        ct = res.headers.get("content-type", "")
        assert "html" in ct, f"unexpected content-type: {ct}"

    def test_no_key_returns_fallback_html(self, client_no_key):
        """APIキー未設定時は fallback 地図モードの HTML を返す。

        app.js がプレースホルダ '%%GOOGLE_MAPS_API_KEY%%' を検出して
        fallback アダプタに切り替える設計 (§5.1.5)。
        Maps bootstrap loader の <script> タグが含まれない。
        """
        res = client_no_key.get("/")
        assert res.status_code == 200
        body = res.text
        # Maps bootstrap loader スクリプトが含まれない
        assert "maps.googleapis.com" not in body, (
            "APIキー未設定時に Maps bootstrap loader が HTML に含まれている"
        )

    def test_key_not_in_html_when_no_key(self, client_no_key):
        """APIキー未設定時、HTML にキー値が含まれない。"""
        res = client_no_key.get("/")
        assert "TEST_DUMMY_KEY_NOT_REAL" not in res.text

    def test_key_injected_in_maps_script_when_key_set(self, client_with_key):
        """APIキー設定時は Maps bootstrap loader が HTML に含まれる (§5.1.1)。

        キーは HTML に注入するのが仕様 (§5.1.1: サーバーが生成する HTML に埋め込む)。
        キーが git・ログ・health エンドポイントに漏れないことは他テストで確認済み。
        """
        res = client_with_key.get("/")
        assert res.status_code == 200
        # Maps API が設定されている時は bootstrap loader が含まれること
        assert "maps.googleapis.com" in res.text, (
            "APIキー設定時に Maps bootstrap loader が HTML に含まれていない"
        )

    def test_html_contains_app_js_script_tag(self, client_no_key):
        """HTML に app.js の script タグが含まれる。"""
        body = client_no_key.get("/").text
        assert "app.js" in body

    def test_html_does_not_500(self, client_no_key):
        """APIキー未設定でも 500 を返さない (§13.4 / §21.4)。"""
        res = client_no_key.get("/")
        assert res.status_code != 500


# ─────────────────────────────────────────────────────────────────────────────
# 許可リスト自体の完全性確認
# ─────────────────────────────────────────────────────────────────────────────

class TestAllowedFiles:
    def test_allowed_files_count_is_9(self):
        """許可ファイルは contract §21.3.1 の 9 件であること。"""
        assert len(ALLOWED_FILES) == 9

    @pytest.mark.parametrize("filename", [
        "pois.geojson",
        "aois.geojson",
        "roadnet.geojson",
        "agent_profiles_N100.json",
        "agent_states.jsonl",
        "poi_visit_records.jsonl",
        "interaction_events.jsonl",
        "relationships.jsonl",
        "summary.json",
    ])
    def test_expected_files_in_allowlist(self, filename):
        """contract で定義された 9 ファイルがすべて許可リストにある。"""
        assert filename in ALLOWED_FILES, f"{filename!r} が許可リストにない"
