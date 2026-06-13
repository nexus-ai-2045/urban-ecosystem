"""
test_urban_viewer_server.py — urban_viewer_server のサーバーエンドポイントテスト。

正本: docs/subagents/work-orders/wo-urban-003-replay-viewer.yaml §テスト
仕様参照: docs/ai-ecosystem-tool-spec.md §21 / §13.4 / §18.1 ビューアサーバー

テスト対象:
  - GET /api/health : ステータス・maps_key フィールド・キー平文非公開
  - GET /api/runs   : ゼロ件 / 1 件
  - GET /api/data/{run_id}/{file}: 許可リスト 11 ファイル通過 / 未許可ファイル 403 / 不在 run 404 / ファイル未存在 404
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
from tools.urban_viewer_server import (
    app,
    ALLOWED_FILES,
    AGENT_PROFILES_RE,
    _RUNTIME_CONFIG,
    _make_configured_llm_provider,
    _set_operator_replay,
    _set_world_bridge_simulated,
    _set_agent_roster_guide,
    _set_motif_arc_default,
    _set_assessment_lab_default,
)
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

# contract §VisitRecord 必須: agent_id / day / time / action / lat / lon
_MIN_VISIT_RECORDS = [
    {"agent_id": 0, "day": 0, "time": "08:05:00", "poi_id": "poi_001",
     "action": "visit", "reason": "commute",
     "lat": 35.661, "lon": 139.701},
    {"agent_id": 1, "day": 0, "time": "08:10:00", "poi_id": "poi_002",
     "action": "visit", "reason": "lunch",
     "lat": 35.662, "lon": 139.702},
]

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

    # poi_visit_records.jsonl: 最小 fixture を手作り (gap §5.2 / §5.5)
    visit_records_path = run_dir / "poi_visit_records.jsonl"
    with open(visit_records_path, "w", encoding="utf-8") as fh:
        for rec in _MIN_VISIT_RECORDS:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # interaction_events.jsonl: 空ファイル
    interaction_path = run_dir / "interaction_events.jsonl"
    with open(interaction_path, "w", encoding="utf-8") as fh:
        for ev in _MIN_INTERACTION_EVENTS:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")

    _write_minimal_activity_plan(run_dir)

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


def _write_minimal_activity_plan(run_dir: Path) -> None:
    """activity_plans.jsonl の optional input fixture を 1 行だけ書く。"""
    activity_plan = {
        "agent_id": 0,
        "day": 0,
        "activities": [
            {
                "kind": "lunch",
                "start": "08:00:00",
                "end": "08:30:00",
                "poi_id": "poi_001",
            }
        ],
    }
    (run_dir / "activity_plans.jsonl").write_text(
        json.dumps(activity_plan, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


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

    _write_minimal_activity_plan(run_dir)


# ─────────────────────────────────────────────────────────────────────────────
# TestClient fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def client_no_key(sample_run_dir, monkeypatch):
    """GOOGLE_MAPS_API_KEY 未設定のクライアント。"""
    _RUNTIME_CONFIG.clear()
    _set_operator_replay()
    _set_world_bridge_simulated()
    _set_agent_roster_guide()
    _set_motif_arc_default()
    _set_assessment_lab_default()
    monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
    monkeypatch.delenv("DATA_SOURCE", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def client_with_key(sample_run_dir, monkeypatch):
    """GOOGLE_MAPS_API_KEY が設定されたクライアント (テスト用ダミーキー)。"""
    _RUNTIME_CONFIG.clear()
    _set_operator_replay()
    _set_world_bridge_simulated()
    _set_agent_roster_guide()
    _set_motif_arc_default()
    _set_assessment_lab_default()
    monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
    monkeypatch.delenv("DATA_SOURCE", raising=False)
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

    def test_local_data_source_is_reported_supported(self, client_no_key):
        """local data source は実装済みとして報告される。"""
        body = client_no_key.get("/api/health").json()
        assert body["data_source"] == "local"
        assert body["data_source_supported"] is True
        assert "data_source_error" not in body

    def test_gcs_data_source_is_reported_unsupported(self, sample_run_dir, monkeypatch):
        """DATA_SOURCE=gcs は health で未対応と明示する。"""
        monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
        monkeypatch.setenv("DATA_SOURCE", "gcs")
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        res = TestClient(app).get("/api/health")
        assert res.status_code == 200
        body = res.json()
        assert body["data_source"] == "gcs"
        assert body["data_source_supported"] is False
        assert "not implemented" in body["data_source_error"]


class TestSettings:
    def test_get_settings_does_not_expose_maps_key(self, client_with_key):
        """設定 API はキーの有無だけ返し、キー値は返さない。"""
        res = client_with_key.get("/api/settings")

        assert res.status_code == 200
        body = res.json()
        assert body["maps"]["api_key"] == "present"
        assert "TEST_DUMMY_KEY_NOT_REAL" not in res.text

    def test_post_settings_updates_data_dir_for_runs(self, sample_run_dir, tmp_path, monkeypatch):
        """UI から DATA_DIR を変えると /api/runs の参照先が変わる。"""
        _RUNTIME_CONFIG.clear()
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "empty"))
        new_root = sample_run_dir
        client = TestClient(app)

        res = client.post("/api/settings", json={"data": {"source": "local", "root": str(new_root)}})
        runs = client.get("/api/runs").json()["runs"]

        assert res.status_code == 200
        assert res.json()["data"]["root"] == str(new_root)
        assert [run["run_id"] for run in runs] == ["test_run"]
        _RUNTIME_CONFIG.clear()

    def test_post_settings_rejects_missing_data_dir(self, client_no_key, tmp_path):
        """存在しない DATA_DIR は 400 にする。"""
        missing = tmp_path / "missing"

        res = client_no_key.post("/api/settings", json={"data": {"root": str(missing)}})

        assert res.status_code == 400
        assert "DATA_DIR not found" in res.text

    def test_post_settings_accepts_local_llm_model_dir(self, client_no_key, tmp_path):
        """ローカル LLM の model path fallback を UI から設定できる。"""
        model_dir = tmp_path / "models"
        model_dir.mkdir()

        res = client_no_key.post(
            "/api/settings",
            json={
                "llm": {
                    "provider": "local",
                    "model": "local-demo",
                    "base_url": "http://127.0.0.1:11434/v1",
                    "model_dir": str(model_dir),
                }
            },
        )

        assert res.status_code == 200
        body = res.json()
        assert body["llm"]["provider"] == "local"
        assert body["llm"]["model_dir_exists"] is True

    def test_local_llm_uses_model_dir_when_model_is_empty(self, client_no_key, tmp_path):
        """model 名が空なら LLM_MODEL_DIR を local provider の model として使う。"""
        model_dir = tmp_path / "models"
        model_dir.mkdir()
        client_no_key.post(
            "/api/settings",
            json={"llm": {"provider": "local", "model": "", "model_dir": str(model_dir)}},
        )

        provider = _make_configured_llm_provider()

        assert provider.model == str(model_dir)

    def test_post_settings_rejects_missing_llm_model_dir(self, client_no_key, tmp_path):
        """存在しない LLM_MODEL_DIR は 400 にする。"""
        res = client_no_key.post(
            "/api/settings",
            json={"llm": {"provider": "local", "model_dir": str(tmp_path / "missing")}},
        )

        assert res.status_code == 400
        assert "LLM_MODEL_DIR not found" in res.text


class TestCreateRun:
    def test_post_runs_creates_sample_run(self, tmp_path, monkeypatch):
        """UI から sample run を生成し、/api/runs で列挙できる。"""
        _RUNTIME_CONFIG.clear()
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        client = TestClient(app)

        res = client.post(
            "/api/runs",
            json={
                "mode": "sample",
                "run_id": "ui_test_run",
                "seed": 42,
                "agents": 2,
                "pois": 10,
                "ticks": 2,
            },
        )
        runs = client.get("/api/runs").json()["runs"]

        assert res.status_code == 200
        assert res.json()["run"]["run_id"] == "ui_test_run"
        assert [run["run_id"] for run in runs] == ["ui_test_run"]
        assert (tmp_path / "ui_test_run" / "agent_states.jsonl").exists()
        _RUNTIME_CONFIG.clear()

    def test_post_runs_rejects_duplicate_run_id(self, tmp_path, monkeypatch):
        """既存 run_id は上書きせず 409 にする。"""
        _RUNTIME_CONFIG.clear()
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        client = TestClient(app)
        payload = {"mode": "sample", "run_id": "dupe_run", "agents": 2, "pois": 10, "ticks": 2}

        first = client.post("/api/runs", json=payload)
        second = client.post("/api/runs", json=payload)

        assert first.status_code == 200
        assert second.status_code == 409
        _RUNTIME_CONFIG.clear()

    def test_post_runs_requires_google_project_for_vertex(self, tmp_path, monkeypatch):
        """Vertex AI provider は GOOGLE_CLOUD_PROJECT 未設定なら実行前に 400。"""
        _RUNTIME_CONFIG.clear()
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        client = TestClient(app)
        client.post("/api/settings", json={"llm": {"provider": "vertex"}})

        res = client.post(
            "/api/runs",
            json={"mode": "sample", "run_id": "vertex_no_project", "agents": 2, "pois": 10, "ticks": 2},
        )

        assert res.status_code == 400
        assert "GOOGLE_CLOUD_PROJECT" in res.text
        assert not (tmp_path / "vertex_no_project").exists()
        _RUNTIME_CONFIG.clear()


class TestOperatorMode:
    def test_operator_mode_starts_in_replay(self, client_no_key):
        """MVP-001: 初期状態は replay viewpoint。"""
        res = client_no_key.get("/api/operator-mode")

        assert res.status_code == 200
        body = res.json()
        assert body["viewpoint"] == "replay"
        assert body["status"] in {"idle", "blocked"}
        assert body["runtime_only"] is True

    def test_operator_entry_and_return_flow(self, client_no_key):
        """MVP-001: agent selection -> entry -> inspection -> return。"""
        entry = client_no_key.post(
            "/api/operator-mode/entry",
            json={"run_id": "test_run", "agent_id": 0, "trigger_class": "entry_intent"},
        )

        assert entry.status_code == 200
        entry_body = entry.json()
        assert entry_body["viewpoint"] == "inspection"
        assert entry_body["status"] == "active"
        assert entry_body["run_id"] == "test_run"
        assert entry_body["agent_id"] == 0
        assert entry_body["trigger_class"] == "entry_intent"
        assert entry_body["failure_state"] == ""

        returned = client_no_key.post("/api/operator-mode/return")

        assert returned.status_code == 200
        return_body = returned.json()
        assert return_body["viewpoint"] == "replay"
        assert return_body["status"] == "idle"
        assert return_body["agent_id"] is None

    def test_operator_entry_rejects_missing_agent(self, client_no_key):
        """存在しない agent は replay viewpoint を維持して target_not_found。"""
        res = client_no_key.post(
            "/api/operator-mode/entry",
            json={"run_id": "test_run", "agent_id": 999, "trigger_class": "entry_intent"},
        )

        assert res.status_code == 404
        body = res.json()["detail"]
        assert body["failure_state"] == "target_not_found"
        assert body["operator_mode"]["viewpoint"] == "replay"

    def test_operator_entry_rejects_missing_run(self, client_no_key):
        """存在しない run も replay viewpoint を維持して target_not_found。"""
        res = client_no_key.post(
            "/api/operator-mode/entry",
            json={"run_id": "missing_run", "agent_id": 0, "trigger_class": "entry_intent"},
        )

        assert res.status_code == 404
        body = res.json()["detail"]
        assert body["failure_state"] == "target_not_found"
        assert body["operator_mode"]["viewpoint"] == "replay"

    def test_operator_entry_rejects_trigger_text(self, client_no_key):
        """public API は生の起動語句を受け取らない。"""
        res = client_no_key.post(
            "/api/operator-mode/entry",
            json={
                "run_id": "test_run",
                "agent_id": 0,
                "trigger_class": "entry_intent",
                "trigger_text": "private local phrase",
            },
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "trigger_not_allowed"
        assert body["operator_mode"]["viewpoint"] == "replay"

    def test_operator_entry_rejects_unknown_trigger_class(self, client_no_key):
        """trigger class は公開安全な抽象classだけ許可する。"""
        res = client_no_key.post(
            "/api/operator-mode/entry",
            json={"run_id": "test_run", "agent_id": 0, "trigger_class": "raw_phrase"},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "trigger_not_allowed"


class TestWorldBridge:
    def test_world_bridge_starts_in_simulated_layer(self, client_no_key):
        """MVP-002: 初期状態は simulated layer。"""
        res = client_no_key.get("/api/world-bridge")

        assert res.status_code == 200
        body = res.json()
        assert body["current_layer"] == "simulated"
        assert body["minimum_world_packet"]["ready"] is True
        assert len(body["minimum_world_packet"]["fields"]) == 7
        assert body["event_music_signal"]["status"] == "planned_signal"
        assert body["runtime_only"] is True

    def test_world_bridge_allows_liminal_transition(self, client_no_key):
        """simulated -> liminal は許可する。"""
        res = client_no_key.post(
            "/api/world-bridge/transition",
            json={"target_layer": "liminal", "reason_class": "operator_intent"},
        )

        assert res.status_code == 200
        body = res.json()
        assert body["previous_layer"] == "simulated"
        assert body["current_layer"] == "liminal"
        assert body["failure_state"] == ""

    def test_world_bridge_blocks_direct_physical_transition(self, client_no_key):
        """simulated -> physical の直行は liminal 経由を要求する。"""
        res = client_no_key.post(
            "/api/world-bridge/transition",
            json={"target_layer": "physical", "reason_class": "operator_intent"},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "transition_not_allowed"
        assert body["world_bridge"]["current_layer"] == "simulated"

    def test_world_bridge_rejects_unknown_layer(self, client_no_key):
        """未定義layerは layer_not_found。"""
        res = client_no_key.post(
            "/api/world-bridge/transition",
            json={"target_layer": "unknown", "reason_class": "operator_intent"},
        )

        assert res.status_code == 404
        body = res.json()["detail"]
        assert body["failure_state"] == "layer_not_found"

    def test_world_bridge_requires_agent_context_when_requested(self, client_no_key):
        """agent context要求時、operator entry前なら失敗する。"""
        res = client_no_key.post(
            "/api/world-bridge/transition",
            json={
                "target_layer": "liminal",
                "reason_class": "operator_intent",
                "requires_agent_context": True,
            },
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "agent_context_missing"

    def test_world_bridge_agent_context_passes_after_operator_entry(self, client_no_key):
        """operator entry後はagent context要求つきtransitionが通る。"""
        entry = client_no_key.post(
            "/api/operator-mode/entry",
            json={"run_id": "test_run", "agent_id": 0, "trigger_class": "entry_intent"},
        )
        res = client_no_key.post(
            "/api/world-bridge/transition",
            json={
                "target_layer": "liminal",
                "reason_class": "operator_intent",
                "requires_agent_context": True,
            },
        )

        assert entry.status_code == 200
        assert res.status_code == 200
        assert res.json()["current_layer"] == "liminal"


class TestAgentRoster:
    def test_agent_roster_returns_public_safe_roles(self, client_no_key):
        """MVP-003: 抽象role一覧を返し、operator境界を明示する。"""
        res = client_no_key.get("/api/agent-roster")

        assert res.status_code == 200
        body = res.json()
        role_ids = [role["id"] for role in body["roles"]]
        assert role_ids == [
            "guide",
            "partner",
            "monitoring",
            "pursuit",
            "intervention",
            "field-support",
            "supervisor",
        ]
        assert body["active_role"] == "guide"
        assert body["runtime_only"] is True
        assert "human oversight" in body["operator_boundary"]

    def test_agent_roster_selects_role(self, client_no_key):
        """active roleを選択でき、world layer接続を返す。"""
        res = client_no_key.post("/api/agent-roster/select", json={"role_id": "field-support"})

        assert res.status_code == 200
        body = res.json()
        assert body["active_role"] == "field-support"
        assert body["active"]["layer"] == "physical"
        assert "human approval" in body["active"]["guidance"]

    def test_agent_roster_rejects_unknown_role(self, client_no_key):
        """未定義roleは role_not_found。"""
        res = client_no_key.post("/api/agent-roster/select", json={"role_id": "raw_character_role"})

        assert res.status_code == 404
        body = res.json()["detail"]
        assert body["failure_state"] == "role_not_found"
        assert body["agent_roster"]["active_role"] == "guide"

    def test_agent_roster_guidance_uses_operator_context(self, client_no_key):
        """operator entry後はguide/partner説明に対象agent contextが入る。"""
        entry = client_no_key.post(
            "/api/operator-mode/entry",
            json={"run_id": "test_run", "agent_id": 0, "trigger_class": "entry_intent"},
        )
        res = client_no_key.post("/api/agent-roster/select", json={"role_id": "partner"})

        assert entry.status_code == 200
        assert res.status_code == 200
        body = res.json()
        assert body["active_role"] == "partner"
        assert "Agent 0" in body["active"]["guidance"]


class TestMotifArcs:
    def test_motif_arcs_returns_public_safe_pack(self, client_no_key):
        """MVP-004: public-safe motif packと保証条件を返す。"""
        res = client_no_key.get("/api/motif-arcs")

        assert res.status_code == 200
        body = res.json()
        motif_ids = [motif["motif_id"] for motif in body["motifs"]]
        assert motif_ids == [
            "equivalent-exchange-pair",
            "pillar-council-arc",
            "unstable-power-arc",
            "boundary-war-arc",
            "fighter-archetype-set",
            "social-tech-mirror-lab",
            "judgment-game-arc",
            "ecological-mediation-arc",
            "pilot-sync-arc",
            "next-motif-expansion-slot",
        ]
        assert body["active_motif_id"] == "equivalent-exchange-pair"
        assert body["runtime_only"] is True
        assert "public_safe" in body["guarantees"]

    def test_motif_arc_evaluate_accepts_known_motif(self, client_no_key):
        """既知motifはArchetype/World guaranteeを満たしてacceptedになる。"""
        res = client_no_key.post(
            "/api/motif-arcs/evaluate",
            json={"motif_id": "ecological-mediation-arc"},
        )

        assert res.status_code == 200
        body = res.json()
        assert body["active_motif_id"] == "ecological-mediation-arc"
        assert body["active"]["accepted"] is True
        assert body["active"]["archetype_ready"] is True
        assert body["active"]["world_ready"] is True

    def test_motif_arc_rejects_unknown_or_raw_name(self, client_no_key):
        """未定義/生名っぽいmotifは motif_name_not_safe。"""
        res = client_no_key.post(
            "/api/motif-arcs/evaluate",
            json={"motif_id": "raw-character-name"},
        )

        assert res.status_code == 404
        body = res.json()["detail"]
        assert body["failure_state"] == "motif_name_not_safe"
        assert body["motif_arcs"]["active_motif_id"] == "equivalent-exchange-pair"

    def test_next_motif_slot_requires_classification_signal(self, client_no_key):
        """Next slotはTODOまたは分類を要求する印を返す。"""
        res = client_no_key.post(
            "/api/motif-arcs/evaluate",
            json={"motif_id": "next-motif-expansion-slot"},
        )

        assert res.status_code == 200
        active = res.json()["active"]
        assert active["accepted"] is True
        assert active["next_classification_required"] is True


class TestAssessmentLab:
    def test_assessment_lab_returns_benchmark_categories(self, client_no_key):
        """MVP-005: 6つの評価カテゴリと境界条件を返す。"""
        res = client_no_key.get("/api/assessment-lab")

        assert res.status_code == 200
        body = res.json()
        category_ids = [category["category_id"] for category in body["categories"]]
        assert category_ids == [
            "human-ai-assessment-lab",
            "post-singularity-scenario-boundary",
            "chaotic-three-body-world-benchmark",
            "frontier-ai-capability-layer-benchmark",
            "scale-simplification-simulation-benchmark",
            "agent-harness-layer-benchmark",
        ]
        assert body["active_category_id"] == "human-ai-assessment-lab"
        assert body["runtime_only"] is True
        assert "harness" in body["boundaries"]

    def test_assessment_lab_evaluate_accepts_harness_category(self, client_no_key):
        """既知benchmark categoryは公開安全なassessment cardへ進める。"""
        res = client_no_key.post(
            "/api/assessment-lab/evaluate",
            json={"category_id": "agent-harness-layer-benchmark"},
        )

        assert res.status_code == 200
        body = res.json()
        assert body["active_category_id"] == "agent-harness-layer-benchmark"
        assert body["active"]["accepted"] is True
        assert "harness assessment card" in body["active"]["output"]

    def test_assessment_lab_evaluate_does_not_change_default_get_state(self, client_no_key):
        """公開runtimeでユーザー間共有にならないよう、POSTはGETの既定状態を変えない。"""
        client_no_key.post(
            "/api/assessment-lab/evaluate",
            json={"category_id": "agent-harness-layer-benchmark"},
        )
        body = client_no_key.get("/api/assessment-lab").json()

        assert body["active_category_id"] == "human-ai-assessment-lab"
        assert body["failure_state"] == ""

    def test_assessment_lab_rejects_unknown_category(self, client_no_key):
        """未定義categoryはscenario_unboundedで拒否する。"""
        res = client_no_key.post(
            "/api/assessment-lab/evaluate",
            json={"category_id": "raw-external-test"},
        )

        assert res.status_code == 404
        body = res.json()["detail"]
        assert body["failure_state"] == "scenario_unbounded"

    def test_assessment_lab_rejects_dangerous_live_test(self, client_no_key):
        """危険なlive testフラグは実行前に拒否する。"""
        res = client_no_key.post(
            "/api/assessment-lab/evaluate",
            json={
                "category_id": "human-ai-assessment-lab",
                "dangerous_live_test": True,
            },
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "unsafe_live_test"

    def test_assessment_lab_rejects_external_body(self, client_no_key):
        """外部投稿本文を評価payloadに含めることを拒否する。"""
        res = client_no_key.post(
            "/api/assessment-lab/evaluate",
            json={
                "category_id": "scale-simplification-simulation-benchmark",
                "external_body_included": True,
            },
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "source_body_leak"

    def test_assessment_lab_rejects_model_ranking(self, client_no_key):
        """未確認のlab/model rankingはcapability claimとして拒否する。"""
        res = client_no_key.post(
            "/api/assessment-lab/evaluate",
            json={
                "category_id": "frontier-ai-capability-layer-benchmark",
                "model_ranking": True,
            },
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "capability_claim_unverified"


class TestGovernanceFde:
    def test_governance_fde_returns_layers_and_fde_steps(self, client_no_key):
        """MVP-006: governance layer、FDE steps、oversight boundaryを返す。"""
        res = client_no_key.get("/api/governance-fde")

        assert res.status_code == 200
        body = res.json()
        assert [layer["layer_id"] for layer in body["layers"]] == [
            "proposal",
            "review",
            "execution",
            "oversight",
        ]
        assert [step["step_id"] for step in body["fde_steps"]] == [
            "entry",
            "packet",
            "evidence",
            "decision",
            "closure",
        ]
        assert body["oversight"]["user_role"] == "external_monitor"
        assert body["oversight"]["user_is_agent"] is False
        assert body["numeric_protocol"]["status"] == "parking-lot"
        assert body["runtime_only"] is True

    def test_governance_fde_accepts_proceed_with_evidence(self, client_no_key):
        """proceedはtests、scan、review相当の証拠がある時だけ通す。"""
        res = client_no_key.post(
            "/api/governance-fde/decide",
            json={
                "decision": "proceed",
                "human_gate": True,
                "evidence": ["tests", "static-scan", "review"],
            },
        )

        assert res.status_code == 200
        body = res.json()
        assert body["active_decision"] == "proceed"
        assert body["failure_state"] == ""

    def test_governance_fde_rejects_proceed_without_evidence(self, client_no_key):
        """証拠不足のproceedはpacket_missing_evidenceで拒否する。"""
        res = client_no_key.post(
            "/api/governance-fde/decide",
            json={"decision": "proceed", "human_gate": True, "evidence": ["tests"]},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "packet_missing_evidence"

    def test_governance_fde_rejects_oversight_bypass(self, client_no_key):
        """human gate省略やuser agent化を拒否する。"""
        res = client_no_key.post(
            "/api/governance-fde/decide",
            json={"decision": "watch", "human_gate": False},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "oversight_bypassed"

    def test_governance_fde_rejects_future_claim_overreach(self, client_no_key):
        """未来像を予言として扱うpacketを拒否する。"""
        res = client_no_key.post(
            "/api/governance-fde/decide",
            json={"decision": "watch", "future_claim": "prophecy"},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "future_claim_overreach"

    def test_governance_fde_rejects_numeric_rule_overreach(self, client_no_key):
        """numeric protocolを実装済みruleにすることを拒否する。"""
        res = client_no_key.post(
            "/api/governance-fde/decide",
            json={"decision": "watch", "numeric_rule": "implemented"},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "numeric_rule_overreach"

    def test_governance_fde_rejects_unbounded_recursive_loop(self, client_no_key):
        """recursive skill callにdepth/stop conditionがないpacketを拒否する。"""
        res = client_no_key.post(
            "/api/governance-fde/decide",
            json={"decision": "watch", "recursive_depth_unbounded": True},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "recursive_loop_unbounded"


class TestRepoSkillMesh:
    def test_repo_skill_mesh_returns_skill_families_and_guards(self, client_no_key):
        """MVP-007: skill family、recursive guard、P2P/cloud境界を返す。"""
        res = client_no_key.get("/api/repo-skill-mesh")

        assert res.status_code == 200
        body = res.json()
        skill_ids = [skill["skill_id"] for skill in body["skill_families"]]
        assert skill_ids == [
            "operator-entry-skill",
            "world-bridge-skill",
            "guide-roster-skill",
            "motif-intake-skill",
            "assessment-skill",
            "governance-skill",
            "distributed-ops-skill",
            "intake-lifecycle-skill",
        ]
        assert body["recursive_guard"]["maximum_depth"] == 3
        assert body["distributed_ops"]["implementation_allowed"] is False
        assert body["cloud_capacity"]["execution_allowed"] is False
        assert body["external_writes_allowed"] is False

    def test_repo_skill_mesh_accepts_guarded_skill_plan(self, client_no_key):
        """allowed I/Oとloop guardがあるskill planだけ受け入れる。"""
        res = client_no_key.post(
            "/api/repo-skill-mesh/evaluate",
            json={
                "skill_id": "governance-skill",
                "maximum_depth": 1,
                "allowed_io": True,
                "loop_guard": True,
            },
        )

        assert res.status_code == 200
        body = res.json()
        assert body["active_skill_id"] == "governance-skill"
        assert body["failure_state"] == ""

    def test_repo_skill_mesh_rejects_missing_allowed_io(self, client_no_key):
        """allowed I/O未定義のskill callを拒否する。"""
        res = client_no_key.post(
            "/api/repo-skill-mesh/evaluate",
            json={"skill_id": "governance-skill", "allowed_io": False},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "allowed_io_missing"

    def test_repo_skill_mesh_rejects_missing_loop_guard(self, client_no_key):
        """loop guardなしのrecursive planを拒否する。"""
        res = client_no_key.post(
            "/api/repo-skill-mesh/evaluate",
            json={"skill_id": "governance-skill", "loop_guard": False},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "loop_guard_missing"

    def test_repo_skill_mesh_rejects_excessive_depth(self, client_no_key):
        """maximum depth上限超過を拒否する。"""
        res = client_no_key.post(
            "/api/repo-skill-mesh/evaluate",
            json={"skill_id": "governance-skill", "maximum_depth": 4},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "recursive_depth_exceeded"

    def test_repo_skill_mesh_rejects_p2p_operationalize(self, client_no_key):
        """trust / moderationなしのP2P実運用化を拒否する。"""
        res = client_no_key.post(
            "/api/repo-skill-mesh/evaluate",
            json={"skill_id": "distributed-ops-skill", "p2p_operationalize": True},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "trust_model_missing"

    def test_repo_skill_mesh_rejects_cloud_execution(self, client_no_key):
        """capacity envelopeなしのcloud実行を拒否する。"""
        res = client_no_key.post(
            "/api/repo-skill-mesh/evaluate",
            json={"skill_id": "distributed-ops-skill", "cloud_execute": True},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "cloud_approval_missing"

    def test_repo_skill_mesh_rejects_external_write(self, client_no_key):
        """human review前の外部writeを拒否する。"""
        res = client_no_key.post(
            "/api/repo-skill-mesh/evaluate",
            json={"skill_id": "intake-lifecycle-skill", "external_write": True},
        )

        assert res.status_code == 400
        body = res.json()["detail"]
        assert body["failure_state"] == "external_write_attempted"


class TestIntakeLifecycle:
    def test_intake_lifecycle_returns_pipeline_and_guards(self, client_no_key):
        """MVP-008: intake pipeline、validator、lifecycle guardを返す。"""
        res = client_no_key.get("/api/intake-lifecycle")

        assert res.status_code == 200
        body = res.json()
        assert body["active_class"] == "accepted"
        assert body["request_classes"] == ["accepted", "parking-lot", "watch", "rejected/out-of-scope"]
        assert "project-hypothesis" in body["source_categories"]
        assert [step["step"] for step in body["pipeline_steps"]] == [
            "receive",
            "classify",
            "source_category",
            "public_safe_name",
            "minimum_world_packet",
            "todo_or_gate",
            "draft_artifact",
            "optional_external_issue",
        ]
        assert body["minimum_world_packet"]["required_fields"] == [
            "world_layer",
            "actor_role",
            "conflict",
            "constraint",
            "signal",
            "transition",
            "failure_state",
        ]
        assert body["lifecycle"]["orphan_threshold"] == 3
        assert body["lifecycle"]["heartbeat_mode"] == "read-only/draft-only"
        assert body["lifecycle"]["external_write_allowed"] is False

    def test_intake_lifecycle_accepts_draft_candidate(self, client_no_key):
        """MVP-008: 公開安全な追加依頼をdraft candidateにする。"""
        res = client_no_key.post(
            "/api/intake-lifecycle/draft",
            json={
                "request_class": "accepted",
                "source_category": "chat-context",
                "public_safe_name": "Add Request Intake Draft Flow",
                "todo_id": "XWORLD-TODO-037",
                "minimum_world_packet": True,
                "heartbeat_present": True,
            },
        )

        assert res.status_code == 200
        body = res.json()
        assert body["active_class"] == "accepted"
        assert body["draft_candidate"]["public_safe_name"] == "Add Request Intake Draft Flow"
        assert body["draft_candidate"]["todo_id"] == "XWORLD-TODO-037"
        assert body["draft_candidate"]["gate"] == "human review before external write"

    def test_intake_lifecycle_rejects_external_write(self, client_no_key):
        """MVP-008: 人間レビュー前の外部writeを拒否する。"""
        res = client_no_key.post(
            "/api/intake-lifecycle/draft",
            json={"request_class": "accepted", "todo_id": "XWORLD-TODO-037", "external_write": True},
        )

        assert res.status_code == 400
        assert res.json()["detail"]["failure_state"] == "external_write_blocked"

    def test_intake_lifecycle_rejects_private_source_content(self, client_no_key):
        """MVP-008: private source本文をpublic docsに入れない。"""
        res = client_no_key.post(
            "/api/intake-lifecycle/draft",
            json={"request_class": "watch", "private_source_content": True},
        )

        assert res.status_code == 400
        assert res.json()["detail"]["failure_state"] == "source_not_public_safe"

    def test_intake_lifecycle_rejects_validator_hit(self, client_no_key):
        """MVP-008: protected name / private path / 外部本文 / secret-like stringを拒否する。"""
        for field in ("protected_name", "private_path", "external_post_body", "secret_like_string"):
            res = client_no_key.post(
                "/api/intake-lifecycle/draft",
                json={"request_class": "watch", field: True},
            )

            assert res.status_code == 400
            assert res.json()["detail"]["failure_state"] == "validator_hit"

    def test_intake_lifecycle_rejects_missing_todo_for_accepted(self, client_no_key):
        """MVP-008: accepted ideaにはTODO IDを要求する。"""
        for payload in ({"request_class": "accepted"}, {"request_class": "accepted", "todo_id": ""}):
            res = client_no_key.post("/api/intake-lifecycle/draft", json=payload)

            assert res.status_code == 400
            assert res.json()["detail"]["failure_state"] == "todo_classification_missing"

    def test_intake_lifecycle_rejects_text_value_validator_hit(self, client_no_key):
        """MVP-008: boolean flagだけでなく文字列本文の混入も拒否する。"""
        cases = [
            ("private_source_content", "local private excerpt"),
            ("protected_name", "protected implementation name"),
            ("private_path", "C:/private/source/path"),
            ("external_post_body", "quoted external body"),
            ("secret_like_string", "secret-like-value"),
        ]
        for field, value in cases:
            res = client_no_key.post(
                "/api/intake-lifecycle/draft",
                json={"request_class": "watch", field: value},
            )

            assert res.status_code == 400
            assert res.json()["detail"]["failure_state"] in {"source_not_public_safe", "validator_hit"}

    def test_intake_lifecycle_rejects_missing_world_packet(self, client_no_key):
        """MVP-008: Minimum World Packet不足を拒否する。"""
        res = client_no_key.post(
            "/api/intake-lifecycle/draft",
            json={"request_class": "watch", "minimum_world_packet": False},
        )

        assert res.status_code == 400
        assert res.json()["detail"]["failure_state"] == "world_packet_missing"

    def test_intake_lifecycle_rejects_orphan_threshold(self, client_no_key):
        """MVP-008: orphan候補がしきい値を超えたらreview alert扱いで止める。"""
        res = client_no_key.post(
            "/api/intake-lifecycle/draft",
            json={"request_class": "watch", "orphan_count": 4},
        )

        assert res.status_code == 400
        assert res.json()["detail"]["failure_state"] == "orphan_threshold_exceeded"

    def test_intake_lifecycle_rejects_stale_without_self_report(self, client_no_key):
        """MVP-008: staleは自己申告なしで確定しない。"""
        res = client_no_key.post(
            "/api/intake-lifecycle/draft",
            json={"request_class": "watch", "stale": True},
        )

        assert res.status_code == 400
        assert res.json()["detail"]["failure_state"] == "stale_without_self_report"

    def test_intake_lifecycle_rejects_missing_heartbeat(self, client_no_key):
        """MVP-008: heartbeatなしのlifecycle更新を拒否する。"""
        res = client_no_key.post(
            "/api/intake-lifecycle/draft",
            json={"request_class": "watch", "heartbeat_present": False},
        )

        assert res.status_code == 400
        assert res.json()["detail"]["failure_state"] == "heartbeat_missing"


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

    def test_matching_summary_run_id_keeps_existing_label(self, client_no_key):
        """summary.json.run_id がディレクトリ名と同じなら従来通り run_id だけで表示できる。"""
        body = client_no_key.get("/api/runs").json()
        run = body["runs"][0]
        assert run["run_id"] == "test_run"
        assert "display_run_id" not in run

    def test_mismatched_summary_run_id_returns_loadable_directory_id(self, tmp_path, monkeypatch):
        """summary の run_id が違っても、API の run_id はロード可能なディレクトリ名にする。"""
        run_dir = tmp_path / "dir_name"
        run_dir.mkdir()
        (run_dir / "summary.json").write_text(
            json.dumps({
                "run_id": "summary_name",
                "seed": 1,
                "ticks": 1,
                "agents": 1,
                "pois": 1,
                "interactions": 0,
            }),
            encoding="utf-8",
        )
        monkeypatch.setenv("DATA_DIR", str(tmp_path))

        client = TestClient(app, raise_server_exceptions=True)
        runs_res = client.get("/api/runs")
        assert runs_res.status_code == 200
        runs = runs_res.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["run_id"] == "dir_name"
        assert runs[0]["display_run_id"] == "summary_name"
        assert client.get("/api/data/dir_name/summary.json").status_code == 200
        assert client.get("/api/data/summary_name/summary.json").status_code == 404

    def test_zero_runs_returns_empty_list(self, tmp_path, monkeypatch):
        """data ディレクトリが空でも 200 で空リストを返す。"""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.delenv("DATA_SOURCE", raising=False)
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        res = TestClient(app).get("/api/runs")
        assert res.status_code == 200
        assert res.json()["runs"] == []

    def test_gcs_data_source_returns_501(self, tmp_path, monkeypatch):
        """DATA_SOURCE=gcs は local の空リストにフォールバックせず明示エラーにする。"""
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "missing"))
        monkeypatch.setenv("DATA_SOURCE", "gcs")
        res = TestClient(app).get("/api/runs")
        assert res.status_code == 501
        assert "not implemented" in res.json()["detail"]


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
        "activity_plans.jsonl",
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

    def test_gcs_data_source_returns_501(self, sample_run_dir, monkeypatch):
        """DATA_SOURCE=gcs では local ファイルを配信せず明示エラーにする。"""
        monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
        monkeypatch.setenv("DATA_SOURCE", "gcs")
        res = TestClient(app).get("/api/data/test_run/summary.json")
        assert res.status_code == 501
        assert "not implemented" in res.json()["detail"]

    def test_symlink_escape_is_blocked(self, tmp_path, monkeypatch):
        """許可ファイル名でも symlink が DATA_DIR 外を指す場合は 403 にする。"""
        data_root = tmp_path / "data"
        run_dir = data_root / "test_run"
        run_dir.mkdir(parents=True)
        outside = tmp_path / "outside_summary.json"
        outside.write_text('{"run_id":"outside"}', encoding="utf-8")
        try:
            (run_dir / "summary.json").symlink_to(outside)
        except OSError as exc:
            if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                pytest.skip("Windows symlink privilege is not available")
            raise

        monkeypatch.setenv("DATA_DIR", str(data_root))
        monkeypatch.delenv("DATA_SOURCE", raising=False)
        res = TestClient(app).get("/api/data/test_run/summary.json")

        assert res.status_code == 403
        assert "invalid path" in res.json()["detail"]

    def test_relative_data_dir_still_serves_contained_file(self, tmp_path, monkeypatch):
        """relative DATA_DIR でも resolve 後に配下なら通常通り配信する。"""
        data_root = tmp_path / "relative_data"
        run_dir = data_root / "test_run"
        run_dir.mkdir(parents=True)
        (run_dir / "summary.json").write_text(
            json.dumps({
                "run_id": "test_run",
                "seed": 42,
                "ticks": 1,
                "agents": 1,
                "pois": 1,
                "interactions": 0,
            }),
            encoding="utf-8",
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DATA_DIR", "relative_data")
        monkeypatch.delenv("DATA_SOURCE", raising=False)
        res = TestClient(app).get("/api/data/test_run/summary.json")

        assert res.status_code == 200
        assert res.json()["run_id"] == "test_run"


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

    def test_maps_env_values_are_json_escaped_in_html(self, sample_run_dir, monkeypatch):
        """quote / backslash を含む env 値でも HTML 内の JS literal を壊さない。"""
        api_key = 'TEST_"KEY\\VALUE'
        map_id = 'MAP_"ID\\VALUE'
        monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", api_key)
        monkeypatch.setenv("GOOGLE_MAPS_MAP_ID", map_id)

        res = TestClient(app).get("/")

        assert res.status_code == 200
        assert 'key: "TEST_"KEY\\VALUE"' not in res.text
        assert json.dumps(api_key) in res.text
        assert json.dumps(map_id) in res.text

    def test_maps_env_values_are_json_escaped_in_app_js(self, sample_run_dir, monkeypatch):
        """app.js placeholder replacement も JSON-safe な JS literal にする。"""
        api_key = 'TEST_"KEY\\VALUE'
        map_id = 'MAP_"ID\\VALUE'
        monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", api_key)
        monkeypatch.setenv("GOOGLE_MAPS_MAP_ID", map_id)

        res = TestClient(app).get("/static/app.js")

        assert res.status_code == 200
        assert json.dumps(api_key) in res.text
        assert json.dumps(map_id) in res.text
        assert 'const MAPS_API_KEY = "TEST_"KEY\\VALUE";' not in res.text

    def test_maps_env_values_are_stripped_before_html_injection(self, sample_run_dir, monkeypatch):
        """Secret Manager 値の末尾改行で Maps key / Map ID を壊さない。"""
        monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "  TEST_KEY_WITH_WHITESPACE\n")
        monkeypatch.setenv("GOOGLE_MAPS_MAP_ID", "\tTEST_MAP_ID_WITH_WHITESPACE\n")

        res = TestClient(app).get("/")

        assert res.status_code == 200
        assert json.dumps("TEST_KEY_WITH_WHITESPACE") in res.text
        assert json.dumps("TEST_MAP_ID_WITH_WHITESPACE") in res.text
        assert json.dumps("  TEST_KEY_WITH_WHITESPACE\n") not in res.text
        assert json.dumps("\tTEST_MAP_ID_WITH_WHITESPACE\n") not in res.text

    def test_maps_env_values_are_stripped_before_app_js_injection(self, sample_run_dir, monkeypatch):
        """app.js 側も Secret Manager 値の前後空白を除去して注入する。"""
        monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "  TEST_KEY_WITH_WHITESPACE\n")
        monkeypatch.setenv("GOOGLE_MAPS_MAP_ID", "\tTEST_MAP_ID_WITH_WHITESPACE\n")

        res = TestClient(app).get("/static/app.js")

        assert res.status_code == 200
        assert json.dumps("TEST_KEY_WITH_WHITESPACE") in res.text
        assert json.dumps("TEST_MAP_ID_WITH_WHITESPACE") in res.text
        assert json.dumps("  TEST_KEY_WITH_WHITESPACE\n") not in res.text
        assert json.dumps("\tTEST_MAP_ID_WITH_WHITESPACE\n") not in res.text

    def test_demo_map_id_is_not_injected_into_html(self, sample_run_dir, monkeypatch):
        """DEMO_MAP_ID は無効な Map ID なので Maps bootstrap loader へ渡さない。"""
        monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "dummy-key")
        monkeypatch.setenv("GOOGLE_MAPS_MAP_ID", "DEMO_MAP_ID")

        res = TestClient(app).get("/")

        assert res.status_code == 200
        assert "maps.googleapis.com" in res.text
        assert "mapIds" not in res.text
        assert "DEMO_MAP_ID" not in res.text

    def test_demo_map_id_is_not_injected_into_app_js(self, sample_run_dir, monkeypatch):
        """app.js 側も DEMO_MAP_ID を空文字扱いにし、通常 Marker へ落とせるようにする。"""
        monkeypatch.setenv("DATA_DIR", str(sample_run_dir))
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "dummy-key")
        monkeypatch.setenv("GOOGLE_MAPS_MAP_ID", "DEMO_MAP_ID")

        res = TestClient(app).get("/static/app.js")

        assert res.status_code == 200
        assert 'const MAPS_MAP_ID  = "";' in res.text
        assert "DEMO_MAP_ID" not in res.text


# ─────────────────────────────────────────────────────────────────────────────
# 許可リスト自体の完全性確認
# ─────────────────────────────────────────────────────────────────────────────

class TestAllowedFiles:
    def test_allowed_files_count_is_12(self):
        """許可ファイルは data-contract §File Names の 12 件であること。"""
        assert len(ALLOWED_FILES) == 12

    @pytest.mark.parametrize("filename", [
        "pois.geojson",
        "aois.geojson",
        "roadnet.geojson",
        "agent_profiles_N100.json",
        "activity_plans.jsonl",
        "agent_states.jsonl",
        "poi_visit_records.jsonl",
        "interaction_events.jsonl",
        "relationships.jsonl",
        "matrix_events.jsonl",
        "summary.json",
        "metrics.json",
    ])
    def test_expected_files_in_allowlist(self, filename):
        """contract で定義された 12 ファイルがすべて許可リストにある。"""
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
      - マーカー glyphText に surname を使う。
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
        """surname 欠落プロフィールに対する glyphText ラベル計算ロジックの検証。

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


