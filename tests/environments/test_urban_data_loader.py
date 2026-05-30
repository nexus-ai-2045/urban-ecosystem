"""
test_urban_data_loader.py — §13.1 データ検証の機械化テスト。

正本:
  - docs/subagents/contracts/urban-ecosystem-data-contract.md v0.2.0
  - docs/ai-ecosystem-tool-spec.md §13.1

カバレッジ:
  - 構造検証: GeoJSON FeatureCollection / JSONL 1行1オブジェクト
  - ID 整合: 重複 ID / 命名規約 (poi_*/aoi_*/road_*/integer)
  - 値域/型: lat/lon 範囲 / time HH:MM:SS / tick 非負整数 / tick↔time 整合
  - enum 検証: action/status/type/visit.action (未知値は warning)
  - 参照整合: agent_id / poi_id / social_networks 自己参照・重複
  - 正常系: 全モデルの最小正常ケース
  - 異常系: 不正 geometry / 重複 id / 範囲外 lat/lon / 未知 enum / 壊れた JSONL
"""

import io
import json
import re
import tempfile
import warnings
from pathlib import Path
from typing import Any

import pytest

from environments.urban_2d.data_loader import (
    ValidationError,
    ValidationWarning,
    load_agent_profiles,
    load_agent_states,
    load_aois,
    load_interaction_events,
    load_pois,
    load_roads,
    load_visit_records,
)
from environments.urban_2d.models import (
    ACTION_VALUES,
    AGENT_STATUS_VALUES,
    INTERACTION_TYPE_VALUES,
)


# ─────────────────────────────────────────────────────────────────────────────
# テスト用データ生成ヘルパー
# ─────────────────────────────────────────────────────────────────────────────

def _write_json(tmp: Path, name: str, obj: Any) -> Path:
    """JSON ファイルを一時ディレクトリに書き出す。"""
    p = tmp / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


def _write_jsonl(tmp: Path, name: str, rows: list[dict]) -> Path:
    """JSONL ファイルを一時ディレクトリに書き出す。"""
    p = tmp / name
    lines = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    p.write_text(lines, encoding="utf-8")
    return p


def _write_raw(tmp: Path, name: str, text: str) -> Path:
    """生テキストをファイルに書き出す。"""
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    return p


def _make_poi_fc(features: list[dict]) -> dict:
    """POI FeatureCollection を生成する。"""
    return {"type": "FeatureCollection", "features": features}


def _poi_feature(
    poi_id: str = "poi_001",
    category: str = "amenity-cafe",
    lon: float = 139.0,
    lat: float = 35.0,
    **extra_props,
) -> dict:
    """最小有効 POI Feature を生成する。"""
    props = {"id": poi_id, "category": category, **extra_props}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def _agent_profile(
    agent_id: int = 0,
    name: str = "Test Agent",
    lat: float = 35.0,
    lon: float = 139.0,
    **kwargs,
) -> dict:
    """最小有効 AgentProfile を生成する。"""
    obj = {
        "id": agent_id,
        "name": name,
        "initial_position": {"lat": lat, "lon": lon},
    }
    obj.update(kwargs)
    return obj


def _agent_state(
    tick: int = 0,
    day: int = 0,
    time: str = "08:00:00",
    agent_id: int = 0,
    lat: float = 35.0,
    lon: float = 139.0,
    action: str = "commute",
    status: str = "moving",
    **kwargs,
) -> dict:
    """最小有効 AgentState を生成する。"""
    obj = {
        "tick": tick,
        "day": day,
        "time": time,
        "agent_id": agent_id,
        "lat": lat,
        "lon": lon,
        "action": action,
        "status": status,
    }
    obj.update(kwargs)
    return obj


def _visit_record(
    agent_id: int = 0,
    day: int = 0,
    time: str = "08:05:00",
    action: str = "visit",
    lat: float = 35.0,
    lon: float = 139.0,
    **kwargs,
) -> dict:
    """最小有効 VisitRecord を生成する。"""
    obj = {
        "agent_id": agent_id,
        "day": day,
        "time": time,
        "action": action,
        "lat": lat,
        "lon": lon,
    }
    obj.update(kwargs)
    return obj


def _interaction_event(
    tick: int = 1,
    day: int = 0,
    time: str = "08:05:00",
    ev_type: str = "conversation",
    agent_ids: list = None,
    summary: str = "Two agents talked.",
    **kwargs,
) -> dict:
    """最小有効 InteractionEvent を生成する。"""
    if agent_ids is None:
        agent_ids = [0, 1]
    obj = {
        "tick": tick,
        "day": day,
        "time": time,
        "type": ev_type,
        "agent_ids": agent_ids,
        "summary": summary,
    }
    obj.update(kwargs)
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# §13.1 構造検証
# ─────────────────────────────────────────────────────────────────────────────

