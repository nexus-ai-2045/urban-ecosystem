"""
urban_2d データモデル。

正本: docs/subagents/contracts/urban-ecosystem-data-contract.md v0.2.0

座標系:
  - GeoJSON (POI/AOI/Road): geometry.coordinates = [lon, lat] (RFC 7946)
    properties に lat/lon を重複させない。
  - Flat JSON (AgentProfile.initial_position / AgentState / VisitRecord):
    lat/lon の個別キー。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

# ── enum 許容値 (contract §Enumerations) ───────────────────────────────────

AGENT_STATUS_VALUES = frozenset({"moving", "arrived", "staying"})

ACTION_VALUES = frozenset({
    "commute", "work", "study", "lunch", "errand",
    "social", "go_home", "wander", "no_target",
})

VISIT_ACTION_VALUES = frozenset({"visit"})

INTERACTION_TYPE_VALUES = frozenset({
    "meeting", "conversation", "conflict", "farewell",
})

RELATIONSHIP_STATE_VALUES = frozenset({
    "rival", "stranger", "acquaintance", "friend", "close_friend",
})

AGENT_ROLE_VALUES = frozenset({"office_worker", "student", "other"})

# ── time フォーマット ────────────────────────────────────────────────────────

TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")

# ── 座標境界 ────────────────────────────────────────────────────────────────

LAT_RANGE = (-90.0, 90.0)
LON_RANGE = (-180.0, 180.0)

# ── tick/time 変換定数 (contract §Time and Tick) ─────────────────────────────

TICK_MINUTES = 5
DAY_START_MINUTES = 8 * 60  # 08:00:00


# ─────────────────────────────────────────────────────────────────────────────
# GeoJSON エンティティ (座標系 1: geometry.coordinates = [lon, lat])
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class POI:
    """POI Feature (Point geometry)。

    contract §POI Feature:
      Required properties: id (poi_*), category (<group>-<sub>)
      Optional properties: name, source
      Extra properties: extra に格納 (reader は未知フィールドを保持する)
    """
    id: str
    category: str
    lon: float  # GeoJSON coordinates[0]
    lat: float  # GeoJSON coordinates[1]
    name: Optional[str] = None
    source: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AOI:
    """AOI Feature (Polygon / MultiPolygon geometry)。

    contract §AOI Feature:
      Required: id (aoi_*)
      Optional: name, category
      geometry は coordinates リストとして保持。
    """
    id: str
    geometry_type: str  # "Polygon" または "MultiPolygon"
    coordinates: Any    # GeoJSON 座標配列 (nested list)
    name: Optional[str] = None
    category: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Road:
    """Road Feature (LineString / MultiLineString geometry)。

    contract §Road Feature:
      Required: id (road_*)
      Optional: length_m (>= 0), walkable (bool, default True)
    """
    id: str
    geometry_type: str  # "LineString" または "MultiLineString"
    coordinates: Any    # GeoJSON 座標配列
    length_m: Optional[float] = None
    walkable: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Flat JSON エンティティ (座標系 2: lat/lon 個別キー)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AgentProfile:
    """AgentProfile (agent_profiles_N100.json)。

    contract §Agent Profile v0.3.0:
      Required: id (int), name (str), initial_position {lat, lon}
      Optional (既存): age, gender, description, home_poi_id, work_or_school_poi_id,
                       role, social_networks
      Optional (WO-006 追加): surname, given, occupation, personality,
                              hobbies, day_pattern
    """
    id: int
    name: str
    initial_lat: float
    initial_lon: float
    age: Optional[int] = None
    gender: Optional[str] = None
    description: Optional[str] = None
    home_poi_id: Optional[str] = None
    work_or_school_poi_id: Optional[str] = None
    role: str = "other"
    social_networks: tuple[int, ...] = field(default_factory=tuple)
    # WO-006: 姓名分割
    surname: Optional[str] = None
    given: Optional[str] = None
    # WO-006: 職業詳細・性格・趣味・行動傾向
    occupation: Optional[str] = None
    personality: Optional[str] = None
    hobbies: tuple[str, ...] = field(default_factory=tuple)
    day_pattern: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentState:
    """Agent State JSONL の 1 行。

    contract §Agent State JSONL:
      Required: tick, day, time, agent_id, lat, lon, action, status
      Optional: current_poi_id, target_poi_id
    """
    tick: int
    day: int
    time: str
    agent_id: int
    lat: float
    lon: float
    action: str
    status: str
    current_poi_id: Optional[str] = None
    target_poi_id: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VisitRecord:
    """Visit Record JSONL の 1 行。

    contract §Visit Record JSONL:
      Required: agent_id, day, time, action (= "visit"), lat, lon
      Optional: poi_id (既存 POI id または "initial_position"), reason
    """
    agent_id: int
    day: int
    time: str
    action: str
    lat: float
    lon: float
    poi_id: Optional[str] = None
    reason: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InteractionEvent:
    """Interaction Event JSONL の 1 行。

    contract §Interaction Event JSONL:
      Required: tick, day, time, type, agent_ids (>=2, sorted asc), summary
      Optional: location_poi_id, relationship_delta {from, to}
    """
    tick: int
    day: int
    time: str
    type: str
    agent_ids: tuple[int, ...]
    summary: str
    location_poi_id: Optional[str] = None
    relationship_delta: Optional[dict[str, str]] = None
    extra: dict[str, Any] = field(default_factory=dict)