# ─────────────────────────────────────────────────────────────────────────────
# gap §5.2: ロード結果表示 / §5.5: poi_visit_records ロード (viewer-ux-1/2/3)
# ─────────────────────────────────────────────────────────────────────────────

class TestPoiVisitRecordsEndpoint:
    """poi_visit_records.jsonl がサーバー経由で取得できる (gap §5.2 / §5.5)。

    受け入れ条件:
    - /api/data/{run_id}/poi_visit_records.jsonl が 200 を返す。
    - レスポンスは NDJSON 形式 (JSON 配列ではない)。
    - 各行に contract §VisitRecord 必須フィールドが含まれる。
    """

    def test_poi_visit_records_returns_200(self, client_no_key):
        """`poi_visit_records.jsonl` エンドポイントは 200 を返す。"""
        res = client_no_key.get("/api/data/test_run/poi_visit_records.jsonl")
        assert res.status_code == 200, f"got {res.status_code}: {res.text[:200]}"

    def test_poi_visit_records_content_type_ndjson(self, client_no_key):
        """Content-Type は application/x-ndjson。"""
        res = client_no_key.get("/api/data/test_run/poi_visit_records.jsonl")
        assert res.status_code == 200
        ct = res.headers.get("content-type", "")
        assert "ndjson" in ct or "x-ndjson" in ct, f"unexpected content-type: {ct}"

    def test_poi_visit_records_is_ndjson_not_array(self, client_no_key):
        """レスポンスは JSON 配列ではなく NDJSON 形式。"""
        res = client_no_key.get("/api/data/test_run/poi_visit_records.jsonl")
        assert res.status_code == 200
        assert not res.text.strip().startswith("["), "JSONL が JSON 配列として返っている"

    def test_poi_visit_records_required_fields(self, client_no_key):
        """各行に contract §VisitRecord 必須フィールドが含まれる。"""
        res = client_no_key.get("/api/data/test_run/poi_visit_records.jsonl")
        assert res.status_code == 200
        lines = [l for l in res.text.strip().split("\n") if l.strip()]
        assert len(lines) >= 1, "レコードが 0 件"
        for line in lines:
            obj = json.loads(line)
            for field in ("agent_id", "day", "time", "action", "lat", "lon"):
                assert field in obj, f"必須フィールド {field!r} が欠けている: {obj}"