class TestStructure:
    """GeoJSON FeatureCollection 構造 / JSONL 構造の検証。"""

    def test_poi_valid_minimal(self, tmp_path):
        """正常系: 最小有効 POI。"""
        p = _write_json(tmp_path, "pois.geojson", _make_poi_fc([_poi_feature()]))
        pois = load_pois(p)
        assert len(pois) == 1
        assert pois[0].id == "poi_001"
        assert pois[0].category == "amenity-cafe"
        assert pois[0].lat == 35.0
        assert pois[0].lon == 139.0

    def test_poi_not_feature_collection(self, tmp_path):
        """異常系: type が FeatureCollection でない。"""
        bad = {"type": "Feature", "geometry": None, "properties": {}}
        p = _write_json(tmp_path, "pois.geojson", bad)
        with pytest.raises(ValidationError, match="FeatureCollection"):
            load_pois(p)

    def test_poi_not_json(self, tmp_path):
        """異常系: 壊れた JSON。"""
        p = _write_raw(tmp_path, "pois.geojson", "{ broken json }")
        with pytest.raises(ValidationError, match="JSON パースエラー"):
            load_pois(p)

    def test_jsonl_broken_line(self, tmp_path):
        """異常系: JSONL の途中に壊れた行がある。"""
        text = (
            '{"tick":0,"day":0,"time":"08:00:00","agent_id":0,"lat":35.0,'
            '"lon":139.0,"action":"commute","status":"moving"}\n'
            '{ bad line\n'
        )
        p = _write_raw(tmp_path, "agent_states.jsonl", text)
        with pytest.raises(ValidationError, match="JSONL パースエラー"):
            load_agent_states(p)

    def test_aoi_valid_polygon(self, tmp_path):
        """正常系: AOI Polygon。"""
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[139.0, 35.0], [139.1, 35.0], [139.0, 35.0]]],
                },
                "properties": {"id": "aoi_001", "name": "Test Area"},
            }],
        }
        p = _write_json(tmp_path, "aois.geojson", fc)
        aois = load_aois(p)
        assert aois[0].id == "aoi_001"
        assert aois[0].geometry_type == "Polygon"

    def test_aoi_invalid_geometry_type(self, tmp_path):
        """異常系: AOI が Point geometry (Polygon/MultiPolygon でない)。"""
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [139.0, 35.0]},
                "properties": {"id": "aoi_001"},
            }],
        }
        p = _write_json(tmp_path, "aois.geojson", fc)
        with pytest.raises(ValidationError, match="Polygon|MultiPolygon"):
            load_aois(p)

    def test_road_valid_linestring(self, tmp_path):
        """正常系: Road LineString。"""
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[139.0, 35.0], [139.001, 35.001]],
                },
                "properties": {"id": "road_001", "length_m": 128.4, "walkable": True},
            }],
        }
        p = _write_json(tmp_path, "roadnet.geojson", fc)
        roads = load_roads(p)
        assert roads[0].id == "road_001"
        assert roads[0].length_m == 128.4
        assert roads[0].walkable is True

    def test_road_invalid_geometry(self, tmp_path):
        """異常系: Road が Polygon geometry。"""
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[139.0, 35.0], [139.1, 35.0], [139.0, 35.0]]],
                },
                "properties": {"id": "road_001"},
            }],
        }
        p = _write_json(tmp_path, "roadnet.geojson", fc)
        with pytest.raises(ValidationError, match="LineString|MultiLineString"):
            load_roads(p)


# ─────────────────────────────────────────────────────────────────────────────
# §13.1 ID 整合
# ─────────────────────────────────────────────────────────────────────────────

