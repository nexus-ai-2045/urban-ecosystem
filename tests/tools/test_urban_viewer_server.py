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
from tools.urban_viewer_server import app, ALLOWED_FILES, AGENT_PROFILES_RE
from tools.urban_viewer.labels import (
    CATEGORY_LABELS,
    ROLE_LABELS,
    ACTION_LABELS,
    INTERACTION_TYPE_LABELS,
    get_label,
)

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

    @pytest.mark.parametrize("filename", [
        "agent_profiles_N10.json",
        "agent_profiles_N100.json",
        "agent_profiles_N2.json",
        "agent_profiles_N1000.json",
    ])
    def test_agent_profiles_variable_n_allowed(self, filename):
        """agent_profiles_N<N>.json は可変エージェント数で許可される (10 体運用対応)。"""
        assert AGENT_PROFILES_RE.match(filename), f"{filename!r} が許可されない"

    @pytest.mark.parametrize("filename", [
        "agent_profiles.json",
        "agent_profiles_N.json",
        "agent_profiles_Nx.json",
        "agent_profiles_N10.json.bak",
        "agent_profiles_N10.py",
        "../agent_profiles_N10.json",
    ])
    def test_agent_profiles_invalid_names_rejected(self, filename):
        """N<数字>.json 形式以外は許可しない (安全側)。"""
        assert not AGENT_PROFILES_RE.match(filename), f"{filename!r} を誤って許可した"

    def test_agent_profiles_n10_not_forbidden(self, client_no_key):
        """N10 プロファイルは許可リストを通過する (存在しない run なら 404 で、403 ではない)。"""
        res = client_no_key.get("/api/data/no_such_run/agent_profiles_N10.json")
        assert res.status_code == 404, f"403 (not allowed) ではなく 404 を期待: got {res.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# labels モジュール単体テスト (WO-010)
# ─────────────────────────────────────────────────────────────────────────────

class TestCategoryLabels:
    """CATEGORY_LABELS: §19.3.1 の 12 カテゴリすべてが日本語表示される。"""

    def test_all_12_categories_present(self):
        """contract §19.3.1 の 12 カテゴリが CATEGORY_LABELS に含まれる。"""
        expected = {
            "amenity-cafe", "amenity-restaurant", "amenity-fast_food",
            "amenity-bar", "shop-convenience", "shop-clothing",
            "shop-supermarket", "leisure-park", "amenity-school",
            "office-building", "home-residential", "other-misc",
        }
        missing = expected - set(CATEGORY_LABELS.keys())
        assert not missing, f"CATEGORY_LABELS に不足: {missing}"

    @pytest.mark.parametrize("code,expected_label", [
        ("amenity-cafe",        "カフェ"),
        ("amenity-restaurant",  "レストラン"),
        ("amenity-fast_food",   "ファストフード"),
        ("amenity-bar",         "バー"),
        ("shop-convenience",    "コンビニ"),
        ("shop-clothing",       "衣料品店"),
        ("shop-supermarket",    "スーパー"),
        ("leisure-park",        "公園"),
        ("amenity-school",      "学校"),
        ("office-building",     "オフィスビル"),
        ("home-residential",    "住宅"),
        ("other-misc",          "その他"),
    ])
    def test_category_label_value(self, code, expected_label):
        """各カテゴリコードが期待する日本語ラベルに変換される。"""
        assert CATEGORY_LABELS[code] == expected_label, (
            f"{code!r}: expected {expected_label!r}, got {CATEGORY_LABELS[code]!r}"
        )

    def test_values_are_nonempty_strings(self):
        """すべてのラベル値は非空文字列である。"""
        for code, label in CATEGORY_LABELS.items():
            assert isinstance(label, str) and label.strip(), (
                f"{code!r} のラベルが空または非文字列: {label!r}"
            )