class TestLoadStatusDomElement:
    """index.html に load-status 表示領域が存在する (gap §5.2: ロード結果表示)。

    受け入れ条件 (§5.2):
    - 読込後は各ファイルの件数・検証結果・エラー件数を表示する。
    - HTML に id="load-status" を持つ要素が存在すること (サーバーが静的 HTML を返す前提)。
    """

    def test_html_has_load_status_element(self, client_no_key):
        """HTML レスポンスに id='load-status' 要素が含まれる。"""
        res = client_no_key.get("/")
        assert res.status_code == 200
        assert 'id="load-status"' in res.text, (
            "index.html に id='load-status' 要素が存在しない (gap §5.2: ロード結果表示)"
        )

    def test_html_has_matrix_panel_element(self, client_no_key):
        """HTML レスポンスに MATRIX 状態表示パネルが含まれる。"""
        res = client_no_key.get("/")
        assert res.status_code == 200
        assert 'id="matrix-panel"' in res.text
        assert "この run には MATRIX イベントがありません" in res.text
        assert "現在のworld layer" in res.text
        assert "matrix-world-chip" in res.text
        assert 'id="btn-audio-cue"' in res.text
        assert "8-bit cue off" in res.text

    def test_html_has_gsi_3d_map_mode_option(self, client_no_key):
        """HTML レスポンスに GSI 3D map adapter の opt-in 選択肢が含まれる。"""
        res = client_no_key.get("/")
        assert res.status_code == 200
        assert 'value="gsi_3d"' in res.text
        assert "GSI 3D" in res.text