class TestIDIntegrity:
    """ID 一意性 / 命名規約 / 参照整合の検証。"""

    def test_poi_duplicate_id(self, tmp_path):
        """異常系: 重複 POI ID。"""
        fc = _make_poi_fc([_poi_feature("poi_001"), _poi_feature("poi_001")])
        p = _write_json(tmp_path, "pois.geojson", fc)
        with pytest.raises(ValidationError, match="重複 ID"):
            load_pois(p)

    def test_poi_invalid_id_prefix(self, tmp_path):
        """異常系: POI ID が poi_ で始まらない。"""
        fc = _make_poi_fc([_poi_feature("cafe_001")])
        p = _write_json(tmp_path, "pois.geojson", fc)
        with pytest.raises(ValidationError, match="poi_"):
            load_pois(p)

    def test_aoi_invalid_id_prefix(self, tmp_path):
        """異常系: AOI ID が aoi_ で始まらない。"""
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[139.0, 35.0], [139.1, 35.0], [139.0, 35.0]]],
                },
                "properties": {"id": "district_001"},
            }],
        }
        p = _write_json(tmp_path, "aois.geojson", fc)
        with pytest.raises(ValidationError, match="aoi_"):
            load_aois(p)

    def test_road_invalid_id_prefix(self, tmp_path):
        """異常系: Road ID が road_ で始まらない。"""
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[139.0, 35.0], [139.001, 35.001]],
                },
                "properties": {"id": "street_001"},
            }],
        }
        p = _write_json(tmp_path, "roadnet.geojson", fc)
        with pytest.raises(ValidationError, match="road_"):
            load_roads(p)

    def test_agent_id_must_be_integer(self, tmp_path):
        """異常系: Agent ID が文字列。"""
        profiles = [{"id": "agent_0", "name": "Test", "initial_position": {"lat": 35.0, "lon": 139.0}}]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="integer"):
            load_agent_profiles(p)

    def test_agent_duplicate_id(self, tmp_path):
        """異常系: 重複 agent ID。"""
        profiles = [
            _agent_profile(0),
            _agent_profile(0),
        ]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="重複 ID"):
            load_agent_profiles(p)

    def test_social_networks_self_reference(self, tmp_path):
        """異常系: social_networks に自己 ID を含む。"""
        profiles = [_agent_profile(0, social_networks=[0])]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="自己 id"):
            load_agent_profiles(p)

    def test_social_networks_duplicate(self, tmp_path):
        """異常系: social_networks に重複がある。"""
        profiles = [_agent_profile(0, social_networks=[1, 1])]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="重複"):
            load_agent_profiles(p)

    def test_home_poi_id_referential_integrity(self, tmp_path):
        """異常系: home_poi_id が POI 集合に存在しない。"""
        profiles = [_agent_profile(0, home_poi_id="poi_nonexistent")]
        p = _write_json(tmp_path, "profiles.json", profiles)
        poi_ids = frozenset({"poi_001"})
        with pytest.raises(ValidationError, match="home_poi_id"):
            load_agent_profiles(p, poi_ids=poi_ids)

    def test_agent_state_agent_id_reference(self, tmp_path):
        """異常系: AgentState の agent_id が profiles に存在しない。"""
        rows = [_agent_state(agent_id=99)]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.raises(ValidationError, match="agent_id"):
            load_agent_states(p, agent_ids=frozenset({0}))

    def test_interaction_event_duplicate_tick_pair(self, tmp_path):
        """異常系: 同一 tick・同一正規化ペアが重複。"""
        rows = [
            _interaction_event(tick=1, time="08:05:00", agent_ids=[0, 1]),
            _interaction_event(tick=1, time="08:05:00", agent_ids=[0, 1]),
        ]
        p = _write_jsonl(tmp_path, "interactions.jsonl", rows)
        with pytest.raises(ValidationError, match="duplicate"):
            load_interaction_events(p)

    def test_interaction_event_agent_ids_normalized(self, tmp_path):
        """正常系: agent_ids は昇順正規化される。"""
        rows = [_interaction_event(tick=1, time="08:05:00", agent_ids=[5, 2])]
        p = _write_jsonl(tmp_path, "interactions.jsonl", rows)
        events = load_interaction_events(p)
        assert events[0].agent_ids == (2, 5)


# ─────────────────────────────────────────────────────────────────────────────
# §13.1 値域/型 検証
# ─────────────────────────────────────────────────────────────────────────────

class TestValueRange:
    """lat/lon 範囲 / time フォーマット / tick・day 非負整数 / tick↔time 整合。"""

    def test_poi_lat_out_of_range(self, tmp_path):
        """異常系: POI lat > 90。"""
        fc = _make_poi_fc([_poi_feature(lat=91.0)])
        p = _write_json(tmp_path, "pois.geojson", fc)
        with pytest.raises(ValidationError, match="lat"):
            load_pois(p)

    def test_poi_lon_out_of_range(self, tmp_path):
        """異常系: POI lon < -180。"""
        fc = _make_poi_fc([_poi_feature(lon=-181.0)])
        p = _write_json(tmp_path, "pois.geojson", fc)
        with pytest.raises(ValidationError, match="lon"):
            load_pois(p)

    def test_agent_state_lat_out_of_range(self, tmp_path):
        """異常系: AgentState lat < -90。"""
        rows = [_agent_state(lat=-91.0)]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.raises(ValidationError, match="lat"):
            load_agent_states(p)

    def test_agent_state_lon_out_of_range(self, tmp_path):
        """異常系: AgentState lon > 180。"""
        rows = [_agent_state(lon=181.0)]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.raises(ValidationError, match="lon"):
            load_agent_states(p)

    def test_time_invalid_format(self, tmp_path):
        """異常系: time が HH:MM:SS 形式でない。"""
        rows = [_agent_state(time="8:00")]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.raises(ValidationError, match="HH:MM:SS"):
            load_agent_states(p)

    def test_tick_must_be_nonnegative(self, tmp_path):
        """異常系: tick が負数。"""
        rows = [_agent_state(tick=-1, time="07:55:00")]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.raises(ValidationError, match="tick"):
            load_agent_states(p)

    def test_tick_time_inconsistency(self, tmp_path):
        """異常系: tick=1 なのに time="08:00:00" (08:05:00 が正しい)。"""
        rows = [_agent_state(tick=1, time="08:00:00")]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.raises(ValidationError, match="time"):
            load_agent_states(p)

    def test_tick0_time_correct(self, tmp_path):
        """正常系: tick=0, time="08:00:00" は整合している。"""
        rows = [_agent_state(tick=0, time="08:00:00")]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        states = load_agent_states(p)
        assert states[0].tick == 0
        assert states[0].time == "08:00:00"

    def test_tick12_time_correct(self, tmp_path):
        """正常系: tick=12 -> time="09:00:00"。"""
        rows = [_agent_state(tick=12, time="09:00:00")]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        states = load_agent_states(p)
        assert states[0].time == "09:00:00"

    def test_agent_age_negative(self, tmp_path):
        """異常系: age が負数。"""
        profiles = [_agent_profile(0, age=-1)]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="age"):
            load_agent_profiles(p)

    def test_road_length_m_negative(self, tmp_path):
        """異常系: Road length_m が負数。"""
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[139.0, 35.0], [139.001, 35.001]],
                },
                "properties": {"id": "road_001", "length_m": -10.0, "walkable": True},
            }],
        }
        p = _write_json(tmp_path, "roadnet.geojson", fc)
        with pytest.raises(ValidationError, match="length_m"):
            load_roads(p)

    def test_interaction_agent_ids_too_few(self, tmp_path):
        """異常系: agent_ids の要素数が 1 (< 2)。"""
        rows = [_interaction_event(agent_ids=[0])]
        p = _write_jsonl(tmp_path, "interactions.jsonl", rows)
        with pytest.raises(ValidationError, match="len >= 2"):
            load_interaction_events(p)

    def test_interaction_agent_ids_duplicate(self, tmp_path):
        """異常系: agent_ids に重複がある。"""
        rows = [_interaction_event(agent_ids=[0, 0])]
        p = _write_jsonl(tmp_path, "interactions.jsonl", rows)
        with pytest.raises(ValidationError, match="重複なし"):
            load_interaction_events(p)