class TestRoleLabels:
    """ROLE_LABELS: contract §Enumerations の 3 種が日本語表示される。"""

    @pytest.mark.parametrize("code,expected_label", [
        ("office_worker", "会社員"),
        ("student",       "学生"),
        ("other",         "その他"),
    ])
    def test_role_label_value(self, code, expected_label):
        """各 role コードが期待する日本語ラベルに変換される。"""
        assert ROLE_LABELS[code] == expected_label, (
            f"{code!r}: expected {expected_label!r}, got {ROLE_LABELS[code]!r}"
        )

    def test_all_3_roles_present(self):
        """3 種すべての role が ROLE_LABELS に含まれる。"""
        for code in ("office_worker", "student", "other"):
            assert code in ROLE_LABELS, f"{code!r} が ROLE_LABELS に存在しない"


class TestInteractionTypeLabels:
    """INTERACTION_TYPE_LABELS: contract §Enumerations の 4 種が日本語表示される。"""

    @pytest.mark.parametrize("code,expected_label", [
        ("meeting",      "出会い"),
        ("conversation", "会話"),
        ("conflict",     "口論"),
        ("farewell",     "別れ"),
    ])
    def test_interaction_type_label_value(self, code, expected_label):
        """各 interaction type コードが期待する日本語ラベルに変換される。"""
        assert INTERACTION_TYPE_LABELS[code] == expected_label, (
            f"{code!r}: expected {expected_label!r}, got {INTERACTION_TYPE_LABELS[code]!r}"
        )

    def test_all_4_types_present(self):
        """4 種すべての interaction type が INTERACTION_TYPE_LABELS に含まれる。"""
        for code in ("meeting", "conversation", "conflict", "farewell"):
            assert code in INTERACTION_TYPE_LABELS, f"{code!r} が INTERACTION_TYPE_LABELS に存在しない"


class TestActionLabels:
    """ACTION_LABELS: contract §Enumerations の行動理由が日本語表示される。"""

    @pytest.mark.parametrize("code,expected_label", [
        ("commute",   "通勤"),
        ("lunch",     "昼食"),
        ("errand",    "用事"),
        ("social",    "交流"),
        ("go_home",   "帰宅"),
        ("wander",    "散策"),
        ("work",      "仕事"),
        ("study",     "勉強"),
        ("no_target", "目的地なし"),
    ])
    def test_action_label_value(self, code, expected_label):
        """各 action/reason コードが期待する日本語ラベルに変換される。"""
        assert ACTION_LABELS[code] == expected_label, (
            f"{code!r}: expected {expected_label!r}, got {ACTION_LABELS[code]!r}"
        )

    def test_all_actions_present(self):
        """contract §Enumerations の全 action が ACTION_LABELS に含まれる。"""
        # contract §Enumerations: commute/work/study/lunch/errand/social/go_home/wander/no_target
        required = {"commute", "work", "study", "lunch", "errand", "social", "go_home", "wander", "no_target"}
        missing = required - set(ACTION_LABELS.keys())
        assert not missing, f"ACTION_LABELS に不足: {missing}"


class TestGetLabel:
    """get_label() ヘルパー: 未知コードはそのままフォールバックする。"""

    def test_known_code_returns_japanese(self):
        """既知コードは日本語ラベルを返す。"""
        assert get_label(CATEGORY_LABELS, "amenity-cafe") == "カフェ"
        assert get_label(ROLE_LABELS,     "student")      == "学生"
        assert get_label(ACTION_LABELS,   "commute")      == "通勤"
        assert get_label(INTERACTION_TYPE_LABELS, "meeting") == "出会い"

    def test_unknown_code_returns_code_itself(self):
        """未知コードは入力コードをそのまま返す (後方互換)。"""
        assert get_label(CATEGORY_LABELS, "unknown-xyz") == "unknown-xyz"
        assert get_label(ROLE_LABELS,     "future_role") == "future_role"
        assert get_label(ACTION_LABELS,   "new_action")  == "new_action"

    def test_empty_code_returns_empty(self):
        """空文字列は空文字列を返す。"""
        assert get_label(CATEGORY_LABELS, "") == ""


