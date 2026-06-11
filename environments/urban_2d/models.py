"""
urban_2d データモデル。

正本: docs/subagents/contracts/urban-ecosystem-data-contract.md v0.7.1

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

ACTIVITY_KIND_VALUES = frozenset({
    "home", "work", "study", "lunch", "errand", "social", "go_home", "wander",
})

ROUTE_MODE_VALUES = frozenset({"roadnet", "linear_fallback"})

VISIT_ACTION_VALUES = frozenset({"visit"})

INTERACTION_TYPE_VALUES = frozenset({
    "meeting", "conversation", "conflict", "farewell",
})

RELATIONSHIP_STATE_VALUES = frozenset({
    "rival", "stranger", "acquaintance", "friend", "close_friend",
})

AGENT_ROLE_VALUES = frozenset({"office_worker", "student", "other"})

MATRIX_EVENT_TYPE_VALUES = frozenset({
    "takeover_start", "takeover_end", "world_transition", "heartbeat",
    "stale_report", "human_gate",
})

MATRIX_ROLE_VALUES = frozenset({
    "sentinel_mvp", "bridge_agent", "guide_agent", "operator_agent", "sentinel_swarm",
})

WORLD_LAYER_VALUES = frozenset({"real", "virtual", "liminal"})

MATRIX_EXIT_REASON_VALUES = frozenset({
    "ttl_expired", "manual_release", "world_transition", "simulation_end", "error",
})

MATRIX_EVIDENCE_TYPE_VALUES = frozenset({
    "replay_state", "matrix_event", "human_gate", "derived_metric",
})

MATRIX_HUMAN_GATE_ACTION_VALUES = frozenset({
    "public_pr", "git_push", "cloud_run_deploy", "external_api",
    "secret_access", "cost_spend",
})

MATRIX_HUMAN_GATE_STATUS_VALUES = frozenset({
    "requires_human", "approved", "rejected",
})

MATRIX_SWARM_STATUS_VALUES = frozenset({"alive", "stale"})

MATRIX_SWARM_STALE_AFTER_TICKS_DEFAULT = 3
MATRIX_SWARM_ORPHAN_TOLERANCE_DEFAULT = 0

WORLD_LAYER_MODEL = {
    "real": {
        "entry_events": ("takeover_end", "world_transition"),
        "exit_layers": ("virtual", "liminal"),
        "transition_cost": {"virtual": 1, "liminal": 1},
        "evidence_types": ("replay_state", "matrix_event"),
    },
    "virtual": {
        "entry_events": ("takeover_start", "world_transition"),
        "exit_layers": ("real", "liminal"),
        "transition_cost": {"real": 1, "liminal": 1},
        "evidence_types": ("matrix_event", "derived_metric"),
    },
    "liminal": {
        "entry_events": ("world_transition",),
        "exit_layers": ("real", "virtual"),
        "transition_cost": {"real": 2, "virtual": 2},
        "evidence_types": ("matrix_event", "human_gate"),
    },
}

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
      Optional: current_poi_id, target_poi_id, route_mode
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
    route_mode: Optional[str] = None
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


@dataclass(frozen=True)
class MatrixEvent:
    """MATRIX Mode Event JSONL の 1 行。

    contract §MATRIX Mode Event JSONL v0.7.1:
      Required: tick, day, time, type, agent_id, matrix_role
      Optional: ttl_ticks, exit_reason, trigger_id, source_layer, target_layer,
                world_layer, transition_cost, evidence_type, evidence_ref,
                guide_summary, candidate_transitions, gate_action, gate_status,
                gate_reason, swarm_status, heartbeat_interval_ticks,
                stale_after_ticks, orphan_tolerance, last_heartbeat_tick,
                missed_heartbeats, reason,
                exchange_cost_payload (MP-002 / v0.7.0),
                exchanged (MP-002 / v0.7.0),
                hierarchy_rank (MP-003 / v0.7.1),
                sworn_duty (MP-003 / v0.7.1)
    """
    tick: int
    day: int
    time: str
    type: str
    agent_id: int
    matrix_role: str
    ttl_ticks: Optional[int] = None
    exit_reason: Optional[str] = None
    trigger_id: Optional[str] = None
    source_layer: Optional[str] = None
    target_layer: Optional[str] = None
    world_layer: Optional[str] = None
    transition_cost: Optional[int] = None
    evidence_type: Optional[str] = None
    evidence_ref: Optional[str] = None
    guide_summary: Optional[str] = None
    candidate_transitions: Optional[tuple[dict[str, Any], ...]] = None
    gate_action: Optional[str] = None
    gate_status: Optional[str] = None
    gate_reason: Optional[str] = None
    swarm_status: Optional[str] = None
    heartbeat_interval_ticks: Optional[int] = None
    stale_after_ticks: Optional[int] = None
    orphan_tolerance: Optional[int] = None
    last_heartbeat_tick: Optional[int] = None
    missed_heartbeats: Optional[int] = None
    reason: Optional[str] = None
    # MP-002 exchange_pair (v0.7.0): world_transition の等価コスト記録
    exchange_cost_payload: Optional[Any] = None  # string or dict
    exchanged: Optional[bool] = None
    # MP-003 oath_chain (v0.7.1): takeover_start の命令権限階層と役割誓約
    hierarchy_rank: Optional[int] = None   # 0 = apex (最上位権限)
    sworn_duty: Optional[str] = None       # 人間可読な役割宣言。例: "threat_containment"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Activity:
    """Activity plan の 1 activity。

    contract §Activity Plans JSONL:
      Required: kind, start, end
      Optional: poi_id, category
    """
    kind: str
    start: str
    end: str
    poi_id: Optional[str] = None
    category: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActivityPlan:
    """Activity Plans JSONL の 1 行。

    1 agent / 1 day の予定を表す optional input。
    """
    agent_id: int
    day: int
    activities: tuple[Activity, ...]
    extra: dict[str, Any] = field(default_factory=dict)