# ─────────────────────────────────────────────────────────────────────────────
# §13.1 enum 検証 (未知値は warning)
# ─────────────────────────────────────────────────────────────────────────────

class TestEnumValidation:
    """未知 enum 値は ValidationWarning として収集されること。"""

    def test_unknown_action_emits_warning(self, tmp_path):
        """異常系: 未知 action 値は ValidationWarning。"""
        rows = [_agent_state(action="teleport")]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.warns(ValidationWarning, match="teleport"):
            load_agent_states(p)

    def test_unknown_status_emits_warning(self, tmp_path):
        """異常系: 未知 status 値は ValidationWarning。"""
        rows = [_agent_state(status="flying")]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.warns(ValidationWarning, match="flying"):
            load_agent_states(p)

    def test_unknown_interaction_type_emits_warning(self, tmp_path):
        """異常系: 未知 interaction type は ValidationWarning。"""
        rows = [_interaction_event(ev_type="dance")]
        p = _write_jsonl(tmp_path, "interactions.jsonl", rows)
        with pytest.warns(ValidationWarning, match="dance"):
            load_interaction_events(p)

    def test_unknown_visit_action_emits_warning(self, tmp_path):
        """異常系: 未知 visit action は ValidationWarning。"""
        rows = [_visit_record(action="leave")]
        p = _write_jsonl(tmp_path, "visits.jsonl", rows)
        with pytest.warns(ValidationWarning, match="leave"):
            load_visit_records(p)

    def test_unknown_role_emits_warning(self, tmp_path):
        """異常系: 未知 role は ValidationWarning (reader は保持)。"""
        profiles = [_agent_profile(0, role="alien")]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.warns(ValidationWarning, match="alien"):
            results = load_agent_profiles(p)
        assert results[0].role == "alien"  # reader は保持する

    def test_all_known_actions_accepted(self, tmp_path):
        """正常系: 全ての既知 action 値で warning が出ない。"""
        for action in ACTION_VALUES:
            # tick=0 -> time="08:00:00" で整合
            rows = [_agent_state(action=action, tick=0, time="08:00:00")]
            p = _write_jsonl(tmp_path, "states.jsonl", rows)
            with warnings.catch_warnings():
                warnings.simplefilter("error", ValidationWarning)
                load_agent_states(p)  # warning が出たら pytest.warns が例外を raise

    def test_all_known_statuses_accepted(self, tmp_path):
        """正常系: 全ての既知 status 値で warning が出ない。"""
        for status in AGENT_STATUS_VALUES:
            rows = [_agent_state(status=status, tick=0, time="08:00:00")]
            p = _write_jsonl(tmp_path, "states.jsonl", rows)
            with warnings.catch_warnings():
                warnings.simplefilter("error", ValidationWarning)
                load_agent_states(p)