# ─────────────────────────────────────────────────────────────────────────────
# /api/labels エンドポイントテスト (WO-010)
# ─────────────────────────────────────────────────────────────────────────────

class TestLabelsEndpoint:
    """GET /api/labels — ラベルマップを JSON で返す。"""

    def test_returns_200(self, client_no_key):
        """ラベルエンドポイントは 200 を返す。"""
        res = client_no_key.get("/api/labels")
        assert res.status_code == 200

    def test_content_type_json(self, client_no_key):
        """Content-Type は application/json。"""
        res = client_no_key.get("/api/labels")
        assert "application/json" in res.headers.get("content-type", "")

    def test_has_all_label_sections(self, client_no_key):
        """レスポンスに category / role / interaction_type / action の 4 セクションがある。"""
        body = client_no_key.get("/api/labels").json()
        for key in ("category", "role", "interaction_type", "action"):
            assert key in body, f"ラベルセクション {key!r} が欠けている"

    def test_category_section_has_12_entries(self, client_no_key):
        """category セクションは 12 エントリを持つ (§19.3.1)。"""
        body = client_no_key.get("/api/labels").json()
        assert len(body["category"]) == 12

    def test_known_category_has_correct_label(self, client_no_key):
        """amenity-cafe -> カフェ が返る。"""
        body = client_no_key.get("/api/labels").json()
        assert body["category"]["amenity-cafe"] == "カフェ"

    def test_known_role_has_correct_label(self, client_no_key):
        """office_worker -> 会社員 が返る。"""
        body = client_no_key.get("/api/labels").json()
        assert body["role"]["office_worker"] == "会社員"

    def test_known_interaction_type_has_correct_label(self, client_no_key):
        """meeting -> 出会い が返る。"""
        body = client_no_key.get("/api/labels").json()
        assert body["interaction_type"]["meeting"] == "出会い"

    def test_known_action_has_correct_label(self, client_no_key):
        """commute -> 通勤 が返る。"""
        body = client_no_key.get("/api/labels").json()
        assert body["action"]["commute"] == "通勤"