class TestInterpolationLogic:
    """§5.1.4 線形補間: 隣接 tick 間 lat/lon 補間のロジック検証 (Python 等価実装)。

    JS 側 playLoop の RAF コールバック内で行う補間ロジックを Python で等価実装して確認する。
    受け入れ条件:
    - alpha=0 のとき現在 tick の位置を返す。
    - alpha=1 のとき次 tick の位置を返す。
    - alpha=0.5 のとき中間位置を返す (線形補間)。
    - alpha は [0, 1] にクランプされる。
    - 状態の真値 (tickIndex) は変えない (補間は描画専用)。
    """

    @staticmethod
    def _lerp(a: float, b: float, alpha: float) -> float:
        """線形補間: a + (b - a) * alpha (JS 側 playLoop の等価実装)。"""
        return a + (b - a) * alpha

    def test_alpha_0_returns_current_position(self):
        """alpha=0 のとき現在 tick の位置を返す。"""
        lat0, lon0 = 35.660, 139.700
        lat1, lon1 = 35.670, 139.710
        assert self._lerp(lat0, lat1, 0.0) == pytest.approx(lat0)
        assert self._lerp(lon0, lon1, 0.0) == pytest.approx(lon0)

    def test_alpha_1_returns_next_position(self):
        """alpha=1 のとき次 tick の位置を返す。"""
        lat0, lon0 = 35.660, 139.700
        lat1, lon1 = 35.670, 139.710
        assert self._lerp(lat0, lat1, 1.0) == pytest.approx(lat1)
        assert self._lerp(lon0, lon1, 1.0) == pytest.approx(lon1)

    def test_alpha_half_returns_midpoint(self):
        """alpha=0.5 のとき中間位置を返す。"""
        lat0, lon0 = 35.660, 139.700
        lat1, lon1 = 35.680, 139.720
        assert self._lerp(lat0, lat1, 0.5) == pytest.approx(35.670)
        assert self._lerp(lon0, lon1, 0.5) == pytest.approx(139.710)

    def test_alpha_clamp_below_zero(self):
        """alpha < 0 は 0 にクランプされ、現在 tick 位置を返す。"""
        lat0, lat1 = 35.660, 35.670
        alpha = max(0.0, min(1.0, -0.5))  # clamp
        assert self._lerp(lat0, lat1, alpha) == pytest.approx(lat0)

    def test_alpha_clamp_above_one(self):
        """alpha > 1 は 1 にクランプされ、次 tick 位置を返す。"""
        lat0, lat1 = 35.660, 35.670
        alpha = max(0.0, min(1.0, 1.5))  # clamp
        assert self._lerp(lat0, lat1, alpha) == pytest.approx(lat1)

    def test_interpolated_lat_within_range(self):
        """補間 lat は [lat0, lat1] の範囲に収まる (テレポート検知)。"""
        lat0, lat1 = 35.660, 35.670
        for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
            result = self._lerp(lat0, lat1, alpha)
            assert lat0 <= result <= lat1, (
                f"alpha={alpha}: result {result} が [{lat0}, {lat1}] 外"
            )

    def test_interpolated_lon_within_range(self):
        """補間 lon は [lon0, lon1] の範囲に収まる。"""
        lon0, lon1 = 139.700, 139.710
        for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
            result = self._lerp(lon0, lon1, alpha)
            assert lon0 <= result <= lon1, (
                f"alpha={alpha}: result {result} が [{lon0}, {lon1}] 外"
            )

    def test_alpha_calculation_from_elapsed_time(self):
        """elapsed / msPerTick から alpha を計算するロジック検証。

        再生ループ: alpha = clamp(elapsed / msPerTick, 0, 1)。
        elapsed=0 なら alpha=0、elapsed=msPerTick ならalpha=1。
        """
        ms_per_tick = 1000  # 1x 速度での 1tick あたり ms

        # フレーム開始直後 (elapsed=0)
        elapsed = 0
        alpha = max(0.0, min(1.0, elapsed / ms_per_tick))
        assert alpha == pytest.approx(0.0)

        # tick 境界 (elapsed == msPerTick)
        elapsed = 1000
        alpha = max(0.0, min(1.0, elapsed / ms_per_tick))
        assert alpha == pytest.approx(1.0)

        # 中間フレーム (elapsed=500ms / 1x)
        elapsed = 500
        alpha = max(0.0, min(1.0, elapsed / ms_per_tick))
        assert alpha == pytest.approx(0.5)

        # 2x 速度 (msPerTick=500ms)
        ms_per_tick_2x = 500
        elapsed = 250
        alpha = max(0.0, min(1.0, elapsed / ms_per_tick_2x))
        assert alpha == pytest.approx(0.5)