# ─────────────────────────────────────────────────────────────────────────────
# 正常系: 全モデルの完全なケース
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalCases:
    """全モデルの正常系 (必須 + 任意フィールド)。"""

    def test_poi_with_optional_fields(self, tmp_path):
        """正常系: POI に name / source / extra フィールドを含む。"""
        fc = _make_poi_fc([_poi_feature(name="Cafe Example", source="synthetic", custom="extra")])
        p = _write_json(tmp_path, "pois.geojson", fc)
        pois = load_pois(p)
        assert pois[0].name == "Cafe Example"
        assert pois[0].source == "synthetic"
        assert pois[0].extra.get("custom") == "extra"

    def test_agent_profile_full(self, tmp_path):
        """正常系: AgentProfile に全任意フィールドを含む。
        social_networks は同一ファイル内に存在する agent_id を参照する必要があるため、
        agent_id=1, 2 も同時に定義する (O1 dangling reference チェック対応)。
        """
        profiles = [
            _agent_profile(
                26,
                name="Mori Akira",
                age=30,
                gender="male",
                description="A test agent",
                home_poi_id="poi_home_001",
                work_or_school_poi_id="poi_work_001",
                role="office_worker",
                social_networks=[1, 2],
            ),
            _agent_profile(1, name="Agent One"),
            _agent_profile(2, name="Agent Two"),
        ]
        p = _write_json(tmp_path, "profiles.json", profiles)
        poi_ids = frozenset({"poi_home_001", "poi_work_001"})
        result = load_agent_profiles(p, poi_ids=poi_ids)
        # id=26 が先頭であることを確認
        profile_26 = next(r for r in result if r.id == 26)
        assert profile_26.id == 26
        assert profile_26.role == "office_worker"
        assert profile_26.social_networks == (1, 2)

    def test_agent_state_with_optional_poi_ids(self, tmp_path):
        """正常系: AgentState に current_poi_id / target_poi_id を含む。"""
        rows = [_agent_state(
            current_poi_id="poi_001",
            target_poi_id="poi_work_001",
        )]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        poi_ids = frozenset({"poi_001", "poi_work_001"})
        states = load_agent_states(p, poi_ids=poi_ids)
        assert states[0].current_poi_id == "poi_001"
        assert states[0].target_poi_id == "poi_work_001"

    def test_visit_record_with_initial_position(self, tmp_path):
        """正常系: VisitRecord.poi_id = 予約値 "initial_position"。"""
        rows = [_visit_record(poi_id="initial_position", reason="commute")]
        p = _write_jsonl(tmp_path, "visits.jsonl", rows)
        poi_ids = frozenset({"poi_001"})  # initial_position は poi_ids に含まれなくてよい
        records = load_visit_records(p, poi_ids=poi_ids)
        assert records[0].poi_id == "initial_position"

    def test_interaction_event_with_relationship_delta(self, tmp_path):
        """正常系: InteractionEvent に relationship_delta を含む。"""
        rows = [_interaction_event(
            relationship_delta={"from": "stranger", "to": "acquaintance"},
            location_poi_id="poi_001",
        )]
        p = _write_jsonl(tmp_path, "interactions.jsonl", rows)
        poi_ids = frozenset({"poi_001"})
        events = load_interaction_events(p, poi_ids=poi_ids)
        assert events[0].relationship_delta == {"from": "stranger", "to": "acquaintance"}

    def test_extra_fields_preserved(self, tmp_path):
        """正常系: reader は未知フィールドを保持する (contract §Common Rules)。"""
        rows = [_agent_state(**{"future_field": "xyz"})]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        states = load_agent_states(p)
        assert states[0].extra.get("future_field") == "xyz"

    def test_aoi_multipolygon(self, tmp_path):
        """正常系: AOI MultiPolygon。"""
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[139.0, 35.0], [139.1, 35.0], [139.0, 35.0]]]],
                },
                "properties": {"id": "aoi_001"},
            }],
        }
        p = _write_json(tmp_path, "aois.geojson", fc)
        aois = load_aois(p)
        assert aois[0].geometry_type == "MultiPolygon"

    def test_road_multilinestring(self, tmp_path):
        """正常系: Road MultiLineString。"""
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": [[[139.0, 35.0], [139.001, 35.001]]],
                },
                "properties": {"id": "road_001"},
            }],
        }
        p = _write_json(tmp_path, "roadnet.geojson", fc)
        roads = load_roads(p)
        assert roads[0].geometry_type == "MultiLineString"

    def test_multiple_pois(self, tmp_path):
        """正常系: 複数 POI (ID 重複なし)。"""
        features = [_poi_feature(f"poi_{i:03d}", "amenity-cafe") for i in range(1, 6)]
        fc = _make_poi_fc(features)
        p = _write_json(tmp_path, "pois.geojson", fc)
        pois = load_pois(p)
        assert len(pois) == 5

    def test_empty_featurecollection(self, tmp_path):
        """正常系: 空の FeatureCollection はエラーなし。"""
        fc = {"type": "FeatureCollection", "features": []}
        p = _write_json(tmp_path, "pois.geojson", fc)
        pois = load_pois(p)
        assert pois == []


# ─────────────────────────────────────────────────────────────────────────────
# 必須フィールド欠損テスト
# ─────────────────────────────────────────────────────────────────────────────

class TestMissingRequiredFields:
    """必須フィールドが欠けている場合の ValidationError。"""

    def test_poi_missing_id(self, tmp_path):
        """異常系: POI properties.id が欠落。"""
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [139.0, 35.0]},
            "properties": {"category": "amenity-cafe"},
        }
        p = _write_json(tmp_path, "pois.geojson", _make_poi_fc([feature]))
        with pytest.raises(ValidationError, match="id"):
            load_pois(p)

    def test_poi_missing_category(self, tmp_path):
        """異常系: POI properties.category が欠落。"""
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [139.0, 35.0]},
            "properties": {"id": "poi_001"},
        }
        p = _write_json(tmp_path, "pois.geojson", _make_poi_fc([feature]))
        with pytest.raises(ValidationError, match="category"):
            load_pois(p)

    def test_agent_state_missing_tick(self, tmp_path):
        """異常系: AgentState.tick が欠落。"""
        row = {
            "day": 0, "time": "08:00:00", "agent_id": 0,
            "lat": 35.0, "lon": 139.0, "action": "commute", "status": "moving",
        }
        p = _write_jsonl(tmp_path, "states.jsonl", [row])
        with pytest.raises(ValidationError, match="tick"):
            load_agent_states(p)

    def test_agent_profile_missing_name(self, tmp_path):
        """異常系: AgentProfile.name が欠落。"""
        profiles = [{"id": 0, "initial_position": {"lat": 35.0, "lon": 139.0}}]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="name"):
            load_agent_profiles(p)

    def test_interaction_event_missing_summary(self, tmp_path):
        """異常系: InteractionEvent.summary が欠落。"""
        row = {
            "tick": 1, "day": 0, "time": "08:05:00",
            "type": "conversation", "agent_ids": [0, 1],
        }
        p = _write_jsonl(tmp_path, "interactions.jsonl", [row])
        with pytest.raises(ValidationError, match="summary"):
            load_interaction_events(p)