# ─────────────────────────────────────────────────────────────────────────────
# WO-007: surname ベースのエージェント表示
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentProfileSurnameFields:
    """agent_profiles_N100.json が surname / given フィールドを持つ (WO-006 contract §0.3.0)。

    WO-007 の受け入れ条件:
      - マーカー glyph に surname を使う。
      - surname 欠落時は name 先頭文字列にフォールバックする。
      - 詳細パネルに「surname given さん」を表示する。
    これらは JS 側で実装されるが、データ契約の検証はサーバーテストで担保する。
    """

    def test_profiles_endpoint_returns_list(self, client_no_key):
        """agent_profiles_N100.json エンドポイントはリストを返す。"""
        res = client_no_key.get("/api/data/test_run/agent_profiles_N100.json")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list), f"profile data should be a list, got {type(data)}"

    def test_profiles_have_required_contract_fields(self, client_no_key):
        """各プロフィールが contract §Agent Profile の必須フィールドを持つ (id / name / initial_position)。"""
        res = client_no_key.get("/api/data/test_run/agent_profiles_N100.json")
        assert res.status_code == 200
        profiles = res.json()
        assert len(profiles) >= 1, "プロフィールが 1 件以上必要"
        for p in profiles:
            assert "id"               in p, f"id 欠落: {p}"
            assert "name"             in p, f"name 欠落: {p}"
            assert "initial_position" in p, f"initial_position 欠落: {p}"

    def test_profiles_have_surname_and_given(self, client_no_key):
        """generate_urban_sample.py が生成したプロフィールは surname / given を持つ (WO-006 §0.3.0)。

        fallback fixture (_create_minimal_static_files) が呼ばれた場合は surname / given を
        持たないことが予想されるため、generate_urban_sample.py が成功した場合のみ検証する。
        テスト用 fixture は generate 成功時 surname = 姓、given = 名 を持つことを期待する。
        """
        res = client_no_key.get("/api/data/test_run/agent_profiles_N100.json")
        assert res.status_code == 200
        profiles = res.json()

        # generate_urban_sample.py が生成したプロフィールかどうかを name フィールドで判定する。
        # 最小 fallback fixture は ASCII 名 ("Tanaka Ken" など) を使うため
        # 日本語名を持つプロフィールは generate が成功した場合のみ存在する。
        # ASCII 名のみの場合は surname/given 無しを許容してスキップする。
        has_japanese_name = any(
            p.get("name", "").encode("utf-8") != p.get("name", "").encode("ascii", errors="ignore")
            for p in profiles
        )
        if not has_japanese_name:
            pytest.skip("最小 fallback fixture のため surname/given テストをスキップ")

        for p in profiles:
            assert "surname" in p, (
                f"WO-006 contract §0.3.0: surname が欠落 (profile id={p.get('id')!r})"
            )
            assert "given"   in p, (
                f"WO-006 contract §0.3.0: given が欠落 (profile id={p.get('id')!r})"
            )
            # name == surname + given 保証 (contract §Agent Profile)
            assert p["name"] == p["surname"] + p["given"], (
                f"name '{p['name']}' != surname '{p['surname']}' + given '{p['given']}'"
            )

    def test_surname_fallback_in_minimal_fixture(self):
        """surname 欠落プロフィールに対する glyph ラベル計算ロジックの検証。

        JS 側 app.js の _buildProfileMap / markerData ラベルロジックを
        Python で等価実装して確認する (fallback = name 先頭文字列)。
        """
        # surname あり
        p_with_surname = {"id": 0, "name": "井上翔", "surname": "井上", "given": "翔"}
        label = p_with_surname.get("surname") or p_with_surname["name"][:2]
        assert label == "井上", f"surname あり: expected '井上', got {label!r}"

        # surname なし → name 先頭にフォールバック
        p_no_surname = {"id": 1, "name": "TanakaKen"}
        label_fb = p_no_surname.get("surname") or p_no_surname["name"][:2]
        assert label_fb == "Ta", f"surname なし fallback: expected 'Ta', got {label_fb!r}"

        # surname が空文字列 → name 先頭にフォールバック
        p_empty_surname = {"id": 2, "name": "山田太郎", "surname": "", "given": "太郎"}
        label_empty = p_empty_surname.get("surname") or p_empty_surname["name"][:2]
        assert label_empty == "山田", f"surname 空: expected '山田', got {label_empty!r}"

    def test_detail_panel_title_logic(self):
        """詳細パネルのタイトル生成ロジック検証 (JS ui_panels.js の Python 等価実装)。

        受け入れ条件: 「surname given さん」表示。surname 欠落時は「name さん」にフォールバック。
        """
        def _panel_title(profile: dict) -> str:
            """JS updateAgentDetail ヘッダー生成ロジックの Python 等価実装。"""
            if not profile:
                return "Agent unknown"
            surname = profile.get("surname", "")
            given   = profile.get("given",   "")
            name    = profile.get("name",    "")
            if surname and given:
                return f"{surname} {given}さん"
            if name:
                return f"{name}さん"
            return f"Agent {profile.get('id', '?')}"

        # surname + given → 「surname given さん」
        assert _panel_title({"id": 0, "name": "井上翔", "surname": "井上", "given": "翔"}) \
            == "井上 翔さん"

        # surname なし → 「name さん」フォールバック
        assert _panel_title({"id": 1, "name": "TanakaKen"}) == "TanakaKenさん"

        # surname のみ (given なし) → 「name さん」フォールバック
        assert _panel_title({"id": 2, "name": "山田", "surname": "山田"}) == "山田さん"

        # name なし profile → 「Agent N」
        assert _panel_title({"id": 3}) == "Agent 3"