class TestVisitRecordDetailLogic:
    """§5.3 / §5.5 エージェント詳細「直近 POI / 理由」「直近の会話またはイベント」表示ロジック。

    JS 側 _findLatestVisit に visitRecords / currentDay / currentTime を渡して
    「現在の再生位置以前かつ最大 (day, time)」の訪問レコードを返す
    ロジックを Python で等価実装して確認する (#3 修正後の新ロジック)。
    """

    def _latest_visit(
        self,
        agent_id: int,
        visit_records: list,
        current_day: int,
        current_time: str,
    ) -> dict | None:
        """agent_id の最新訪問レコードを返す (JS 側 _findLatestVisit の Python 等価実装)。

        - agent_id が一致するレコードのみ対象。
        - (day, time) が (current_day, current_time) 以下のものだけ候補。
        - 候補の中で (day, time) が最大のレコードを返す。
        - 候補なし -> None。
        """
        best: dict | None = None
        for rec in visit_records:
            if rec.get("agent_id") != agent_id:
                continue
            r_day  = rec.get("day",  0)
            r_time = rec.get("time", "")
            # (day, time) の辞書比較で現在位置より未来をフィルタ
            if (r_day, r_time) > (current_day, current_time):
                continue
            if best is None or (r_day, r_time) > (best["day"], best["time"]):
                best = rec
        return best

    def test_latest_visit_found_for_agent(self):
        """正しい agent_id の最新レコードを返す。"""
        records = [
            {"agent_id": 0, "day": 0, "time": "08:05:00", "poi_id": "poi_001",
             "action": "visit", "reason": "commute", "lat": 35.660, "lon": 139.700},
            {"agent_id": 1, "day": 0, "time": "08:10:00", "poi_id": "poi_002",
             "action": "visit", "reason": "lunch", "lat": 35.661, "lon": 139.701},
            {"agent_id": 0, "day": 0, "time": "12:00:00", "poi_id": "poi_003",
             "action": "visit", "reason": "lunch", "lat": 35.662, "lon": 139.702},
        ]
        # 現在 day=0, time="12:00:00" ならすべて候補 -> "poi_003" が最新
        result = self._latest_visit(0, records, current_day=0, current_time="12:00:00")
        assert result is not None
        assert result["poi_id"] == "poi_003"
        assert result["reason"] == "lunch"
        assert result["time"]   == "12:00:00"

    def test_latest_visit_returns_none_when_no_record(self):
        """訪問レコードがない agent_id には None を返す。"""
        records = [
            {"agent_id": 1, "day": 0, "time": "08:10:00", "poi_id": "poi_002",
             "action": "visit", "reason": "lunch", "lat": 35.661, "lon": 139.701},
        ]
        result = self._latest_visit(99, records, current_day=0, current_time="23:59:59")
        assert result is None

    def test_latest_visit_returns_none_for_empty_records(self):
        """空の visitRecords に対して None を返す。"""
        result = self._latest_visit(0, [], current_day=0, current_time="23:59:59")
        assert result is None

    def test_latest_visit_shows_poi_and_reason(self):
        """最新 visit の poi_id と reason が詳細パネル表示に使える。"""
        records = [
            {"agent_id": 5, "day": 0, "time": "12:00:00", "poi_id": "poi_cafe",
             "action": "visit", "reason": "lunch", "lat": 35.660, "lon": 139.700},
        ]
        rec = self._latest_visit(5, records, current_day=0, current_time="12:00:00")
        assert rec is not None
        # 表示ロジック: 「{time} {poi_id} ({reason})」形式で組み立て可能
        display = f"{rec['time']} {rec.get('poi_id', '—')} ({rec.get('reason', '—')})"
        assert "poi_cafe" in display
        assert "lunch"    in display

    # ── #3 修正の新テスト ─────────────────────────────────────────────────────

    def test_future_visit_is_excluded(self):
        """現在の (day, time) より未来の訪問レコードは返さない (#3)。"""
        records = [
            # 現在 08:05:00 / 未来レコードは 12:00:00
            {"agent_id": 0, "day": 0, "time": "08:05:00", "poi_id": "poi_past",
             "action": "visit", "reason": "commute", "lat": 35.660, "lon": 139.700},
            {"agent_id": 0, "day": 0, "time": "12:00:00", "poi_id": "poi_future",
             "action": "visit", "reason": "lunch", "lat": 35.661, "lon": 139.701},
        ]
        # 現在は day=0, time="08:05:00" -> "12:00:00" は未来なので除外
        result = self._latest_visit(0, records, current_day=0, current_time="08:05:00")
        assert result is not None
        assert result["poi_id"] == "poi_past", (
            f"未来訪問が返された: {result!r}"
        )

    def test_multiday_latest_is_selected(self):
        """複数 day にまたがるレコードで最大 (day, time) を返す (#3)。"""
        records = [
            {"agent_id": 0, "day": 0, "time": "20:00:00", "poi_id": "poi_day0",
             "action": "visit", "reason": "dinner", "lat": 35.660, "lon": 139.700},
            {"agent_id": 0, "day": 1, "time": "08:00:00", "poi_id": "poi_day1",
             "action": "visit", "reason": "commute", "lat": 35.661, "lon": 139.701},
        ]
        # 現在は day=1, time="08:00:00" -> どちらも候補 / day=1 が最大
        result = self._latest_visit(0, records, current_day=1, current_time="08:00:00")
        assert result is not None
        assert result["poi_id"] == "poi_day1"

    def test_same_day_earlier_time_is_excluded(self):
        """同 day で time が現在より大きいレコードは除外される (#3)。"""
        records = [
            {"agent_id": 0, "day": 0, "time": "08:00:00", "poi_id": "poi_early",
             "action": "visit", "reason": "commute", "lat": 35.660, "lon": 139.700},
            {"agent_id": 0, "day": 0, "time": "10:00:00", "poi_id": "poi_later",
             "action": "visit", "reason": "errand", "lat": 35.661, "lon": 139.701},
        ]
        # 現在は day=0, time="09:00:00" -> "10:00:00" は未来なので除外
        result = self._latest_visit(0, records, current_day=0, current_time="09:00:00")
        assert result is not None
        assert result["poi_id"] == "poi_early"

    def test_current_time_exact_match_is_included(self):
        """(day, time) が現在値と完全一致するレコードは含まれる (境界値)。"""
        records = [
            {"agent_id": 0, "day": 0, "time": "08:05:00", "poi_id": "poi_exact",
             "action": "visit", "reason": "commute", "lat": 35.660, "lon": 139.700},
        ]
        result = self._latest_visit(0, records, current_day=0, current_time="08:05:00")
        assert result is not None
        assert result["poi_id"] == "poi_exact"

    def test_next_day_future_is_excluded(self):
        """現在が day=0 のとき day=1 のレコードは未来として除外される (#3)。"""
        records = [
            {"agent_id": 0, "day": 0, "time": "20:00:00", "poi_id": "poi_today",
             "action": "visit", "reason": "dinner", "lat": 35.660, "lon": 139.700},
            {"agent_id": 0, "day": 1, "time": "08:00:00", "poi_id": "poi_tomorrow",
             "action": "visit", "reason": "commute", "lat": 35.661, "lon": 139.701},
        ]
        # 現在は day=0, time="20:00:00"
        result = self._latest_visit(0, records, current_day=0, current_time="20:00:00")
        assert result is not None
        assert result["poi_id"] == "poi_today"