# ─────────────────────────────────────────────────────────────────────────────
# エラーメッセージ可読性テスト
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorMessageReadability:
    """エラーメッセージが「ファイル名・行番号・違反フィールド・期待値」を含むこと。"""

    def test_error_contains_filename(self, tmp_path):
        """エラーメッセージにファイル名が含まれる。"""
        filename = "agent_states_test.jsonl"
        rows = [_agent_state(lat=999.0)]
        p = _write_jsonl(tmp_path, filename, rows)
        with pytest.raises(ValidationError) as exc_info:
            load_agent_states(p)
        assert filename in str(exc_info.value)

    def test_error_contains_lineno(self, tmp_path):
        """JSONL エラーメッセージに行番号が含まれる。"""
        rows = [_agent_state(), _agent_state(lat=999.0)]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.raises(ValidationError) as exc_info:
            load_agent_states(p)
        # 2 行目にエラーがあるので "2" が含まれる
        assert ":2" in str(exc_info.value)

    def test_error_contains_field_and_expected(self, tmp_path):
        """エラーメッセージに違反フィールド名と期待値が含まれる。"""
        rows = [_agent_state(lon=999.0)]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.raises(ValidationError) as exc_info:
            load_agent_states(p)
        msg = str(exc_info.value)
        assert "lon" in msg
        assert "180" in msg  # 期待値 [-180, 180]


# ─────────────────────────────────────────────────────────────────────────────
# 座標系検証 (contract §Coordinate Systems)
# ─────────────────────────────────────────────────────────────────────────────

class TestCoordinateSystems:
    """2 座標系が混在しないことを確認する。"""

    def test_poi_uses_geojson_coordinates(self, tmp_path):
        """正常系: POI は geometry.coordinates = [lon, lat] を使う。"""
        fc = _make_poi_fc([_poi_feature(lon=139.5, lat=35.5)])
        p = _write_json(tmp_path, "pois.geojson", fc)
        pois = load_pois(p)
        # GeoJSON [lon, lat] 順で格納されていること
        assert pois[0].lon == 139.5
        assert pois[0].lat == 35.5

    def test_agent_profile_uses_flat_lat_lon(self, tmp_path):
        """正常系: AgentProfile は initial_position.lat/lon を使う。"""
        profiles = [_agent_profile(lat=35.5, lon=139.5)]
        p = _write_json(tmp_path, "profiles.json", profiles)
        result = load_agent_profiles(p)
        assert result[0].initial_lat == 35.5
        assert result[0].initial_lon == 139.5

    def test_agent_state_uses_flat_lat_lon(self, tmp_path):
        """正常系: AgentState は lat/lon 個別キーを使う。"""
        rows = [_agent_state(lat=35.5, lon=139.5)]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        states = load_agent_states(p)
        assert states[0].lat == 35.5
        assert states[0].lon == 139.5

    def test_poi_category_format(self, tmp_path):
        """正常系: category が <group>-<sub> 形式。"""
        fc = _make_poi_fc([_poi_feature(category="shop-convenience")])
        p = _write_json(tmp_path, "pois.geojson", fc)
        pois = load_pois(p)
        assert pois[0].category == "shop-convenience"

    def test_poi_category_invalid_format(self, tmp_path):
        """異常系: category にスペースが含まれる (contract: ハイフン区切りのみ)。"""
        fc = _make_poi_fc([_poi_feature(category="amenity cafe")])
        p = _write_json(tmp_path, "pois.geojson", fc)
        with pytest.raises(ValidationError, match="category"):
            load_pois(p)


# ─────────────────────────────────────────────────────────────────────────────
# コードレビュー指摘対応テスト (WO-001 / R1 / R2 / R3 / O1 / O2)
# ─────────────────────────────────────────────────────────────────────────────

