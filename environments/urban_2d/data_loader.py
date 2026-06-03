"""
urban_2d データローダー。

GeoJSON / JSON / JSONL ファイルを読み込み、正規化・検証して
models.py の dataclass を返す。

正本: docs/subagents/contracts/urban-ecosystem-data-contract.md v0.5.0
検証仕様: docs/ai-ecosystem-tool-spec.md §13.1

エラー報告ポリシー:
  - 構造・型・必須フィールド違反 → ValidationError (即時 raise)
  - 未知 enum 値           → ValidationWarning (リスト収集後まとめて警告)
  - ID 参照整合の問題      → ValidationError (post-parse チェックで raise)

エラーメッセージ形式: "ファイル名:行番号 フィールド 期待値 (実際値)"
  JSONL の行番号は 1 始まり。JSON/GeoJSON は "line:N/A" とする。
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import Any, Optional, Union

from .models import (
    POI,
    AOI,
    Road,
    AgentProfile,
    AgentState,
    Activity,
    ActivityPlan,
    VisitRecord,
    InteractionEvent,
    ACTION_VALUES,
    ACTIVITY_KIND_VALUES,
    AGENT_STATUS_VALUES,
    AGENT_ROLE_VALUES,
    INTERACTION_TYPE_VALUES,
    RELATIONSHIP_STATE_VALUES,
    ROUTE_MODE_VALUES,
    VISIT_ACTION_VALUES,
    TIME_RE,
    TICK_MINUTES,
    DAY_START_MINUTES,
    LAT_RANGE,
    LON_RANGE,
)

# ─────────────────────────────────────────────────────────────────────────────
# 例外 / 警告クラス
# ─────────────────────────────────────────────────────────────────────────────


class ValidationError(ValueError):
    """データ契約違反 (即修正が必要な構造・型・参照エラー)。"""


class ValidationWarning(UserWarning):
    """未知 enum 値などの警告 (reader は保持を続ける)。"""


# ─────────────────────────────────────────────────────────────────────────────
# 内部ユーティリティ
# ─────────────────────────────────────────────────────────────────────────────

def _loc(filename: str, lineno: Union[int, str] = "N/A") -> str:
    """エラー位置文字列を返す。"""
    return f"{filename}:{lineno}"


def _require(
    cond: bool,
    loc: str,
    field: str,
    expected: str,
    actual: Any = None,
) -> None:
    """条件が偽なら ValidationError を raise する。"""
    if not cond:
        msg = f"{loc} フィールド={field!r} 期待={expected}"
        if actual is not None:
            msg += f" 実際={actual!r}"
        raise ValidationError(msg)


def _warn_enum(
    loc: str,
    field: str,
    value: Any,
    allowed: frozenset,
) -> None:
    """未知 enum 値を ValidationWarning として発行する。"""
    warnings.warn(
        f"{loc} フィールド={field!r} 未知値={value!r} 許容値={sorted(allowed)}",
        ValidationWarning,
        stacklevel=4,
    )


def _check_lat(loc: str, field: str, val: Any) -> float:
    """lat を検証して float を返す。"""
    _require(isinstance(val, (int, float)), loc, field, "number (lat)", val)
    fv = float(val)
    _require(
        LAT_RANGE[0] <= fv <= LAT_RANGE[1],
        loc, field, f"lat in [{LAT_RANGE[0]}, {LAT_RANGE[1]}]", fv,
    )
    return fv


def _check_lon(loc: str, field: str, val: Any) -> float:
    """lon を検証して float を返す。"""
    _require(isinstance(val, (int, float)), loc, field, "number (lon)", val)
    fv = float(val)
    _require(
        LON_RANGE[0] <= fv <= LON_RANGE[1],
        loc, field, f"lon in [{LON_RANGE[0]}, {LON_RANGE[1]}]", fv,
    )
    return fv


def _check_time(loc: str, field: str, val: Any) -> str:
    """time を HH:MM:SS 形式で検証して str を返す。"""
    _require(isinstance(val, str), loc, field, "string HH:MM:SS", val)
    _require(
        bool(TIME_RE.match(val)),
        loc, field, "HH:MM:SS", val,
    )
    return val


def _tick_to_time(tick: int) -> str:
    """tick を time 文字列 (HH:MM:00) に変換する。

    Args:
        tick: 0 始まりの当日 tick。1 日内での位置 (tick % ticks_per_day 適用後) を渡す。
              0 → "08:00:00"、1 → "08:05:00" など (O3)。
    """
    total_minutes = DAY_START_MINUTES + tick * TICK_MINUTES
    hh = total_minutes // 60
    mm = total_minutes % 60
    return f"{hh:02d}:{mm:02d}:00"


def _check_tick_day_time_consistency(
    loc: str,
    tick: int,
    day: int,
    time_str: str,
) -> None:
    """tick/day/time の整合性を検証する (contract §Time and Tick)。

    [推測] contract §Time and Tick の変換式を適用:
      minutes = DAY_START_MINUTES + tick * TICK_MINUTES
      time = HH:MM:00
    tick が多日にまたがる場合 day は増えるが time は当日の時刻 (08:00 起点) を表す。
    そのため tick から日内位置 (tick % TICKS_PER_DAY) を計算して time と照合する。
    """
    ticks_per_day = (24 * 60 - DAY_START_MINUTES) // TICK_MINUTES  # 192
    tick_in_day = tick % ticks_per_day
    expected_time = _tick_to_time(tick_in_day)
    _require(
        time_str == expected_time,
        loc, "time",
        f"{expected_time} (tick={tick} day={day} から算出)",
        time_str,
    )


def _extract_extra(obj: dict, known_keys: set) -> dict:
    """既知キー以外の余剰フィールドを返す (reader は未知フィールドを保持)。"""
    return {k: v for k, v in obj.items() if k not in known_keys}


def _read_json(path: Path, filename: str) -> Any:
    """JSON ファイルを読み込む。"""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"{filename}:N/A JSON パースエラー: {exc}"
        ) from exc


def _iter_jsonl(path: Path, filename: str):
    """JSONL を 1 行ずつ yield する。行番号は 1 始まり。"""
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield lineno, json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    f"{_loc(filename, lineno)} JSONL パースエラー: {exc}"
                ) from exc


def _check_geojson_feature_collection(data: Any, filename: str) -> list:
    """GeoJSON FeatureCollection を検証して features リストを返す。"""
    loc = _loc(filename)
    _require(isinstance(data, dict), loc, "type", "GeoJSON FeatureCollection (dict)")
    _require(
        data.get("type") == "FeatureCollection",
        loc, "type", "FeatureCollection", data.get("type"),
    )
    _require(
        isinstance(data.get("features"), list),
        loc, "features", "list",
    )
    return data["features"]


# ─────────────────────────────────────────────────────────────────────────────
# POI ローダー (pois.geojson)
# ─────────────────────────────────────────────────────────────────────────────

_POI_KNOWN_PROPS = {"id", "category", "name", "source"}
_CATEGORY_RE = re.compile(r"^[A-Za-z0-9_]+-[A-Za-z0-9_]+$")


def _parse_poi_feature(feature: Any, idx: int, filename: str) -> POI:
    """GeoJSON Feature を POI に変換する。"""
    loc = _loc(filename, f"feature[{idx}]")

    _require(isinstance(feature, dict), loc, "feature", "dict")
    geom = feature.get("geometry", {})
    _require(
        isinstance(geom, dict) and geom.get("type") == "Point",
        loc, "geometry.type", "Point", geom.get("type") if isinstance(geom, dict) else geom,
    )
    coords = geom.get("coordinates", [])
    _require(
        isinstance(coords, list) and len(coords) >= 2,
        loc, "geometry.coordinates", "[lon, lat] list",
    )
    lon = _check_lon(loc, "geometry.coordinates[0] (lon)", coords[0])
    lat = _check_lat(loc, "geometry.coordinates[1] (lat)", coords[1])

    props = feature.get("properties") or {}
    _require(isinstance(props, dict), loc, "properties", "dict")

    _require("id" in props, loc, "properties.id", "required string poi_*")
    pid = props["id"]
    # contract §POI Feature: id は "poi_" 始まりの文字列のみ許可。
    # "initial_position" は VisitRecord.poi_id の参照先専用の予約値であり、
    # POI Feature id としては不正 (R1)。
    _require(
        isinstance(pid, str) and pid.startswith("poi_"),
        loc, "properties.id", "string starting with 'poi_'", pid,
    )

    _require("category" in props, loc, "properties.category", "required string <group>-<sub>")
    category = props["category"]
    _require(
        isinstance(category, str) and bool(_CATEGORY_RE.match(category)),
        loc, "properties.category", "<group>-<sub> 形式", category,
    )

    extra = _extract_extra(props, _POI_KNOWN_PROPS)
    return POI(
        id=pid,
        category=category,
        lon=lon,
        lat=lat,
        name=props.get("name"),
        source=props.get("source"),
        extra=extra,
    )


def load_pois(path: Union[str, Path]) -> list[POI]:
    """pois.geojson を読み込み POI リストを返す。

    ID 重複があれば ValidationError を raise する。
    """
    path = Path(path)
    filename = path.name
    data = _read_json(path, filename)
    features = _check_geojson_feature_collection(data, filename)

    pois: list[POI] = []
    for idx, feature in enumerate(features):
        pois.append(_parse_poi_feature(feature, idx, filename))

    # ID 一意チェック
    _check_unique_ids([p.id for p in pois], filename)
    return pois


# ─────────────────────────────────────────────────────────────────────────────
# AOI ローダー (aois.geojson)
# ─────────────────────────────────────────────────────────────────────────────

_AOI_KNOWN_PROPS = {"id", "name", "category"}
_AOI_GEOM_TYPES = frozenset({"Polygon", "MultiPolygon"})


def _parse_aoi_feature(feature: Any, idx: int, filename: str) -> AOI:
    """GeoJSON Feature を AOI に変換する。"""
    loc = _loc(filename, f"feature[{idx}]")

    _require(isinstance(feature, dict), loc, "feature", "dict")
    geom = feature.get("geometry", {})
    _require(isinstance(geom, dict), loc, "geometry", "dict")
    geom_type = geom.get("type")
    _require(
        geom_type in _AOI_GEOM_TYPES,
        loc, "geometry.type", "Polygon|MultiPolygon", geom_type,
    )

    props = feature.get("properties") or {}
    _require(isinstance(props, dict), loc, "properties", "dict")
    _require("id" in props, loc, "properties.id", "required string aoi_*")
    aid = props["id"]
    _require(
        isinstance(aid, str) and aid.startswith("aoi_"),
        loc, "properties.id", "string starting with 'aoi_'", aid,
    )

    extra = _extract_extra(props, _AOI_KNOWN_PROPS)
    return AOI(
        id=aid,
        geometry_type=geom_type,
        coordinates=geom.get("coordinates"),
        name=props.get("name"),
        category=props.get("category"),
        extra=extra,
    )


def load_aois(path: Union[str, Path]) -> list[AOI]:
    """aois.geojson を読み込み AOI リストを返す。"""
    path = Path(path)
    filename = path.name
    data = _read_json(path, filename)
    features = _check_geojson_feature_collection(data, filename)

    aois: list[AOI] = []
    for idx, feature in enumerate(features):
        aois.append(_parse_aoi_feature(feature, idx, filename))

    _check_unique_ids([a.id for a in aois], filename)
    return aois


# ─────────────────────────────────────────────────────────────────────────────
# Road ローダー (roadnet.geojson)
# ─────────────────────────────────────────────────────────────────────────────

_ROAD_KNOWN_PROPS = {"id", "length_m", "walkable"}
_ROAD_GEOM_TYPES = frozenset({"LineString", "MultiLineString"})


def _parse_road_feature(feature: Any, idx: int, filename: str) -> Road:
    """GeoJSON Feature を Road に変換する。"""
    loc = _loc(filename, f"feature[{idx}]")

    _require(isinstance(feature, dict), loc, "feature", "dict")
    geom = feature.get("geometry", {})
    _require(isinstance(geom, dict), loc, "geometry", "dict")
    geom_type = geom.get("type")
    _require(
        geom_type in _ROAD_GEOM_TYPES,
        loc, "geometry.type", "LineString|MultiLineString", geom_type,
    )

    props = feature.get("properties") or {}
    _require(isinstance(props, dict), loc, "properties", "dict")
    _require("id" in props, loc, "properties.id", "required string road_*")
    rid = props["id"]
    _require(
        isinstance(rid, str) and rid.startswith("road_"),
        loc, "properties.id", "string starting with 'road_'", rid,
    )

    length_m = props.get("length_m")
    if length_m is not None:
        _require(
            isinstance(length_m, (int, float)) and float(length_m) >= 0,
            loc, "properties.length_m", "number >= 0", length_m,
        )
        length_m = float(length_m)

    walkable_raw = props.get("walkable", True)
    _require(
        isinstance(walkable_raw, bool),
        loc, "properties.walkable", "boolean", walkable_raw,
    )

    extra = _extract_extra(props, _ROAD_KNOWN_PROPS)
    return Road(
        id=rid,
        geometry_type=geom_type,
        coordinates=geom.get("coordinates"),
        length_m=length_m,
        walkable=bool(walkable_raw),
        extra=extra,
    )


def load_roads(path: Union[str, Path]) -> list[Road]:
    """roadnet.geojson を読み込み Road リストを返す。"""
    path = Path(path)
    filename = path.name
    data = _read_json(path, filename)
    features = _check_geojson_feature_collection(data, filename)

    roads: list[Road] = []
    for idx, feature in enumerate(features):
        roads.append(_parse_road_feature(feature, idx, filename))

    _check_unique_ids([r.id for r in roads], filename)
    return roads


# ─────────────────────────────────────────────────────────────────────────────
# AgentProfile ローダー (agent_profiles_N100.json)
# ─────────────────────────────────────────────────────────────────────────────

_PROFILE_KNOWN_KEYS = {
    "id", "name", "initial_position",
    "age", "gender", "description",
    "home_poi_id", "work_or_school_poi_id",
    "role", "social_networks",
    # WO-006: rich profile 拡張フィールド
    "surname", "given",
    "occupation", "personality", "hobbies", "day_pattern",
}


def _parse_agent_profile(obj: Any, idx: int, filename: str) -> AgentProfile:
    """dict を AgentProfile に変換する。"""
    loc = _loc(filename, f"item[{idx}]")

    _require(isinstance(obj, dict), loc, "item", "dict")
    _require("id" in obj, loc, "id", "required integer")
    _require(isinstance(obj["id"], int), loc, "id", "integer", obj.get("id"))

    _require("name" in obj, loc, "name", "required string")
    _require(isinstance(obj["name"], str), loc, "name", "string", obj.get("name"))

    _require("initial_position" in obj, loc, "initial_position", "required {lat, lon}")
    pos = obj["initial_position"]
    _require(isinstance(pos, dict), loc, "initial_position", "dict", pos)
    _require("lat" in pos, loc, "initial_position.lat", "required")
    _require("lon" in pos, loc, "initial_position.lon", "required")
    init_lat = _check_lat(loc, "initial_position.lat", pos["lat"])
    init_lon = _check_lon(loc, "initial_position.lon", pos["lon"])

    age = obj.get("age")
    if age is not None:
        _require(
            isinstance(age, int) and age >= 0,
            loc, "age", "integer >= 0", age,
        )

    role = obj.get("role", "other")
    if role not in AGENT_ROLE_VALUES:
        _warn_enum(loc, "role", role, AGENT_ROLE_VALUES)

    optional_strings: dict[str, str | None] = {}
    for field in ("surname", "given", "occupation", "personality", "day_pattern"):
        val = obj.get(field)
        if field in obj:
            _require(isinstance(val, str), loc, field, "string", val)
        optional_strings[field] = val

    sn_raw = obj.get("social_networks", [])
    _require(isinstance(sn_raw, list), loc, "social_networks", "list")
    # 全要素が int 型 (bool は int サブクラスだが除外) であることを事前検証する (R2)。
    # 非整数要素が混在した場合は生 ValueError ではなく ValidationError を出す。
    _require(
        all(isinstance(x, int) and not isinstance(x, bool) for x in sn_raw),
        loc, "social_networks", "list of integers (bool 不可)",
        [x for x in sn_raw if not isinstance(x, int) or isinstance(x, bool)] or None,
    )
    social_networks = tuple(sn_raw)

    # WO-006: hobbies は list[str] → tuple[str, ...]
    # contract §Agent Profile: hobbies は string の配列 / 1 件以上 (present の場合のみ)
    hobbies_present = "hobbies" in obj
    if hobbies_present:
        hobbies_raw = obj.get("hobbies")
        # present の場合はまず型を検証する。null / 非 list を [] に丸めてから件数検査すると
        # 「list でない」型エラーが「1 件以上」件数エラーに化けるため、型チェックを先に置く。
        _require(isinstance(hobbies_raw, list), loc, "hobbies", "list of strings", hobbies_raw)
        # present かつ空リストは contract 違反 (1 件以上)
        _require(
            len(hobbies_raw) >= 1,
            loc, "hobbies", "1 件以上の string (present の場合)", hobbies_raw,
        )
        # 全要素が string であることを検証する
        _require(
            all(isinstance(x, str) for x in hobbies_raw),
            loc, "hobbies", "全要素が string",
            [x for x in hobbies_raw if not isinstance(x, str)] or None,
        )
    else:
        # absent (キーなし) は後方互換: 空扱い
        hobbies_raw = []

    extra = _extract_extra(obj, _PROFILE_KNOWN_KEYS)
    return AgentProfile(
        id=obj["id"],
        name=obj["name"],
        initial_lat=init_lat,
        initial_lon=init_lon,
        age=age,
        gender=obj.get("gender"),
        description=obj.get("description"),
        home_poi_id=obj.get("home_poi_id"),
        work_or_school_poi_id=obj.get("work_or_school_poi_id"),
        role=role,
        social_networks=social_networks,
        surname=optional_strings["surname"],
        given=optional_strings["given"],
        occupation=optional_strings["occupation"],
        personality=optional_strings["personality"],
        hobbies=tuple(hobbies_raw),
        day_pattern=optional_strings["day_pattern"],
        extra=extra,
    )


def load_agent_profiles(
    path: Union[str, Path],
    poi_ids: Optional[frozenset[str]] = None,
) -> list[AgentProfile]:
    """agent_profiles_N100.json を読み込み AgentProfile リストを返す。

    poi_ids が与えられた場合、home_poi_id / work_or_school_poi_id の
    参照整合性を検証する。
    """
    path = Path(path)
    filename = path.name
    data = _read_json(path, filename)
    _require(
        isinstance(data, list),
        _loc(filename), "root", "list of AgentProfile objects",
    )

    profiles: list[AgentProfile] = []
    for idx, obj in enumerate(data):
        profiles.append(_parse_agent_profile(obj, idx, filename))

    _check_unique_ids([p.id for p in profiles], filename)

    if poi_ids is not None:
        for p in profiles:
            loc = _loc(filename, f"id={p.id}")
            if p.home_poi_id is not None:
                _require(
                    p.home_poi_id in poi_ids,
                    loc, "home_poi_id",
                    "既存 POI id", p.home_poi_id,
                )
            if p.work_or_school_poi_id is not None:
                _require(
                    p.work_or_school_poi_id in poi_ids,
                    loc, "work_or_school_poi_id",
                    "既存 POI id", p.work_or_school_poi_id,
                )

    # social_networks 自己参照チェック + 重複チェック + dangling reference チェック (O1)
    all_agent_ids = frozenset(p.id for p in profiles)
    for p in profiles:
        loc = _loc(filename, f"id={p.id}")
        _require(
            p.id not in p.social_networks,
            loc, "social_networks",
            "自己 id を含めない",
            f"self id {p.id} found",
        )
        # 重複チェック
        _require(
            len(p.social_networks) == len(set(p.social_networks)),
            loc, "social_networks",
            "重複なし",
            f"duplicates in {p.social_networks}",
        )
        # dangling reference チェック: 存在しない agent_id を参照していないか
        # contract §Agent Profile「既存 agent id の配列」(O1)
        dangling = [x for x in p.social_networks if x not in all_agent_ids]
        _require(
            len(dangling) == 0,
            loc, "social_networks",
            "既存 agent id のみ",
            f"dangling ids: {dangling}",
        )

    return profiles


# ─────────────────────────────────────────────────────────────────────────────
# AgentState ローダー (agent_states.jsonl)
# ─────────────────────────────────────────────────────────────────────────────

_STATE_KNOWN_KEYS = {
    "tick", "day", "time", "agent_id", "lat", "lon",
    "action", "status", "current_poi_id", "target_poi_id", "route_mode",
}


def _parse_agent_state(obj: dict, lineno: int, filename: str) -> AgentState:
    """dict を AgentState に変換する。"""
    loc = _loc(filename, lineno)

    for req in ("tick", "day", "time", "agent_id", "lat", "lon", "action", "status"):
        _require(req in obj, loc, req, "required")

    tick = obj["tick"]
    day = obj["day"]
    _require(isinstance(tick, int) and tick >= 0, loc, "tick", "non-negative integer", tick)
    _require(isinstance(day, int) and day >= 0, loc, "day", "non-negative integer", day)

    time_str = _check_time(loc, "time", obj["time"])
    _check_tick_day_time_consistency(loc, tick, day, time_str)

    _require(isinstance(obj["agent_id"], int), loc, "agent_id", "integer")
    lat = _check_lat(loc, "lat", obj["lat"])
    lon = _check_lon(loc, "lon", obj["lon"])

    action = obj["action"]
    if action not in ACTION_VALUES:
        _warn_enum(loc, "action", action, ACTION_VALUES)

    status = obj["status"]
    if status not in AGENT_STATUS_VALUES:
        _warn_enum(loc, "status", status, AGENT_STATUS_VALUES)

    route_mode = obj.get("route_mode")
    if route_mode is not None and route_mode not in ROUTE_MODE_VALUES:
        _warn_enum(loc, "route_mode", route_mode, ROUTE_MODE_VALUES)

    extra = _extract_extra(obj, _STATE_KNOWN_KEYS)
    return AgentState(
        tick=tick,
        day=day,
        time=time_str,
        agent_id=obj["agent_id"],
        lat=lat,
        lon=lon,
        action=action,
        status=status,
        current_poi_id=obj.get("current_poi_id"),
        target_poi_id=obj.get("target_poi_id"),
        route_mode=route_mode,
        extra=extra,
    )


def load_agent_states(
    path: Union[str, Path],
    agent_ids: Optional[frozenset[int]] = None,
    poi_ids: Optional[frozenset[str]] = None,
) -> list[AgentState]:
    """agent_states.jsonl を読み込み AgentState リストを返す。

    agent_ids が与えられた場合、参照整合性を検証する。
    """
    path = Path(path)
    filename = path.name
    # post-parse 参照チェックで行番号を出すため (lineno, record) のペアで保持する (R3)
    state_rows: list[tuple[int, AgentState]] = []
    for lineno, obj in _iter_jsonl(path, filename):
        state_rows.append((lineno, _parse_agent_state(obj, lineno, filename)))

    if agent_ids is not None:
        for lineno, s in state_rows:
            # エラーロケーションに行番号を含める (contract §13.1 / R3)
            loc = _loc(filename, lineno)
            _require(
                s.agent_id in agent_ids,
                loc, "agent_id", "既存 agent id", s.agent_id,
            )

    if poi_ids is not None:
        for lineno, s in state_rows:
            loc = _loc(filename, lineno)
            if s.current_poi_id is not None:
                _require(
                    s.current_poi_id in poi_ids,
                    loc, "current_poi_id", "既存 POI id", s.current_poi_id,
                )
            if s.target_poi_id is not None:
                _require(
                    s.target_poi_id in poi_ids,
                    loc, "target_poi_id", "既存 POI id", s.target_poi_id,
                )

    return [s for _, s in state_rows]


# ─────────────────────────────────────────────────────────────────────────────
# ActivityPlan ローダー (activity_plans.jsonl)
# ─────────────────────────────────────────────────────────────────────────────

_PLAN_KNOWN_KEYS = {"agent_id", "day", "activities"}
_ACTIVITY_KNOWN_KEYS = {"kind", "start", "end", "poi_id", "category"}


def _time_to_minutes(time_str: str) -> int:
    hh, mm, ss = [int(x) for x in time_str.split(":")]
    return hh * 60 + mm + (1 if ss > 0 else 0)


def _parse_activity(obj: dict, lineno: int, filename: str, index: int) -> Activity:
    loc = _loc(filename, lineno)
    _require(isinstance(obj, dict), loc, f"activities[{index}]", "object")
    for req in ("kind", "start", "end"):
        _require(req in obj, loc, f"activities[{index}].{req}", "required")

    kind = obj["kind"]
    _require(
        isinstance(kind, str) and kind in ACTIVITY_KIND_VALUES,
        loc,
        f"activities[{index}].kind",
        f"one of {sorted(ACTIVITY_KIND_VALUES)}",
        kind,
    )
    start = _check_time(loc, f"activities[{index}].start", obj["start"])
    end = _check_time(loc, f"activities[{index}].end", obj["end"])
    _require(
        _time_to_minutes(start) < _time_to_minutes(end),
        loc,
        f"activities[{index}].end",
        "start より後の時刻",
        end,
    )

    poi_id = obj.get("poi_id")
    category = obj.get("category")
    if poi_id is not None:
        _require(isinstance(poi_id, str), loc, f"activities[{index}].poi_id", "string")
    if category is not None:
        _require(
            isinstance(category, str) and _CATEGORY_RE.match(category) is not None,
            loc,
            f"activities[{index}].category",
            "<group>-<sub>",
            category,
        )

    extra = _extract_extra(obj, _ACTIVITY_KNOWN_KEYS)
    return Activity(
        kind=kind,
        start=start,
        end=end,
        poi_id=poi_id,
        category=category,
        extra=extra,
    )


def _parse_activity_plan(obj: dict, lineno: int, filename: str) -> ActivityPlan:
    loc = _loc(filename, lineno)
    for req in ("agent_id", "day", "activities"):
        _require(req in obj, loc, req, "required")
    _require(isinstance(obj["agent_id"], int), loc, "agent_id", "integer")
    _require(
        isinstance(obj["day"], int) and obj["day"] >= 0,
        loc,
        "day",
        "non-negative integer",
        obj.get("day"),
    )
    _require(isinstance(obj["activities"], list), loc, "activities", "array")

    activities = tuple(
        _parse_activity(activity, lineno, filename, idx)
        for idx, activity in enumerate(obj["activities"])
    )
    sorted_activities = sorted(
        activities,
        key=lambda a: (_time_to_minutes(a.start), _time_to_minutes(a.end)),
    )
    for prev, cur in zip(sorted_activities, sorted_activities[1:]):
        _require(
            _time_to_minutes(prev.end) <= _time_to_minutes(cur.start),
            loc,
            "activities",
            "non-overlapping activities",
            f"{prev.start}-{prev.end} overlaps {cur.start}-{cur.end}",
        )

    extra = _extract_extra(obj, _PLAN_KNOWN_KEYS)
    return ActivityPlan(
        agent_id=obj["agent_id"],
        day=obj["day"],
        activities=activities,
        extra=extra,
    )


def load_activity_plans(
    path: Union[str, Path],
    agent_ids: Optional[frozenset[int]] = None,
    poi_ids: Optional[frozenset[str]] = None,
) -> list[ActivityPlan]:
    """activity_plans.jsonl を読み込み ActivityPlan リストを返す。

    activity_plans は optional input。指定された場合のみ agent / POI 参照整合を検証する。
    """
    path = Path(path)
    filename = path.name
    plan_rows: list[tuple[int, ActivityPlan]] = []
    seen: set[tuple[int, int]] = set()
    for lineno, obj in _iter_jsonl(path, filename):
        plan = _parse_activity_plan(obj, lineno, filename)
        loc = _loc(filename, lineno)
        key = (plan.agent_id, plan.day)
        _require(key not in seen, loc, "agent_id/day", "1行だけ", key)
        seen.add(key)
        plan_rows.append((lineno, plan))

    if agent_ids is not None:
        for lineno, plan in plan_rows:
            loc = _loc(filename, lineno)
            _require(plan.agent_id in agent_ids, loc, "agent_id", "既存 agent id", plan.agent_id)

    if poi_ids is not None:
        for lineno, plan in plan_rows:
            loc = _loc(filename, lineno)
            for idx, activity in enumerate(plan.activities):
                if activity.poi_id is not None:
                    _require(
                        activity.poi_id in poi_ids,
                        loc,
                        f"activities[{idx}].poi_id",
                        "既存 POI id",
                        activity.poi_id,
                    )

    return [p for _, p in plan_rows]


# ─────────────────────────────────────────────────────────────────────────────
# VisitRecord ローダー (poi_visit_records.jsonl)
# ─────────────────────────────────────────────────────────────────────────────

_VISIT_KNOWN_KEYS = {
    "agent_id", "day", "time", "poi_id", "action", "reason", "lat", "lon",
}

_VISIT_POI_ID_RESERVED = {"initial_position"}


def _parse_visit_record(obj: dict, lineno: int, filename: str) -> VisitRecord:
    """dict を VisitRecord に変換する。"""
    loc = _loc(filename, lineno)

    for req in ("agent_id", "day", "time", "action", "lat", "lon"):
        _require(req in obj, loc, req, "required")

    _require(isinstance(obj["agent_id"], int), loc, "agent_id", "integer")
    _require(
        isinstance(obj["day"], int) and obj["day"] >= 0,
        loc, "day", "non-negative integer", obj.get("day"),
    )
    time_str = _check_time(loc, "time", obj["time"])
    lat = _check_lat(loc, "lat", obj["lat"])
    lon = _check_lon(loc, "lon", obj["lon"])

    action = obj["action"]
    if action not in VISIT_ACTION_VALUES:
        _warn_enum(loc, "action", action, VISIT_ACTION_VALUES)

    reason = obj.get("reason")
    if reason is not None and reason not in ACTION_VALUES:
        _warn_enum(loc, "reason", reason, ACTION_VALUES)

    extra = _extract_extra(obj, _VISIT_KNOWN_KEYS)
    return VisitRecord(
        agent_id=obj["agent_id"],
        day=obj["day"],
        time=time_str,
        action=action,
        lat=lat,
        lon=lon,
        poi_id=obj.get("poi_id"),
        reason=reason,
        extra=extra,
    )


def load_visit_records(
    path: Union[str, Path],
    agent_ids: Optional[frozenset[int]] = None,
    poi_ids: Optional[frozenset[str]] = None,
) -> list[VisitRecord]:
    """poi_visit_records.jsonl を読み込み VisitRecord リストを返す。"""
    path = Path(path)
    filename = path.name
    # post-parse 参照チェックで行番号を出すため (lineno, record) のペアで保持する (R3)
    record_rows: list[tuple[int, VisitRecord]] = []
    for lineno, obj in _iter_jsonl(path, filename):
        record_rows.append((lineno, _parse_visit_record(obj, lineno, filename)))

    if agent_ids is not None:
        for lineno, r in record_rows:
            # エラーロケーションに行番号を含める (contract §13.1 / R3)
            loc = _loc(filename, lineno)
            _require(
                r.agent_id in agent_ids,
                loc, "agent_id", "既存 agent id", r.agent_id,
            )

    if poi_ids is not None:
        for lineno, r in record_rows:
            loc = _loc(filename, lineno)
            if r.poi_id is not None and r.poi_id not in _VISIT_POI_ID_RESERVED:
                _require(
                    r.poi_id in poi_ids,
                    loc, "poi_id", "既存 POI id または 'initial_position'", r.poi_id,
                )

    return [r for _, r in record_rows]


# ─────────────────────────────────────────────────────────────────────────────
# InteractionEvent ローダー (interaction_events.jsonl)
# ─────────────────────────────────────────────────────────────────────────────

_INTERACTION_KNOWN_KEYS = {
    "tick", "day", "time", "type", "agent_ids",
    "summary", "location_poi_id", "relationship_delta",
}


def _parse_interaction_event(obj: dict, lineno: int, filename: str) -> InteractionEvent:
    """dict を InteractionEvent に変換する。"""
    loc = _loc(filename, lineno)

    for req in ("tick", "day", "time", "type", "agent_ids", "summary"):
        _require(req in obj, loc, req, "required")

    tick = obj["tick"]
    day = obj["day"]
    _require(isinstance(tick, int) and tick >= 0, loc, "tick", "non-negative integer", tick)
    _require(isinstance(day, int) and day >= 0, loc, "day", "non-negative integer", day)
    time_str = _check_time(loc, "time", obj["time"])
    _check_tick_day_time_consistency(loc, tick, day, time_str)

    ev_type = obj["type"]
    if ev_type not in INTERACTION_TYPE_VALUES:
        _warn_enum(loc, "type", ev_type, INTERACTION_TYPE_VALUES)

    agent_ids_raw = obj["agent_ids"]
    _require(isinstance(agent_ids_raw, list), loc, "agent_ids", "list")
    _require(len(agent_ids_raw) >= 2, loc, "agent_ids", "len >= 2", len(agent_ids_raw))
    _require(
        all(isinstance(x, int) for x in agent_ids_raw),
        loc, "agent_ids", "integer elements",
    )
    # 重複チェック
    _require(
        len(set(agent_ids_raw)) == len(agent_ids_raw),
        loc, "agent_ids", "重複なし", agent_ids_raw,
    )
    # contract: agent_ids は caller が昇順正規化済みの値を渡す。
    _require(
        agent_ids_raw == sorted(agent_ids_raw),
        loc, "agent_ids", "昇順ソート済み", agent_ids_raw,
    )
    agent_ids = tuple(agent_ids_raw)

    _require(isinstance(obj["summary"], str), loc, "summary", "string")

    rel_delta = obj.get("relationship_delta")
    if rel_delta is not None:
        _require(isinstance(rel_delta, dict), loc, "relationship_delta", "dict")
        for key in ("from", "to"):
            _require(key in rel_delta, loc, f"relationship_delta.{key}", "required")
            val = rel_delta[key]
            # enum チェック前に文字列型であることを確認する (O2)
            _require(
                isinstance(val, str),
                loc, f"relationship_delta.{key}", "string", val,
            )
            if val not in RELATIONSHIP_STATE_VALUES:
                _warn_enum(loc, f"relationship_delta.{key}", val, RELATIONSHIP_STATE_VALUES)

    extra = _extract_extra(obj, _INTERACTION_KNOWN_KEYS)
    return InteractionEvent(
        tick=tick,
        day=day,
        time=time_str,
        type=ev_type,
        agent_ids=agent_ids,
        summary=obj["summary"],
        location_poi_id=obj.get("location_poi_id"),
        relationship_delta=rel_delta,
        extra=extra,
    )


def load_interaction_events(
    path: Union[str, Path],
    agent_ids: Optional[frozenset[int]] = None,
    poi_ids: Optional[frozenset[str]] = None,
) -> list[InteractionEvent]:
    """interaction_events.jsonl を読み込み InteractionEvent リストを返す。

    同一 tick・同一正規化ペアの重複を検出した場合 ValidationError を raise する。
    """
    path = Path(path)
    filename = path.name
    # post-parse 参照チェックで行番号を出すため (lineno, event) のペアで保持する (R3)
    event_rows: list[tuple[int, InteractionEvent]] = []
    seen_tick_pairs: set[tuple] = set()

    for lineno, obj in _iter_jsonl(path, filename):
        ev = _parse_interaction_event(obj, lineno, filename)
        event_rows.append((lineno, ev))

        # 同一 tick・同一正規化ペアの重複チェック
        key = (ev.tick, ev.agent_ids)
        loc = _loc(filename, lineno)
        _require(
            key not in seen_tick_pairs,
            loc, "tick+agent_ids",
            "同一 tick・同一ペアは 1 件まで",
            f"duplicate: tick={ev.tick} agents={ev.agent_ids}",
        )
        seen_tick_pairs.add(key)

    if agent_ids is not None:
        for lineno, ev in event_rows:
            # エラーロケーションに行番号を含める (contract §13.1 / R3)
            loc = _loc(filename, lineno)
            for aid in ev.agent_ids:
                _require(
                    aid in agent_ids,
                    loc, "agent_ids element", "既存 agent id", aid,
                )

    if poi_ids is not None:
        for lineno, ev in event_rows:
            loc = _loc(filename, lineno)
            if ev.location_poi_id is not None:
                _require(
                    ev.location_poi_id in poi_ids,
                    loc, "location_poi_id", "既存 POI id", ev.location_poi_id,
                )

    return [ev for _, ev in event_rows]


# ─────────────────────────────────────────────────────────────────────────────
# 共通ユーティリティ
# ─────────────────────────────────────────────────────────────────────────────

def _check_unique_ids(ids: list, filename: str) -> None:
    """ID リストに重複があれば ValidationError を raise する。"""
    seen: set = set()
    for id_val in ids:
        if id_val in seen:
            raise ValidationError(
                f"{_loc(filename)} 重複 ID={id_val!r} (各コレクション内で一意であること)"
            )
        seen.add(id_val)