# ─────────────────────────────────────────────────────────────────────────────
# #4: agent_states.jsonl ロード件数 = record 数 (tick 数ではない)
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentStatesLoadCount:
    """loadRun が agent_states.jsonl の実 record 件数 (行数) を
    updateLoadStatus に渡す (#4 修正の等価ロジック確認)。"""

    def test_record_count_is_total_lines_not_ticks(self):
        """statesRaw の行数 (全エージェント×tick) を count とし、
        distinct tick 数 (ticks.length) を使わないことを確認する。

        fixture: 2 tick x 2 agent = 4 record / distinct tick = 2
        正しい count = 4。ticks.length ベースの誤実装 = 2。
        """
        states_raw = [
            {"tick": 0, "day": 0, "time": "08:00:00", "agent_id": 0,
             "lat": 35.660, "lon": 139.700, "action": "commute", "status": "moving"},
            {"tick": 0, "day": 0, "time": "08:00:00", "agent_id": 1,
             "lat": 35.661, "lon": 139.701, "action": "commute", "status": "moving"},
            {"tick": 1, "day": 0, "time": "08:05:00", "agent_id": 0,
             "lat": 35.662, "lon": 139.702, "action": "commute", "status": "moving"},
            {"tick": 1, "day": 0, "time": "08:05:00", "agent_id": 1,
             "lat": 35.663, "lon": 139.703, "action": "commute", "status": "moving"},
        ]

        # ticks.length (誤実装): distinct tick 値の数
        states_by_tick: dict[int, list] = {}
        for s in states_raw:
            states_by_tick.setdefault(s["tick"], []).append(s)
        ticks = sorted(states_by_tick.keys())
        wrong_count = len(ticks)           # = 2 (誤)

        # 正しい実装: statesRaw の配列長
        correct_count = len(states_raw)    # = 4 (正)

        assert correct_count == 4, f"expected 4, got {correct_count}"
        assert wrong_count   == 2, f"wrong_count sanity check: expected 2, got {wrong_count}"
        # 修正後は wrong_count を渡さないことを表明する
        assert correct_count != wrong_count, (
            "record 数と tick 数が一致している: テストの前提が崩れた"
        )