class TestReviewFixes:
    """レビュー指摘修正項目の異常系テスト。"""

    # ── R1: POI Feature id = "initial_position" は不正 ──────────────────────

    def test_poi_id_initial_position_is_invalid(self, tmp_path):
        """異常系[R1]: pois.geojson の Feature id = "initial_position" は ValidationError。
        "initial_position" は VisitRecord.poi_id 専用の予約値であり POI Feature id として不正。
        """
        fc = _make_poi_fc([_poi_feature(poi_id="initial_position")])
        p = _write_json(tmp_path, "pois.geojson", fc)
        with pytest.raises(ValidationError, match="poi_"):
            load_pois(p)

    def test_visit_record_poi_id_initial_position_is_valid(self, tmp_path):
        """正常系[R1]: VisitRecord.poi_id = "initial_position" は引き続き許容される。"""
        rows = [_visit_record(poi_id="initial_position")]
        p = _write_jsonl(tmp_path, "visits.jsonl", rows)
        # poi_ids に "initial_position" が含まれなくてもエラーにならない
        records = load_visit_records(p, poi_ids=frozenset({"poi_001"}))
        assert records[0].poi_id == "initial_position"

    # ── R2: social_networks 要素が非整数 → ValidationError ──────────────────

    def test_social_networks_string_element_raises(self, tmp_path):
        """異常系[R2]: social_networks の要素が文字列 → ValidationError (生 ValueError 不可)。"""
        profiles = [_agent_profile(0, social_networks=["abc"])]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="social_networks"):
            load_agent_profiles(p)

    def test_social_networks_float_element_raises(self, tmp_path):
        """異常系[R2]: social_networks の要素が float → ValidationError。"""
        profiles = [_agent_profile(0, social_networks=[1.5])]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="social_networks"):
            load_agent_profiles(p)

    def test_social_networks_bool_element_raises(self, tmp_path):
        """異常系[R2]: social_networks の要素が bool (int サブクラス) → ValidationError。
        bool は int のサブクラスだが contract §Agent Profile は「整数」を意図しているため除外。
        """
        profiles = [_agent_profile(0, social_networks=[True])]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="social_networks"):
            load_agent_profiles(p)

    def test_social_networks_mixed_raises(self, tmp_path):
        """異常系[R2]: social_networks に整数と文字列が混在 → ValidationError。"""
        profiles = [_agent_profile(0, social_networks=[1, "two"])]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="social_networks"):
            load_agent_profiles(p)

    def test_social_networks_valid_integers(self, tmp_path):
        """正常系[R2]: social_networks が全て整数 → 正常ロード。"""
        profiles = [_agent_profile(0), _agent_profile(1, social_networks=[0])]
        p = _write_json(tmp_path, "profiles.json", profiles)
        result = load_agent_profiles(p)
        assert result[1].social_networks == (0,)

    # ── R3: post-parse 参照チェックのエラーに行番号が入ること ───────────────

    def test_agent_state_agent_id_check_includes_lineno(self, tmp_path):
        """異常系[R3]: agent_states.jsonl の agent_id 参照エラーに行番号が含まれる。
        1 行目は有効、2 行目に不正な agent_id を置いてエラーの ":2" を確認する。
        """
        rows = [
            _agent_state(agent_id=0, tick=0, time="08:00:00"),
            _agent_state(agent_id=99, tick=1, time="08:05:00"),  # 2行目 / 不正
        ]
        p = _write_jsonl(tmp_path, "states.jsonl", rows)
        with pytest.raises(ValidationError) as exc_info:
            load_agent_states(p, agent_ids=frozenset({0}))
        # エラーメッセージに行番号 "2" が含まれること
        assert ":2" in str(exc_info.value)

    def test_visit_record_agent_id_check_includes_lineno(self, tmp_path):
        """異常系[R3]: poi_visit_records.jsonl の agent_id 参照エラーに行番号が含まれる。"""
        rows = [
            _visit_record(agent_id=0),
            _visit_record(agent_id=99),  # 2行目 / 不正
        ]
        p = _write_jsonl(tmp_path, "visits.jsonl", rows)
        with pytest.raises(ValidationError) as exc_info:
            load_visit_records(p, agent_ids=frozenset({0}))
        assert ":2" in str(exc_info.value)

    def test_interaction_event_agent_id_check_includes_lineno(self, tmp_path):
        """異常系[R3]: interaction_events.jsonl の agent_ids 参照エラーに行番号が含まれる。"""
        rows = [
            _interaction_event(tick=0, time="08:00:00", agent_ids=[0, 1]),
            _interaction_event(tick=1, time="08:05:00", agent_ids=[0, 99]),  # 2行目 / 不正
        ]
        p = _write_jsonl(tmp_path, "interactions.jsonl", rows)
        with pytest.raises(ValidationError) as exc_info:
            load_interaction_events(p, agent_ids=frozenset({0, 1}))
        assert ":2" in str(exc_info.value)

    # ── O1: social_networks の dangling reference → ValidationError ──────────

    def test_social_networks_dangling_reference_raises(self, tmp_path):
        """異常系[O1]: social_networks に存在しない agent_id を参照すると ValidationError。
        同一ファイル内に存在しない agent_id (999) を参照するケース。
        """
        # agent_id 0 のみ存在するファイルで social_networks=[999] を参照
        profiles = [_agent_profile(0, social_networks=[999])]
        p = _write_json(tmp_path, "profiles.json", profiles)
        with pytest.raises(ValidationError, match="dangling"):
            load_agent_profiles(p)

    def test_social_networks_existing_reference_is_valid(self, tmp_path):
        """正常系[O1]: social_networks が同一ファイル内に存在する agent_id を参照 → 正常。"""
        profiles = [
            _agent_profile(0, social_networks=[1]),
            _agent_profile(1, social_networks=[0]),
        ]
        p = _write_json(tmp_path, "profiles.json", profiles)
        result = load_agent_profiles(p)
        assert result[0].social_networks == (1,)
        assert result[1].social_networks == (0,)

    # ── O2: relationship_delta.from/to が非文字列 → ValidationError ─────────

    def test_relationship_delta_from_integer_raises(self, tmp_path):
        """異常系[O2]: relationship_delta.from が int → ValidationError。"""
        rows = [_interaction_event(
            relationship_delta={"from": 123, "to": "friend"},
        )]
        p = _write_jsonl(tmp_path, "interactions.jsonl", rows)
        with pytest.raises(ValidationError, match="relationship_delta.from"):
            load_interaction_events(p)

    def test_relationship_delta_to_none_raises(self, tmp_path):
        """異常系[O2]: relationship_delta.to が None → ValidationError。"""
        rows = [_interaction_event(
            relationship_delta={"from": "stranger", "to": None},
        )]
        p = _write_jsonl(tmp_path, "interactions.jsonl", rows)
        with pytest.raises(ValidationError, match="relationship_delta.to"):
            load_interaction_events(p)

    def test_relationship_delta_both_strings_is_valid(self, tmp_path):
        """正常系[O2]: relationship_delta.from/to が文字列 → 正常ロード。"""
        rows = [_interaction_event(
            relationship_delta={"from": "stranger", "to": "acquaintance"},
        )]
        p = _write_jsonl(tmp_path, "interactions.jsonl", rows)
        events = load_interaction_events(p)
        assert events[0].relationship_delta == {"from": "stranger", "to": "acquaintance"}


# ─────────────────────────────────────────────────────────────────────────────
# WO-006: AgentProfile rich profile フィールド (surname/given/occupation/personality/hobbies/day_pattern)
# ─────────────────────────────────────────────────────────────────────────────

class TestRichProfileFields:
    """WO-006: surname/given/occupation/personality/hobbies/day_pattern の ロード検証。"""

    def test_surname_and_given_loaded_as_named_fields(self, tmp_path):
        """正常系: surname/given を含む profile が AgentProfile.surname/given として取得できる。"""
        profiles = [_agent_profile(0, surname="田中", given="健")]
        p = _write_json(tmp_path, "profiles.json", profiles)
        result = load_agent_profiles(p)
        assert result[0].surname == "田中"
        assert result[0].given == "健"

    def test_occupation_loaded_as_named_field(self, tmp_path):
        """正常系: occupation を含む profile が AgentProfile.occupation として取得できる。"""
        profiles = [_agent_profile(0, occupation="会社員")]
        p = _write_json(tmp_path, "profiles.json", profiles)
        result = load_agent_profiles(p)
        assert result[0].occupation == "会社員"

    def test_personality_loaded_as_named_field(self, tmp_path):
        """正常系: personality を含む profile が AgentProfile.personality として取得できる。"""
        profiles = [_agent_profile(0, personality="几帳面")]
        p = _write_json(tmp_path, "profiles.json", profiles)
        result = load_agent_profiles(p)
        assert result[0].personality == "几帳面"

    def test_hobbies_loaded_as_named_field(self, tmp_path):
        """正常系: hobbies (list) を含む profile が AgentProfile.hobbies として取得できる。"""
        profiles = [_agent_profile(0, hobbies=["読書", "ランニング"])]
        p = _write_json(tmp_path, "profiles.json", profiles)
        result = load_agent_profiles(p)
        assert result[0].hobbies == ("読書", "ランニング")

    def test_day_pattern_loaded_as_named_field(self, tmp_path):
        """正常系: day_pattern を含む profile が AgentProfile.day_pattern として取得できる。"""
        profiles = [_agent_profile(0, day_pattern="morning")]
        p = _write_json(tmp_path, "profiles.json", profiles)
        result = load_agent_profiles(p)
        assert result[0].day_pattern == "morning"

    def test_rich_profile_all_optional(self, tmp_path):
        """正常系: rich フィールドを全て省略しても既存 profile は正常ロードできる (後方互換)。"""
        profiles = [_agent_profile(0)]  # rich フィールドなし
        p = _write_json(tmp_path, "profiles.json", profiles)
        result = load_agent_profiles(p)
        assert result[0].surname is None
        assert result[0].given is None
        assert result[0].occupation is None
        assert result[0].personality is None
        assert result[0].hobbies == ()
        assert result[0].day_pattern is None

    def test_rich_profile_full_round_trip(self, tmp_path):
        """正常系: 全 rich フィールドを含む profile が完全にロードできる。"""
        profiles = [_agent_profile(
            0,
            surname="井上",
            given="翔",
            occupation="エンジニア",
            personality="内向的",
            hobbies=["プログラミング", "ゲーム"],
            day_pattern="night",
        )]
        p = _write_json(tmp_path, "profiles.json", profiles)
        result = load_agent_profiles(p)
        r = result[0]
        assert r.surname == "井上"
        assert r.given == "翔"
        assert r.occupation == "エンジニア"
        assert r.personality == "内向的"
        assert r.hobbies == ("プログラミング", "ゲーム")
        assert r.day_pattern == "night"