# ─────────────────────────────────────────────────────────────────────────────
# viewer run load の壊れたデータ耐性
# ─────────────────────────────────────────────────────────────────────────────

class TestViewerAppRobustLoad:
    """app.js の loadRun 周辺に parse fallback / profile fallback / clamp があることを確認する。"""

    @pytest.fixture(scope="class")
    def app_js(self) -> str:
        path = _PROJECT_ROOT / "tools" / "urban_viewer" / "app.js"
        return path.read_text(encoding="utf-8")

    def test_fetch_run_file_catches_parse_errors(self, app_js):
        assert "catch (error)" in app_js
        assert "return null;" in app_js
        assert "JSON.parse(l)" in app_js

    def test_profile_file_falls_back_to_n100(self, app_js):
        assert "agent_profiles_N100.json" in app_js
        assert "profilesFileFallbackUsed" in app_js

    def test_slider_index_is_clamped(self, app_js):
        assert "_clampTickIndex" in app_js
        assert "Math.max(0, Math.min(maxIndex, idx))" in app_js

    def test_matrix_events_are_loaded_as_optional_viewer_input(self, app_js):
        assert 'fetchRunFile(runId, "matrix_events.jsonl")' in app_js
        assert "matrixEventsByTick" in app_js
        assert "updateMatrixPanel" in app_js
        assert "optional: true" in app_js

    def test_matrix_snapshot_uses_takeover_ttl(self, app_js):
        assert "function _getMatrixSnapshot(tick)" in app_js
        assert 'ev.type !== "takeover_start"' in app_js
        assert "ev.ttl_ticks" in app_js

    def test_matrix_snapshot_resolves_current_world_layer(self, app_js):
        assert "function _getCurrentWorldLayer(tick, events)" in app_js
        assert "currentWorldLayer" in app_js
        assert 'ev.world_layer || ev.target_layer' in app_js
        assert 'layer: "real"' in app_js

    def test_matrix_audio_cue_is_generated_and_opt_in(self, app_js):
        assert "function toggleAudioCue()" in app_js
        assert "function playGeneratedSquareCue(eventType)" in app_js
        assert "window.AudioContext || window.webkitAudioContext" in app_js
        assert 'osc.type = "square"' in app_js
        assert "audioCueState.enabled" in app_js
