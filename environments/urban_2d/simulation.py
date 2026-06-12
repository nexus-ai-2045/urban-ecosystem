"""
urban_2d ルールベースシミュレーション (§9 / §13.3 / §20)。

正本:
  - docs/ai-ecosystem-tool-spec.md §9 行動ルール / §13.3 シミュレーション検証 / §20 境界ケース
  - docs/subagents/contracts/urban-ecosystem-data-contract.md v0.7.4

責務:
  profiles + POI から tick ループを回し、agent_states.jsonl /
  poi_visit_records.jsonl / interaction_events.jsonl / summary.json /
  metrics.json を生成する。
  LLM は呼ばない (RuleBasedProvider 相当)。

決定論 (§13.3.2):
  単一 random.Random(seed) インスタンスを固定消費順で使う。同一 seed → 3 jsonl が
  byte 一致する。summary.json は started_at を含むため byte 一致対象外。

  ─ rng 消費順序 (厳守 / 変更禁止) ─────────────────────────────────────────
  各 tick で agent_id 昇順に 1 体ずつ処理し、その体について以下の順で rng を消費する:
    (1) 目的地が "weighted" / "social" モードの場合: weighted_nearest_poi の抽選
        (rng.random を 1 回)。"nearest"/"fixed_*"/"stay_current" は rng 非消費。
    (2) "wander" モードの場合: 滞在/移動の二択判定 (rng.random を 1 回)。移動と
        判定されたら近傍 POI 抽選 (weighted_nearest_poi で rng.random を 1 回)。
    (3) 目的地に到達 (arrived) しその reason が固定 tick 滞在を持つ場合:
        dwell_ticks の seeded 抽選 (lunch=1 回 / social=1 回 / errand|wander=1 回)。
  interaction の発生確率・type 抽選は単一 rng を使わず seeded_rand(run_seed, tick,
  a_id, b_id) のハッシュ値で決定する (bucket 走査順に非依存)。これにより interaction
  処理は agent ループの rng 消費順と独立し、決定論が保たれる。
  ───────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from . import rules
from .data_loader import (
    load_pois,
    load_agent_profiles,
)
from .models import Activity, ActivityPlan, POI, AgentProfile
from .models import (
    MATRIX_EVIDENCE_TYPE_VALUES,
    MATRIX_EXIT_REASON_VALUES,
    MATRIX_HUMAN_GATE_ACTION_VALUES,
    MATRIX_HUMAN_GATE_STATUS_VALUES,
    MATRIX_ROLE_VALUES,
    MATRIX_STABILIZATION_PHASE_VALUES,
    MATRIX_SWARM_ORPHAN_TOLERANCE_DEFAULT,
    MATRIX_SWARM_STALE_AFTER_TICKS_DEFAULT,
    MATRIX_SWARM_STATUS_VALUES,
    WORLD_LAYER_MODEL,
    WORLD_LAYER_VALUES,
)
from .road_graph import RoadGraph

if TYPE_CHECKING:
    # 型チェック時のみ import (循環回避 / SDK 未インストール環境での安全性)
    from app.llm_provider import LLMProvider

# tick/time 変換 (data-contract §Time and Tick)
TICK_MINUTES = rules.TICK_MINUTES
DAY_START_MINUTES = rules.DAY_START_MINUTES
TICKS_PER_DAY = rules.TICKS_PER_DAY


def tick_to_day_time(tick: int) -> tuple[int, str]:
    """ラン通算 tick から (day, time HH:MM:00) を返す (data-contract §Time and Tick)。"""
    day = tick // TICKS_PER_DAY
    in_day = tick % TICKS_PER_DAY
    total = DAY_START_MINUTES + in_day * TICK_MINUTES
    hh = total // 60
    mm = total % 60
    return day, f"{hh:02d}:{mm:02d}:00"


def _time_to_minutes(time_str: str) -> int:
    hh, mm, ss = [int(part) for part in time_str.split(":")]
    return hh * 60 + mm + (1 if ss > 0 else 0)


def _activity_kind_to_action(kind: str) -> str:
    """Activity kind を既存 AgentState.action / VisitRecord.reason 語彙へ写像する。"""
    if kind == "home":
        return "go_home"
    return kind


# ─────────────────────────────────────────────────────────────────────────────
# 内部 agent 状態 (mutable / 出力時に AgentState 行へ写像)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _AgentRuntime:
    """tick ループ中に保持する mutable な agent 状態。

    出力 (AgentState JSONL) には status/action を contract 語彙に写像して書く。
    """
    profile: AgentProfile
    lat: float
    lon: float
    # 内部状態機械 (§9.2): "idle" / "moving" / "at_poi"
    internal: str = "idle"
    action: str = "no_target"          # data-contract reason 語彙
    target_poi: Optional[POI] = None
    current_poi_id: Optional[str] = None
    # 固定 tick 滞在の残り (None=時刻ベース退出 / 0=滞在なし)
    dwell_remaining: Optional[int] = None
    # 直前 tick に moving だったか (arrived 判定用 §9.2)
    was_moving: bool = False
    # 当 tick に初期位置=目的地一致で到達扱いになったか (§20.2 項4/項5 / tick=0 限定)
    just_arrived: bool = False
    # 当 tick に出力する status (contract 語彙)
    out_status: str = "staying"
    # WO-009: 道路追従用の残りウェイポイント列 [(lat, lon), ...]
    # 空リスト = 直線補間フォールバック (road graph なし / 到達不能)
    route_waypoints: list[tuple[float, float]] = field(default_factory=list)
    # 当該移動で使った経路種別。移動中/到着 tick の AgentState に optional 出力する。
    route_mode: str = "none"


# ─────────────────────────────────────────────────────────────────────────────
# シミュレーション本体
# ─────────────────────────────────────────────────────────────────────────────

class Simulation:
    """ルールベース都市シミュレーション。

    use: Simulation(pois, profiles, seed=..., ticks=..., run_id=...).run(out_dir)
    """

    def __init__(
        self,
        pois: list[POI],
        profiles: list[AgentProfile],
        *,
        seed: int = 42,
        ticks: int = 24,
        run_id: str = "urban_demo",
        aois: int = 0,
        roads: int = 0,
        road_graph: Optional[RoadGraph] = None,
        activity_plans: Optional[list[ActivityPlan]] = None,
        llm_provider: Optional[Any] = None,
        enable_summaries: bool = True,
        matrix_mode: bool = False,
        matrix_role: str = "sentinel_mvp",
        matrix_agent_id: Optional[int] = None,
        matrix_ttl_ticks: int = 1,
        matrix_trigger_id: str = "assume_sentinel",
        matrix_transition_tick: Optional[int] = None,
        matrix_source_layer: str = "real",
        matrix_target_layer: str = "virtual",
        matrix_evidence_type: str = "matrix_event",
        matrix_evidence_ref: str = "matrix_events.jsonl",
        matrix_guide_tick: Optional[int] = None,
        matrix_guide_layer: str = "real",
        matrix_human_gate_tick: Optional[int] = None,
        matrix_gate_action: str = "public_pr",
        matrix_gate_status: str = "requires_human",
        matrix_gate_reason: str = "operator_agent_human_gate",
        matrix_swarm_heartbeat_tick: Optional[int] = None,
        matrix_swarm_stale_tick: Optional[int] = None,
        matrix_swarm_stale_after_ticks: int = MATRIX_SWARM_STALE_AFTER_TICKS_DEFAULT,
        matrix_swarm_orphan_tolerance: int = MATRIX_SWARM_ORPHAN_TOLERANCE_DEFAULT,
        matrix_swarm_heartbeat_interval_ticks: int = 1,
        matrix_oath_chain_rank: int = 1,
        matrix_sworn_duty: str = "threat_containment",
        matrix_core_instability_level: int = 1,
        matrix_stabilization_phase: str = "precursor",
        matrix_boundary_permeability: int = 0,
        matrix_outside_knowledge_level: int = 0,
        matrix_duel_style: str = "adaptive",
        matrix_duel_rank: int = 0,
    ) -> None:
        """シミュレーション初期化。

        Args:
            pois: POI リスト。
            profiles: エージェントプロフィールリスト。
            seed: 乱数 seed (決定論 §13.3.2)。
            ticks: シミュレーション tick 数。
            run_id: run 識別子。
            aois: AOI 件数 (summary 用)。
            roads: Road 件数 (summary 用)。
            road_graph: RoadGraph インスタンス (WO-009 道路追従 §acceptance 1-5)。
                None の場合は直線補間フォールバックで動作する (後方互換)。
                road_graph を渡すとエージェントが最短経路で道路追従移動する。
            activity_plans: optional activity_plans.jsonl 入力。None の場合は既存
                rule-driven destination selection を維持する (WO-015)。
            llm_provider: LLMProvider インスタンス (spec §10.1)。
                None の場合は RuleBasedProvider を使う (MVP 既定)。
                RuleBasedProvider 経路では決定論が保たれる (byte 一致 §13.3.2)。
            enable_summaries: True (既定) で interaction summary を生成する。
                False にすると summary は空文字になり、LLM 呼び出しをスキップする。
            matrix_mode: True の場合だけ MATRIX Mode Event JSONL を生成する。
                既定 False では `matrix_events.jsonl` を出力しない。
            matrix_role: 公開 alias。保護されたキャラクター名は使わない。
            matrix_agent_id: takeover 対象の既存 agent id。None の場合は最小 id。
            matrix_ttl_ticks: takeover の TTL tick 数。1 以上。
            matrix_trigger_id: 起動 trigger id。公開 UI コピーではなく内部識別子。
            matrix_transition_tick: 指定時だけ `world_transition` を追加する。
            matrix_source_layer: transition 元 layer。
            matrix_target_layer: transition 先 layer。
            matrix_evidence_type: transition の根拠種別。
            matrix_evidence_ref: transition 根拠への短い参照。
            matrix_guide_tick: 指定時だけ `guide_agent` heartbeat を追加する。
            matrix_guide_layer: guide が説明する現在 layer。
            matrix_human_gate_tick: 指定時だけ `operator_agent` human_gate を追加する。
            matrix_gate_action: gate 対象の高リスク action。
            matrix_gate_status: gate 状態。MVP 既定は requires_human。
            matrix_gate_reason: gate 理由。
            matrix_swarm_heartbeat_tick: 指定時だけ `sentinel_swarm` heartbeat を追加する。
            matrix_swarm_stale_tick: 指定時だけ `sentinel_swarm` stale_report を追加する。
            matrix_swarm_stale_after_ticks: stale 判定までの heartbeat 欠落 tick 数。
            matrix_swarm_orphan_tolerance: orphan sentinel の許容数。MVP 既定は 0。
            matrix_swarm_heartbeat_interval_ticks: heartbeat 期待間隔。
            matrix_oath_chain_rank: oath_chain motif (MP-003 / v0.7.1) の命令権限ランク。
                0 が apex (最上位権限)。matrix_mode=True の takeover_start に付与する。
                rng を消費しないため既存の rng 消費順序は不変。
            matrix_sworn_duty: oath_chain motif (MP-003 / v0.7.1) の役割誓約。
                matrix_mode=True の takeover_start に付与する。
                保護されたキャラクター名・外部秘密・個人情報を含めない。
            matrix_core_instability_level: unstable_city_core motif (MP-004 / v0.7.2) の
                都市中枢不安定度。0 が安定基準値。matrix_mode=True かつ
                matrix_swarm_stale_tick 指定時の stale_report に付与する。
                rng を消費しないため既存の rng 消費順序は不変。
            matrix_stabilization_phase: unstable_city_core motif (MP-004 / v0.7.2) の
                崩壊-回復フェーズ。許容値: precursor / collapse / intervention / recovery / stable。
                matrix_mode=True かつ matrix_swarm_stale_tick 指定時の stale_report に付与する。
                保護されたキャラクター名・外部秘密・個人情報を含めない。
            matrix_boundary_permeability: walled_society motif (MP-005 / v0.7.3) の境界透過性。
                0 が完全封鎖。matrix_mode=True かつ matrix_guide_tick 指定時の guide_agent
                heartbeat に付与する。rng を消費しないため既存の rng 消費順序は不変。
            matrix_outside_knowledge_level: walled_society motif (MP-005 / v0.7.3) の
                外部知識蓄積レベル。0 が外部知識なし。matrix_mode=True かつ matrix_guide_tick
                指定時の guide_agent heartbeat に付与する。
                保護されたキャラクター名・外部秘密・個人情報を含めない。
            matrix_duel_style: duel_school motif (MP-006 / v0.7.4) の engagement style。
                人間可読な抽象 style 文字列。matrix_mode=True の takeover_start に付与する。
                保護された流派名・外部秘密・個人情報を含めない。
                rng を消費しないため既存の rng 消費順序は不変。
            matrix_duel_rank: duel_school motif (MP-006 / v0.7.4) の competitive rank。
                0 が未ランク基準。matrix_mode=True の takeover_start に付与する。
                保護された名称・外部秘密・個人情報を含めない。
                rng を消費しないため既存の rng 消費順序は不変。
        """
        if ticks < 1:
            raise ValueError("ticks は 1 以上が必要")
        if not pois:
            raise ValueError("pois は 1 件以上が必要")
        if not profiles:
            raise ValueError("profiles は 1 件以上が必要")
        self.pois = pois
        # agent は id 昇順で固定処理する (決定論)
        self.profiles = sorted(profiles, key=lambda p: p.id)
        self.seed = seed
        self.ticks = ticks
        self.run_id = run_id
        self.aois = aois
        self.roads = roads
        # WO-009: 道路追従グラフ (None = 直線補間フォールバック)
        self.road_graph: Optional[RoadGraph] = road_graph
        self.activity_plan_index: dict[tuple[int, int], tuple[Activity, ...]] = {}
        if activity_plans:
            self.activity_plan_index = {
                (plan.agent_id, plan.day): plan.activities
                for plan in activity_plans
            }

        # LLMProvider: None の場合は遅延生成で RuleBasedProvider を使う
        self._llm_provider: Optional[Any] = llm_provider

        # summary 生成の on/off (#1 会話オプション)
        self._enable_summaries = enable_summaries

        self._poi_by_id: dict[str, POI] = {p.id: p for p in pois}
        self._profile_ids = frozenset(p.id for p in profiles)
        self.rng = random.Random(seed)
        self.matrix_mode = matrix_mode
        self.matrix_role = matrix_role
        self.matrix_agent_id = matrix_agent_id
        self.matrix_ttl_ticks = matrix_ttl_ticks
        self.matrix_trigger_id = matrix_trigger_id
        self.matrix_transition_tick = matrix_transition_tick
        self.matrix_source_layer = matrix_source_layer
        self.matrix_target_layer = matrix_target_layer
        self.matrix_evidence_type = matrix_evidence_type
        self.matrix_evidence_ref = matrix_evidence_ref
        self.matrix_guide_tick = matrix_guide_tick
        self.matrix_guide_layer = matrix_guide_layer
        self.matrix_human_gate_tick = matrix_human_gate_tick
        self.matrix_gate_action = matrix_gate_action
        self.matrix_gate_status = matrix_gate_status
        self.matrix_gate_reason = matrix_gate_reason
        self.matrix_swarm_heartbeat_tick = matrix_swarm_heartbeat_tick
        self.matrix_swarm_stale_tick = matrix_swarm_stale_tick
        self.matrix_swarm_stale_after_ticks = matrix_swarm_stale_after_ticks
        self.matrix_swarm_orphan_tolerance = matrix_swarm_orphan_tolerance
        self.matrix_swarm_heartbeat_interval_ticks = matrix_swarm_heartbeat_interval_ticks
        # MP-003 oath_chain (v0.7.1): takeover_start に付与する命令権限と誓約
        self.matrix_oath_chain_rank = matrix_oath_chain_rank
        self.matrix_sworn_duty = matrix_sworn_duty
        # MP-004 unstable_city_core (v0.7.2): stale_report に付与する不安定度とフェーズ
        self.matrix_core_instability_level = matrix_core_instability_level
        self.matrix_stabilization_phase = matrix_stabilization_phase
        # MP-005 walled_society (v0.7.3): guide_agent heartbeat に付与する境界透過性と外部知識レベル
        self.matrix_boundary_permeability = matrix_boundary_permeability
        self.matrix_outside_knowledge_level = matrix_outside_knowledge_level
        # MP-006 duel_school (v0.7.4): takeover_start に付与する engagement style と competitive rank
        self.matrix_duel_style = matrix_duel_style
        self.matrix_duel_rank = matrix_duel_rank
        if self.matrix_mode:
            self._validate_matrix_config()

        # エージェント id → 表示名 の lookup (#2 苗字)
        # AgentProfile.name (例: "清水優斗") に "さん" を付けて使う。
        # profile は surname+given の連結のみ持つため分割は行わない。
        self._agent_display_name: dict[int, str] = {
            p.id: p.name + "さん" for p in profiles if p.name
        }

        # POI id → 表示名 の lookup (#4 店名)
        # POI.name が None の場合は id をフォールバックとして使う。
        self._poi_display_name: dict[str, str] = {
            p.id: (p.name if p.name else p.id) for p in pois
        }

        # relationship 状態 (key=(min_id, max_id) → {"score", "state"})
        self._rel: dict[tuple[int, int], dict[str, Any]] = {}

        # 出力バッファ
        self.agent_states: list[dict[str, Any]] = []
        self.visit_records: list[dict[str, Any]] = []
        self.interaction_events: list[dict[str, Any]] = []
        self.matrix_events: list[dict[str, Any]] = []

        # bbox (§13.3.3 invariant 用 / 出力には使わない)
        self.bbox = self._compute_bbox(pois, profiles)

    @property
    def llm_provider(self) -> Any:
        """LLMProvider を返す。未設定の場合は RuleBasedProvider を遅延生成する。"""
        if self._llm_provider is None:
            # 遅延 import (RuleBased 経路では SDK 不要)
            from app.llm_provider import RuleBasedProvider
            self._llm_provider = RuleBasedProvider()
        return self._llm_provider

    def _validate_matrix_config(self) -> None:
        """MATRIXモード設定を public alias と既存 agent id に限定する。"""
        if self.matrix_role not in MATRIX_ROLE_VALUES:
            allowed = ", ".join(sorted(MATRIX_ROLE_VALUES))
            raise ValueError(f"matrix_role は {allowed} のいずれかが必要")
        if self.matrix_ttl_ticks < 1:
            raise ValueError("matrix_ttl_ticks は 1 以上が必要")
        if self.matrix_agent_id is not None and self.matrix_agent_id not in self._profile_ids:
            raise ValueError(f"matrix_agent_id が profiles に存在しません: {self.matrix_agent_id}")
        if self.matrix_transition_tick is not None:
            if self.matrix_transition_tick < 0 or self.matrix_transition_tick >= self.ticks:
                raise ValueError("matrix_transition_tick は 0 以上 ticks 未満が必要")
            if self.matrix_source_layer not in WORLD_LAYER_VALUES:
                raise ValueError(f"matrix_source_layer が不正です: {self.matrix_source_layer}")
            if self.matrix_target_layer not in WORLD_LAYER_VALUES:
                raise ValueError(f"matrix_target_layer が不正です: {self.matrix_target_layer}")
            if self.matrix_source_layer == self.matrix_target_layer:
                raise ValueError("matrix_source_layer と matrix_target_layer は異なる必要があります")
            source_model = WORLD_LAYER_MODEL[self.matrix_source_layer]
            if self.matrix_target_layer not in source_model["exit_layers"]:
                raise ValueError(
                    f"matrix_target_layer は {self.matrix_source_layer} から遷移できません: "
                    f"{self.matrix_target_layer}"
                )
            target_model = WORLD_LAYER_MODEL[self.matrix_target_layer]
            if self.matrix_evidence_type not in MATRIX_EVIDENCE_TYPE_VALUES:
                raise ValueError(f"matrix_evidence_type が不正です: {self.matrix_evidence_type}")
            if self.matrix_evidence_type not in target_model["evidence_types"]:
                raise ValueError(
                    f"matrix_evidence_type は {self.matrix_target_layer} の evidence ではありません: "
                    f"{self.matrix_evidence_type}"
                )
        if self.matrix_guide_tick is not None:
            if self.matrix_guide_tick < 0 or self.matrix_guide_tick >= self.ticks:
                raise ValueError("matrix_guide_tick は 0 以上 ticks 未満が必要")
            if self.matrix_guide_layer not in WORLD_LAYER_VALUES:
                raise ValueError(f"matrix_guide_layer が不正です: {self.matrix_guide_layer}")
        if self.matrix_human_gate_tick is not None:
            if self.matrix_human_gate_tick < 0 or self.matrix_human_gate_tick >= self.ticks:
                raise ValueError("matrix_human_gate_tick は 0 以上 ticks 未満が必要")
            if self.matrix_gate_action not in MATRIX_HUMAN_GATE_ACTION_VALUES:
                raise ValueError(f"matrix_gate_action が不正です: {self.matrix_gate_action}")
            if self.matrix_gate_status not in MATRIX_HUMAN_GATE_STATUS_VALUES:
                raise ValueError(f"matrix_gate_status が不正です: {self.matrix_gate_status}")
        if self.matrix_oath_chain_rank < 0:
            raise ValueError("matrix_oath_chain_rank は 0 以上が必要")
        if self.matrix_core_instability_level < 0:
            raise ValueError("matrix_core_instability_level は 0 以上が必要")
        if self.matrix_boundary_permeability < 0:
            raise ValueError("matrix_boundary_permeability は 0 以上が必要")
        if self.matrix_outside_knowledge_level < 0:
            raise ValueError("matrix_outside_knowledge_level は 0 以上が必要")
        if self.matrix_duel_rank < 0:
            raise ValueError("matrix_duel_rank は 0 以上が必要")
        if self.matrix_stabilization_phase not in MATRIX_STABILIZATION_PHASE_VALUES:
            allowed = ", ".join(sorted(MATRIX_STABILIZATION_PHASE_VALUES))
            raise ValueError(
                f"matrix_stabilization_phase は {allowed} のいずれかが必要"
            )
        if self.matrix_swarm_stale_after_ticks < 1:
            raise ValueError("matrix_swarm_stale_after_ticks は 1 以上が必要")
        if self.matrix_swarm_orphan_tolerance < 0:
            raise ValueError("matrix_swarm_orphan_tolerance は 0 以上が必要")
        if self.matrix_swarm_heartbeat_interval_ticks < 1:
            raise ValueError("matrix_swarm_heartbeat_interval_ticks は 1 以上が必要")
        if self.matrix_swarm_heartbeat_tick is not None:
            if self.matrix_swarm_heartbeat_tick < 0 or self.matrix_swarm_heartbeat_tick >= self.ticks:
                raise ValueError("matrix_swarm_heartbeat_tick は 0 以上 ticks 未満が必要")
        if self.matrix_swarm_stale_tick is not None:
            if self.matrix_swarm_stale_tick < 0 or self.matrix_swarm_stale_tick >= self.ticks:
                raise ValueError("matrix_swarm_stale_tick は 0 以上 ticks 未満が必要")
            last_heartbeat_tick = self._matrix_swarm_last_heartbeat_tick()
            stale_ready_tick = last_heartbeat_tick + self.matrix_swarm_stale_after_ticks
            if self.matrix_swarm_stale_tick < stale_ready_tick:
                raise ValueError(
                    "matrix_swarm_stale_tick は last heartbeat から "
                    "matrix_swarm_stale_after_ticks 以上後が必要"
                )

    # ── 初期化補助 ──────────────────────────────────────────────────────────

    @staticmethod
    def _compute_bbox(
        pois: list[POI], profiles: list[AgentProfile]
    ) -> dict[str, float]:
        lats = [p.lat for p in pois] + [a.initial_lat for a in profiles]
        lons = [p.lon for p in pois] + [a.initial_lon for a in profiles]
        return {
            "lat_min": min(lats), "lat_max": max(lats),
            "lon_min": min(lons), "lon_max": max(lons),
        }

    def _resolve_fixed_poi(
        self, agent: _AgentRuntime, poi_id: Optional[str]
    ) -> Optional[POI]:
        """固定 POI id を解決する。無ければ initial_position 最近傍で代替 (§9.3 注記)。"""
        if poi_id is not None and poi_id in self._poi_by_id:
            return self._poi_by_id[poi_id]
        # initial_position 最近傍で代替
        return rules.nearest_poi(
            agent.profile.initial_lat, agent.profile.initial_lon, self.pois
        )

    # ── 目的地解決 (rng 消費は本メソッド内で完結) ──────────────────────────

    def _build_destination_context(
        self,
        agent: _AgentRuntime,
        tick: int,
        poi_presence: Optional[dict[str, set[int]]] = None,
    ) -> dict:
        """§10.3 コンテキスト dict を組む (choose_destination_category 用)。

        WO-008: occupation / personality / hobbies / day_pattern / current_time を
        context に含める (acceptance criterion 1)。
        各フィールドは AgentProfile (WO-006 追加) から取得し、存在する場合のみ注入する。

        §10.3 gap 修正: nearby_pois / nearby_agents / recent_interactions / agent_profile
        の 4 フィールドを追加注入する。
          - nearby_pois: エージェント座標から近い順に最大 NEIGHBOR_K 件の POI ID リスト。
          - nearby_agents: 同 POI に滞在/向かっている他エージェント ID リスト
                          (poi_presence が渡された場合のみ)。
          - recent_interactions: self.interaction_events からこのエージェントが
                                 関与した直近 5 件 (tick 降順)。
          - agent_profile: プロフィールの主要フィールドを dict 化したもの。
        """
        day, time_str = tick_to_day_time(tick)
        ctx: dict = {
            "agent_id": agent.profile.id,
            "role": agent.profile.role,
            "current_time": time_str,
        }
        # WO-008: WO-006 プロフィール拡張フィールドを注入する
        if agent.profile.occupation:
            ctx["occupation"] = agent.profile.occupation
        if agent.profile.personality:
            ctx["personality"] = agent.profile.personality
        if agent.profile.hobbies:
            ctx["hobbies"] = list(agent.profile.hobbies)
        if agent.profile.day_pattern:
            ctx["day_pattern"] = agent.profile.day_pattern
        if agent.current_poi_id:
            ctx["current_location"] = agent.current_poi_id

        # §10.3 gap: nearby_pois — エージェント座標からの最近傍 NEIGHBOR_K 件
        sorted_pois = sorted(
            self.pois,
            key=lambda p: rules.haversine_m(agent.lat, agent.lon, p.lat, p.lon),
        )
        ctx["nearby_pois"] = [p.id for p in sorted_pois[: rules.NEIGHBOR_K]]

        # §10.3 gap: nearby_agents — 同 POI に居る他エージェント (poi_presence 利用)
        nearby_agent_ids: list[int] = []
        if poi_presence is not None and agent.current_poi_id:
            co_present = poi_presence.get(agent.current_poi_id, set())
            nearby_agent_ids = sorted(
                aid for aid in co_present if aid != agent.profile.id
            )
        ctx["nearby_agents"] = nearby_agent_ids

        # §10.3 gap: recent_interactions — このエージェントが関与した直近 5 件
        agent_id = agent.profile.id
        recent: list[dict[str, Any]] = [
            ev for ev in self.interaction_events
            if agent_id in ev.get("agent_ids", [])
        ]
        # tick 降順で上位 5 件 (immutable コピーを渡す)
        recent_sorted = sorted(recent, key=lambda ev: ev.get("tick", 0), reverse=True)
        ctx["recent_interactions"] = [dict(ev) for ev in recent_sorted[:5]]

        # §10.3 gap: agent_profile — プロフィール主要フィールドの dict
        profile = agent.profile
        agent_profile: dict[str, Any] = {"id": profile.id}
        if profile.name:
            agent_profile["name"] = profile.name
        if profile.age is not None:
            agent_profile["age"] = profile.age
        if profile.gender:
            agent_profile["gender"] = profile.gender
        if profile.occupation:
            agent_profile["occupation"] = profile.occupation
        if profile.personality:
            agent_profile["personality"] = profile.personality
        if profile.hobbies:
            agent_profile["hobbies"] = list(profile.hobbies)
        if profile.day_pattern:
            agent_profile["day_pattern"] = profile.day_pattern
        ctx["agent_profile"] = agent_profile

        return ctx

    def _llm_narrow_candidates(
        self,
        agent: _AgentRuntime,
        tick: int,
        cands: list[POI],
        poi_presence: Optional[dict[str, set[int]]] = None,
    ) -> list[POI]:
        """LLMProvider で候補 POI を 1 カテゴリに絞り込む。

        RuleBasedProvider は "" を返すため候補は変化しない (決定論維持 §13.3.2)。
        VertexGeminiProvider が有効カテゴリを返した場合のみ絞り込む。
        不正カテゴリ/例外は §9.3 ルール (cands 全体) にフォールバックし、
        fallback を debug ログに記録する (プロンプト本文は出力しない)。

        poi_presence: §10.3 nearby_agents 計算用 (None の場合は nearby_agents = [])。
        """
        if not cands:
            return cands

        # 候補の distinct カテゴリリストを allowed_categories として渡す
        allowed = sorted({p.category for p in cands})
        ctx = self._build_destination_context(agent, tick, poi_presence=poi_presence)

        try:
            chosen = self.llm_provider.choose_destination_category(ctx, allowed)
        except Exception:
            import logging
            logging.getLogger(__name__).debug(
                "choose_destination_category で例外 — §9.3 fallback (agent_id=%d)",
                agent.profile.id,
            )
            return cands

        if not chosen or chosen not in allowed:
            if chosen:
                import logging
                logging.getLogger(__name__).debug(
                    "不正カテゴリ %r — §9.3 fallback (agent_id=%d)",
                    chosen,
                    agent.profile.id,
                )
            return cands  # フォールバック: §9.3 のまま

        # 有効カテゴリで絞り込む
        narrowed = [p for p in cands if p.category == chosen]
        return narrowed if narrowed else cands  # 候補が空になったらフォールバック

    def _choose_destination(
        self,
        agent: _AgentRuntime,
        tick: int,
        poi_presence: dict[str, set[int]],
    ) -> tuple[Optional[POI], str, str]:
        """§9.3 テーブルから (target_poi, action, mode) を返す。

        rng 消費は weighted/social/wander モードのみ (docstring の消費順序参照)。
        target_poi が None で action="no_target" の場合は候補なし (§9.4 項5)。

        spec §10.2 配線:
          nearest/weighted/social モードでは _llm_narrow_candidates を経由し、
          LLMProvider.choose_destination_category() でカテゴリを絞り込む。
          RuleBasedProvider は "" を返すため候補は変化せず決定論が維持される。
          VertexGeminiProvider が不正/例外時も §9.3 ルールにフォールバックする。
        """
        activity_choice = self._choose_activity_destination(agent, tick, poi_presence)
        if activity_choice is not None:
            return activity_choice

        minutes = rules.minutes_of_tick(tick)
        mode, vocab, reason = rules.schedule_decision(minutes, agent.profile.role)

        if mode == "fixed_work":
            poi = self._resolve_fixed_poi(agent, agent.profile.work_or_school_poi_id)
            return (poi, reason, mode)

        if mode == "fixed_home":
            poi = self._resolve_fixed_poi(agent, agent.profile.home_poi_id)
            return (poi, reason, mode)

        if mode == "stay_current":
            # 移動なし: 現 POI 滞在 (target は現在地 POI / None でも可)
            cur = self._poi_by_id.get(agent.current_poi_id) if agent.current_poi_id else None
            return (cur, reason, mode)

        if mode == "nearest":
            cands = [p for p in self.pois if rules.category_matches(p.category, vocab)]
            # LLM カテゴリ絞り込み (RuleBased は no-op)
            cands = self._llm_narrow_candidates(agent, tick, cands, poi_presence=poi_presence)
            poi = rules.nearest_poi(agent.lat, agent.lon, cands)
            if poi is None:
                return (None, "no_target", mode)
            return (poi, reason, mode)

        if mode == "weighted":
            cands = [p for p in self.pois if rules.category_matches(p.category, vocab)]
            # LLM カテゴリ絞り込み (RuleBased は no-op)
            cands = self._llm_narrow_candidates(agent, tick, cands, poi_presence=poi_presence)
            poi = rules.weighted_nearest_poi(agent.lat, agent.lon, cands, self.rng)
            if poi is None:
                return (None, "no_target", mode)
            return (poi, reason, mode)

        if mode == "social":
            cands = [p for p in self.pois if rules.category_matches(p.category, vocab)]
            # LLM カテゴリ絞り込み (RuleBased は no-op)
            cands = self._llm_narrow_candidates(agent, tick, cands, poi_presence=poi_presence)
            # §9.10: social_networks メンバーが滞在/向かっている POI を FRIEND_GRAVITY 倍
            friend_pois = self._friend_target_pois(agent, poi_presence)

            def _wf(poi: POI, base: float) -> float:
                return base * rules.FRIEND_GRAVITY if poi.id in friend_pois else base

            poi = rules.weighted_nearest_poi(agent.lat, agent.lon, cands, self.rng, _wf)
            if poi is None:
                return (None, "no_target", mode)
            return (poi, reason, mode)

        # mode == "wander": 確率 0.3 で近傍へ / 0.7 で現地滞在
        if self.rng.random() < 0.3:
            poi = rules.weighted_nearest_poi(agent.lat, agent.lon, self.pois, self.rng)
            if poi is None:
                return (None, "no_target", mode)
            return (poi, "wander", mode)
        # 現地滞在
        return (None, "wander", "wander_stay")

    def _choose_activity_destination(
        self,
        agent: _AgentRuntime,
        tick: int,
        poi_presence: dict[str, set[int]],
    ) -> Optional[tuple[Optional[POI], str, str]]:
        """activity_plans.jsonl の active activity から目的地を返す (WO-015)。

        plan が無い agent/day/tick では None を返し、既存 §9.3 ルールへ委譲する。
        poi_id がある activity は固定目的地、category のみの activity は既存の
        カテゴリ候補抽出 + LLM 絞り込み + 最近傍選択へ委譲する。
        """
        day, time_str = tick_to_day_time(tick)
        activities = self.activity_plan_index.get((agent.profile.id, day))
        if not activities:
            return None
        minutes = _time_to_minutes(time_str)
        active = next(
            (
                activity for activity in activities
                if _time_to_minutes(activity.start) <= minutes < _time_to_minutes(activity.end)
            ),
            None,
        )
        if active is None:
            return None

        action = _activity_kind_to_action(active.kind)
        if active.poi_id:
            return (self._poi_by_id.get(active.poi_id), action, "activity_fixed")
        if active.category:
            cands = [p for p in self.pois if p.category == active.category]
            cands = self._llm_narrow_candidates(agent, tick, cands, poi_presence=poi_presence)
            poi = rules.nearest_poi(agent.lat, agent.lon, cands)
            if poi is None:
                return (None, "no_target", "activity_category")
            return (poi, action, "activity_category")
        if active.kind == "home":
            return (self._resolve_fixed_poi(agent, agent.profile.home_poi_id), action, "activity_home")
        if active.kind in ("work", "study"):
            return (self._resolve_fixed_poi(agent, agent.profile.work_or_school_poi_id), action, "activity_routine")
        return (None, action, "activity_stay")

    def _friend_target_pois(
        self,
        agent: _AgentRuntime,
        poi_presence: dict[str, set[int]],
    ) -> set[str]:
        """social_networks メンバーが滞在/目的地としている POI 集合を返す (§9.10)。"""
        net = set(agent.profile.social_networks)
        if not net:
            return set()
        result: set[str] = set()
        for poi_id, agents_here in poi_presence.items():
            if net & agents_here:
                result.add(poi_id)
        return result

    # ── tick 処理 ───────────────────────────────────────────────────────────

    def _build_poi_presence(
        self, runtimes: list[_AgentRuntime]
    ) -> dict[str, set[int]]:
        """POI → 滞在/向かっているエージェント id 集合の逆引き index を作る (§9.10)。"""
        presence: dict[str, set[int]] = {}
        for rt in runtimes:
            poi_id = None
            if rt.internal == "at_poi" and rt.current_poi_id:
                poi_id = rt.current_poi_id
            elif rt.internal == "moving" and rt.target_poi is not None:
                poi_id = rt.target_poi.id
            if poi_id is not None:
                presence.setdefault(poi_id, set()).add(rt.profile.id)
        return presence

    def _step_agent(
        self,
        agent: _AgentRuntime,
        tick: int,
        poi_presence: dict[str, set[int]],
    ) -> Optional[dict[str, Any]]:
        """1 体の 1 tick を処理し、必要なら visit record dict を返す。"""
        visit: Optional[dict[str, Any]] = None
        prev_internal = agent.internal
        agent.was_moving = prev_internal == "moving"
        agent.just_arrived = False  # §20.2 項4: 当 tick の到達フラグは毎 tick リセット

        # ── 再評価契機判定 (§20.5): idle / 滞在消化済み のみ §9.3 を引く ──
        need_reevaluate = False
        if agent.internal == "idle":
            need_reevaluate = True
        elif agent.internal == "at_poi":
            if agent.dwell_remaining is None:
                # 時刻ベース退出 (commute→work=18:00 / go_home=翌08:00)
                need_reevaluate = self._time_based_exit_due(agent, tick)
            elif agent.dwell_remaining <= 0:
                need_reevaluate = True
            else:
                agent.dwell_remaining -= 1
                need_reevaluate = agent.dwell_remaining <= 0

        if need_reevaluate:
            target, action, mode = self._choose_destination(agent, tick, poi_presence)
            agent.action = action
            agent.target_poi = target
            if target is None:
                # no_target または wander_stay: 現地滞在 (§9.4 項5 / §20.4)
                agent.internal = "idle"
                agent.dwell_remaining = 0
                agent.route_waypoints = []
                agent.route_mode = "none"
            elif target.id == agent.current_poi_id and self._at_poi_coords(agent, target):
                # 既に目的地 POI に居る (stay_current / 初期位置一致): 移動せず滞在
                agent.internal = "at_poi"
                agent.route_waypoints = []
                agent.route_mode = "none"
                if tick == 0:
                    # §20.2 項4/項5: tick=0 で初期位置=目的地 POI に一致 → 「到達」扱い。
                    # arrived を出力し、visit record を 1 行出力する (移動開始は記録しない §9.5)。
                    agent.just_arrived = True
                    visit = self._make_visit(agent, tick)
                    # §20.1 項2 と整合: commute 即着なら work/study に切替 (dwell は時刻ベース None)。
                    if agent.action == "commute":
                        agent.action = "study" if agent.profile.role == "student" else "work"
                # 非 tick=0 / 非 commute は action 不変のため dwell の rng 消費順は従来と一致。
                agent.dwell_remaining = self._dwell_for(agent.action)
            else:
                agent.internal = "moving"
                # WO-009: 道路追従ルートを計算して waypoints に格納する。
                # road_graph がない場合は空リスト → 既存の直線補間フォールバック。
                agent.route_waypoints, agent.route_mode = self._compute_route(
                    agent.lat, agent.lon, target.lat, target.lon
                )

        # ── 移動処理 (§9.5 / WO-009 道路追従) ──
        if agent.internal == "moving" and agent.target_poi is not None:
            if agent.route_waypoints:
                # WO-009: waypoints チェーンに沿って STEP_M 前進する。
                new_lat, new_lon, arrived = self._step_along_route(agent)
            else:
                # 直線補間フォールバック (road_graph なし / 到達不能)
                new_lat, new_lon, arrived = rules.step_towards(
                    agent.lat, agent.lon, agent.target_poi.lat, agent.target_poi.lon
                )
            agent.lat, agent.lon = new_lat, new_lon
            if arrived:
                agent.internal = "at_poi"
                agent.current_poi_id = agent.target_poi.id
                agent.route_waypoints = []
                # 到達 tick に visit record を 1 行出力 (§9.5 / §20.2 項5)。
                # reason は移動時の §9.3 reason (commute 等) をそのまま記録する。
                visit = self._make_visit(agent, tick)
                # §20.1 項2: commute 到達後は即 work/study 開始 (18:00 まで滞在)。
                # action を職場滞在の reason に切り替える。dwell は時刻ベース (None)。
                if agent.action == "commute":
                    agent.action = "study" if agent.profile.role == "student" else "work"
                agent.dwell_remaining = self._dwell_for(agent.action)

        # ── 出力 status 写像 (§9.2) ──
        agent.out_status = self._map_status(agent, prev_internal)
        return visit

    def _at_poi_coords(self, agent: _AgentRuntime, poi: POI) -> bool:
        """agent が POI 座標とほぼ一致しているか (到達済み判定)。"""
        return rules.haversine_m(agent.lat, agent.lon, poi.lat, poi.lon) <= rules.STEP_M

    # ── WO-009 道路追従 ──────────────────────────────────────────────────────

    def _compute_route(
        self,
        src_lat: float,
        src_lon: float,
        dst_lat: float,
        dst_lon: float,
    ) -> tuple[list[tuple[float, float]], str]:
        """road_graph で src → dst のウェイポイント列と route_mode を返す。

        road_graph がない場合は ([], "linear_fallback") を返す。
        到達不能の場合も直線 fallback として返す (RoadGraph.route は [(dst_lat, dst_lon)] を返すが、
        それは dst スナップなので最終目的地 = dst_lat/dst_lon と同等 → 直線で十分)。

        ウェイポイントは「まだ向かうべき残り点列」。先頭から順に消費する。
        最終要素に近づいたら到達判定を行う。
        """
        if self.road_graph is None or self.road_graph.is_empty():
            return [], "linear_fallback"
        waypoints = self.road_graph.route(src_lat, src_lon, dst_lat, dst_lon)
        # フォールバック (グラフ空 / 到達不能): [(dst_lat, dst_lon)] を 1 要素で返すが
        # そのまま使うと「waypoints がある」と判定されてしまう。
        # 到達不能は直線フォールバックに委ねるため空リストを返す。
        # ただし到達可能 (>=2 ノード) のみ道路追従を使う。
        if len(waypoints) <= 1:
            # 1 要素 = 直線フォールバック (到達不能) または同一ノード
            return [], "linear_fallback"
        return list(waypoints), "roadnet"

    def _step_along_route(
        self,
        agent: _AgentRuntime,
    ) -> tuple[float, float, bool]:
        """route_waypoints に沿って STEP_M 前進し、新座標と到達フラグを返す。

        毎 tick STEP_M m ずつ waypoints を消費する。
        最終 waypoint (= dst スナップ点) に近づいたら実際の目的地にスナップし
        arrived=True を返す。

        waypoints が尽きた場合は target_poi 座標への直線補間にフォールバックする。
        これはウェイポイント列計算後に target が変わることがないため理論上起きないが、
        防御的に実装しておく。
        """
        assert agent.target_poi is not None
        remaining_budget = rules.STEP_M
        lat, lon = agent.lat, agent.lon

        while remaining_budget > 0 and agent.route_waypoints:
            wp_lat, wp_lon = agent.route_waypoints[0]
            d = rules.haversine_m(lat, lon, wp_lat, wp_lon)

            if d <= remaining_budget:
                # このウェイポイントは今 tick で通り越せる
                remaining_budget -= d
                lat, lon = wp_lat, wp_lon
                agent.route_waypoints.pop(0)
            else:
                # このウェイポイントには今 tick で到達しない: 途中まで進む
                fraction = remaining_budget / d
                lat = lat + (wp_lat - lat) * fraction
                lon = lon + (wp_lon - lon) * fraction
                remaining_budget = 0

        # 全ウェイポイントを消費 → 実際の目的地 (POI 座標) にスナップ
        if not agent.route_waypoints:
            dst_lat = agent.target_poi.lat
            dst_lon = agent.target_poi.lon
            d_final = rules.haversine_m(lat, lon, dst_lat, dst_lon)
            if d_final <= remaining_budget + 1e-9:
                return (dst_lat, dst_lon, True)
            # まだ目的地まで距離がある場合は直線でもう一歩
            if d_final > 0:
                fraction = min(1.0, remaining_budget / d_final) if remaining_budget > 0 else 0.0
                lat = lat + (dst_lat - lat) * fraction
                lon = lon + (dst_lon - lon) * fraction
            # 残り距離が STEP_M 以下なら到達
            d_now = rules.haversine_m(lat, lon, dst_lat, dst_lon)
            if d_now <= 1e-6:
                return (dst_lat, dst_lon, True)
            return (lat, lon, False)

        return (lat, lon, False)

    def _time_based_exit_due(self, agent: _AgentRuntime, tick: int) -> bool:
        """時刻ベース滞在の退出時刻に達したか判定する (§9.6 / §20.5)。

        work/study (commute 到達後) は 18:00 (tick_in_day=120) で退出。
        go_home は翌 08:00 (= 当日終端) で退出。
        """
        minutes = rules.minutes_of_tick(tick)
        if agent.action in ("work", "study", "commute"):
            return minutes >= 18 * 60
        if agent.action == "go_home":
            # 当日内 tick が 0 (= 翌 08:00 相当) に戻ったら退出。
            # MVP 受け入れ (ticks<=192) では到達しないことが多いが堅牢に判定する。
            return rules.tick_in_day(tick) == 0 and tick > 0
        return False

    def _dwell_for(self, action: str) -> Optional[int]:
        """action から滞在 tick を決める (rng 消費は dwell_ticks 内 §9.6)。"""
        return rules.dwell_ticks(action, self.rng)

    def _map_status(self, agent: _AgentRuntime, prev_internal: str) -> str:
        """内部状態を contract status 語彙へ写像する (§9.2)。"""
        if agent.internal == "moving":
            return "moving"
        if agent.internal == "at_poi":
            # 直前 tick が moving で当 tick にスナップ → arrived。
            # tick=0 初期位置=目的地一致 (just_arrived) も arrived (§20.2 項4)。
            if prev_internal == "moving" or agent.just_arrived:
                return "arrived"
            return "staying"
        # idle → staying
        return "staying"

    def _make_visit(self, agent: _AgentRuntime, tick: int) -> dict[str, Any]:
        """到達 tick の visit record dict を作る (§9.5)。"""
        day, time_str = tick_to_day_time(tick)
        rec: dict[str, Any] = {
            "agent_id": agent.profile.id,
            "day": day,
            "time": time_str,
            "poi_id": agent.current_poi_id,
            "action": "visit",
            "reason": agent.action,
            "lat": agent.lat,
            "lon": agent.lon,
        }
        return rec

    # ── interaction 処理 (§9.7 / §9.8 / §20.3) ──────────────────────────────

    def _process_interactions(
        self, runtimes: list[_AgentRuntime], tick: int
    ) -> list[dict[str, Any]]:
        """近接ペアを bucket 化して検出し interaction を生成する (§9.7 / §9.8)。"""
        # §9.7: status が at_poi のエージェントを current_poi_id で bucket 化
        buckets: dict[str, list[_AgentRuntime]] = {}
        for rt in runtimes:
            if rt.internal == "at_poi" and rt.current_poi_id:
                buckets.setdefault(rt.current_poi_id, []).append(rt)

        # 候補ペア (近接 + 抽選で発生) を収集してから §20.3 で上位 50 件に絞る
        candidates: list[dict[str, Any]] = []
        for poi_id, members in buckets.items():
            if len(members) < 2:
                continue
            # bucket 内ペアのみ Haversine 判定 (全ペア O(N^2) 回避 §9.7)
            members_sorted = sorted(members, key=lambda r: r.profile.id)
            n = len(members_sorted)
            for i in range(n):
                for j in range(i + 1, n):
                    a = members_sorted[i]
                    b = members_sorted[j]
                    d = rules.haversine_m(a.lat, a.lon, b.lat, b.lon)
                    if d > rules.PROXIMITY_M:
                        continue
                    pair = self._eval_pair(a, b, poi_id, tick, d)
                    if pair is not None:
                        candidates.append(pair)

        if not candidates:
            return []

        # §20.3: 上限超過時の選別 (social ペア → 距離近い順 → seeded_rand 昇順)
        selected = self._select_top_interactions(candidates)

        # 選別された候補のみ score 更新 + event 生成 (§20.3: 破棄分は score 更新しない)
        events: list[dict[str, Any]] = []
        for c in selected:
            events.append(self._commit_interaction(c, tick))
        return events

    def _eval_pair(
        self,
        a: _AgentRuntime,
        b: _AgentRuntime,
        poi_id: str,
        tick: int,
        dist: float,
    ) -> Optional[dict[str, Any]]:
        """ペア (a,b) の発生判定を行い、発生するなら候補 dict を返す (§9.8.1)。"""
        a_id, b_id = sorted((a.profile.id, b.profile.id))
        in_net = rules.is_in_network(a.profile, b.profile)
        p = rules.interaction_probability(self.seed, tick, a_id, b_id, in_net)
        draw = rules.seeded_rand(self.seed, tick, a_id, b_id, salt="occur")
        if draw >= p:
            return None
        return {
            "a_id": a_id,
            "b_id": b_id,
            "poi_id": poi_id,
            "dist": dist,
            "in_net": in_net,
            "type_draw": rules.seeded_rand(self.seed, tick, a_id, b_id, salt="type"),
            "rank_draw": rules.seeded_rand(self.seed, tick, a_id, b_id, salt="rank"),
        }

    def _select_top_interactions(
        self, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """§20.3 の優先順位で上位 MAX_INTERACTIONS_PER_TICK 件を返す。"""
        if len(candidates) <= rules.MAX_INTERACTIONS_PER_TICK:
            # 出力順は決定論のため (a_id, b_id) 昇順に整える
            return sorted(candidates, key=lambda c: (c["a_id"], c["b_id"]))
        # 優先順位: social ペア優先 → 距離近い順 → seeded_rand 昇順
        ranked = sorted(
            candidates,
            key=lambda c: (
                0 if c["in_net"] else 1,
                c["dist"],
                c["rank_draw"],
                c["a_id"],
                c["b_id"],
            ),
        )
        top = ranked[: rules.MAX_INTERACTIONS_PER_TICK]
        return sorted(top, key=lambda c: (c["a_id"], c["b_id"]))

    def _pair_rel(self, a_id: int, b_id: int, in_net: bool) -> dict[str, Any]:
        """ペアの relationship 状態を取得/初期化する (§9.9)。"""
        key = (a_id, b_id)
        if key not in self._rel:
            score = rules.initial_pair_score(in_net)
            self._rel[key] = {"score": score, "state": rules.state_from_score(score)}
        return self._rel[key]

    def _commit_interaction(
        self, cand: dict[str, Any], tick: int
    ) -> dict[str, Any]:
        """候補から type 決定 + score 更新 + event dict 生成 (§9.8.2 / §9.9)。

        summary は LLMProvider.complete() 経由で生成する (spec §10.2)。
        RuleBasedProvider 経路では _summary_text と同一のテンプレ文が返り、
        決定論 byte 一致 (§13.3.2) が保たれる。
        """
        a_id = cand["a_id"]
        b_id = cand["b_id"]
        rel = self._pair_rel(a_id, b_id, cand["in_net"])
        from_state = rel["state"]
        ev_type = rules.pick_interaction_type(from_state, cand["type_draw"])

        # §9.9: score 増減 → state 再計算
        rel["score"] += rules.SCORE_DELTA[ev_type]
        to_state = rules.state_from_score(rel["score"])
        rel["state"] = to_state

        day, time_str = tick_to_day_time(tick)

        # LLMProvider 経由で summary を生成 (§10.2 / spec §10.1)
        summary = self._generate_summary(ev_type, a_id, b_id, cand["poi_id"], from_state)

        event: dict = {
            "tick": tick,
            "day": day,
            "time": time_str,
            "type": ev_type,
            "agent_ids": [a_id, b_id],
            "location_poi_id": cand["poi_id"],
            "summary": summary,
            "relationship_delta": {"from": from_state, "to": to_state},
        }

        # WO-008: relationship 変化時に理由文を生成して格納する (acceptance criterion 2)
        # from_state != to_state の場合のみ生成する。
        # RuleBasedProvider は決定論テンプレ文を返す (§13.3.2 byte 一致維持)。
        # WO-012 (data-contract v0.4.0): 空文字の場合はキーを出力しない。
        # enable_summaries=False では理由文が "" になるため、契約に従い格納しない。
        if from_state != to_state:
            reason = self._generate_relationship_reason(
                ev_type, a_id, b_id, cand["poi_id"], from_state, to_state
            )
            if reason:
                event["relationship_reason"] = reason

        return event

    def _generate_summary(
        self,
        ev_type: str,
        a_id: int,
        b_id: int,
        poi_id: str,
        relationship_state: str,
    ) -> str:
        """LLMProvider 経由で interaction summary を生成する (spec §10.2)。

        enable_summaries=False の場合は空文字を返す (#1 会話オプション)。
        RuleBasedProvider 経路ではテンプレ文が返り、決定論が保たれる (§13.3.2)。
        VertexGeminiProvider では Gemini が自然言語要約を返す (後段 M5)。

        エージェントは profile.name に "さん" を付けた表示名を使う (#2 苗字)。
        POI は properties.name があれば実名、なければ id を使う (#4 店名)。
        """
        if not self._enable_summaries:
            return ""

        from app.llm_provider import build_prompt
        # #2 苗字: エージェント表示名を lookup (未登録は "エージェント {id}" へフォールバック)
        a_name = self._agent_display_name.get(a_id, f"エージェント {a_id}")
        b_name = self._agent_display_name.get(b_id, f"エージェント {b_id}")
        # #4 店名: POI 実名を lookup (未登録は poi_id へフォールバック)
        poi_name = self._poi_display_name.get(poi_id, poi_id)

        prompt = build_prompt(
            prompt_type="summary",
            agent_a_id=a_id,
            agent_b_id=b_id,
            event_type=ev_type,
            location_poi_id=poi_id,
            agent_a_name=a_name,
            agent_b_name=b_name,
            poi_name=poi_name,
            relationship_state=relationship_state,
        )
        return self.llm_provider.complete(prompt)

    def _generate_relationship_reason(
        self,
        ev_type: str,
        a_id: int,
        b_id: int,
        poi_id: str,
        from_state: str,
        to_state: str,
    ) -> str:
        """LLMProvider 経由で relationship 変化理由文を生成する (WO-008 §10.2)。

        enable_summaries=False の場合は空文字を返す (summary と同じオプション)。
        RuleBasedProvider 経路ではテンプレ文が返り、決定論が保たれる (§13.3.2)。
        VertexGeminiProvider では Gemini が自然言語理由文を返す。

        Args:
            ev_type: interaction type (meeting / conversation / conflict / farewell)。
            a_id: エージェント A の ID。
            b_id: エージェント B の ID。
            poi_id: 発生場所の POI ID。
            from_state: 変化前の relationship state。
            to_state: 変化後の relationship state。

        Returns:
            理由文テキスト (末尾改行なし)。
        """
        if not self._enable_summaries:
            return ""

        from app.llm_provider import build_prompt
        # 表示名 lookup (summary と同じ方式)
        a_name = self._agent_display_name.get(a_id, f"エージェント {a_id}")
        b_name = self._agent_display_name.get(b_id, f"エージェント {b_id}")
        poi_name = self._poi_display_name.get(poi_id, poi_id)

        prompt = build_prompt(
            prompt_type="relationship_reason",
            agent_a_id=a_id,
            agent_b_id=b_id,
            event_type=ev_type,
            location_poi_id=poi_id,
            agent_a_name=a_name,
            agent_b_name=b_name,
            poi_name=poi_name,
            relationship_state=from_state,
            relationship_to=to_state,
        )
        try:
            return self.llm_provider.complete(prompt)
        except Exception:
            import logging
            logging.getLogger(__name__).debug(
                "relationship_reason 生成で例外 — §9.3 fallback テンプレ使用 (agent_a=%d, agent_b=%d)",
                a_id,
                b_id,
            )
            # fallback: テンプレ文を直接返す
            return self._relationship_reason_text(
                ev_type, a_id, b_id, poi_id,
                a_name=a_name, b_name=b_name, poi_name=poi_name,
                rel_from=from_state, rel_to=to_state,
            )

    @staticmethod
    def _relationship_reason_text(
        ev_type: str,
        a_id: int,
        b_id: int,
        poi_id: str,
        a_name: str = "",
        b_name: str = "",
        poi_name: str = "",
        rel_from: str = "",
        rel_to: str = "",
    ) -> str:
        """WO-008 関係変化理由のテンプレ文を返す。

        RuleBasedProvider._template_relationship_reason と同一出力を保証する。
        決定論 byte 一致 (§13.3.2) の根拠。変更時は両方を同期する。
        """
        verb = {
            "meeting": "が出会ったことで関係が始まった",
            "conversation": "の会話を通じて距離が縮まった",
            "conflict": "の口論により関係が悪化した",
            "farewell": "との別れにより関係が変化した",
        }.get(ev_type, "との交流により関係が変化した")
        display_a = a_name if a_name else f"エージェント {a_id}"
        display_b = b_name if b_name else f"エージェント {b_id}"
        display_poi = poi_name if poi_name else poi_id
        if rel_from and rel_to and rel_from != rel_to:
            return (
                f"{display_a} と {display_b} {verb} (場所: {display_poi})。"
                f"関係: {rel_from} → {rel_to}。"
            )
        return f"{display_a} と {display_b} {verb} (場所: {display_poi})。"

    @staticmethod
    def _summary_text(
        ev_type: str,
        a_id: int,
        b_id: int,
        poi_id: str,
        a_name: str = "",
        b_name: str = "",
        poi_name: str = "",
    ) -> str:
        """MVP テンプレ summary を返す (§9.8.2 / 後段で Gemini 差し替え)。

        注意: 本メソッドは _generate_summary への移行後も互換性のため残す。
        直接呼び出しは _generate_summary 経由 (LLMProvider) を推奨する。

        a_name / b_name が空の場合は "エージェント {id}" 形式にフォールバックする。
        poi_name が空の場合は poi_id にフォールバックする (#2 苗字 / #4 店名)。
        """
        verb = {
            "meeting": "が出会った",
            "conversation": "が会話した",
            "conflict": "が口論した",
            "farewell": "が別れた",
        }.get(ev_type, "が交流した")
        # 表示名フォールバック
        display_a = a_name if a_name else f"エージェント {a_id}"
        display_b = b_name if b_name else f"エージェント {b_id}"
        display_poi = poi_name if poi_name else poi_id
        return f"{display_a} と {display_b} {verb} (場所: {display_poi})。"

    # ── run ─────────────────────────────────────────────────────────────────

    def _make_state_row(self, agent: _AgentRuntime, tick: int) -> dict[str, Any]:
        """agent の当 tick 状態を AgentState JSONL dict に写像する。"""
        day, time_str = tick_to_day_time(tick)
        row: dict[str, Any] = {
            "tick": tick,
            "day": day,
            "time": time_str,
            "agent_id": agent.profile.id,
            "lat": agent.lat,
            "lon": agent.lon,
            "action": agent.action,
            "status": agent.out_status,
        }
        if agent.current_poi_id is not None:
            row["current_poi_id"] = agent.current_poi_id
        if agent.target_poi is not None and agent.internal == "moving":
            row["target_poi_id"] = agent.target_poi.id
        if agent.route_mode != "none":
            row["route_mode"] = agent.route_mode
        return row

    def simulate(self) -> dict[str, Any]:
        """tick ループを回し出力バッファを満たす。summary dict を返す。"""
        # ── 初期化 (tick=0 直前) ──
        runtimes: list[_AgentRuntime] = []
        for prof in self.profiles:
            cur_id = None
            # initial_position が既存 POI 座標と一致するなら current_poi_id 設定 (§20.2 項2)
            for poi in self.pois:
                if poi.lat == prof.initial_lat and poi.lon == prof.initial_lon:
                    cur_id = poi.id
                    break
            runtimes.append(
                _AgentRuntime(
                    profile=prof,
                    lat=prof.initial_lat,
                    lon=prof.initial_lon,
                    internal="idle",
                    action="no_target",
                    current_poi_id=cur_id,
                )
            )

        for tick in range(self.ticks):
            self._append_matrix_events_for_tick(tick)
            # §9.10: tick 冒頭で POI presence 逆引き index を作る
            poi_presence = self._build_poi_presence(runtimes)
            # agent_id 昇順で 1 体ずつ処理 (rng 消費順固定)
            for rt in runtimes:
                visit = self._step_agent(rt, tick, poi_presence)
                if visit is not None:
                    self.visit_records.append(visit)
            # 状態行を出力 (agent_id 昇順)
            for rt in runtimes:
                self.agent_states.append(self._make_state_row(rt, tick))
            # arrived tick には route_mode を出したいが、次 tick の staying には引き継がない。
            for rt in runtimes:
                if rt.internal != "moving":
                    rt.route_mode = "none"
            # interaction 処理 (rng 非依存 / seeded_rand)
            events = self._process_interactions(runtimes, tick)
            self.interaction_events.extend(events)

        return self._build_summary()

    def _append_matrix_events_for_tick(self, tick: int) -> None:
        """MATRIXモード有効時だけ takeover lifecycle event を追加する。"""
        if not self.matrix_mode:
            return

        agent_id = (
            self.matrix_agent_id
            if self.matrix_agent_id is not None
            else self.profiles[0].id
        )
        day, time_str = tick_to_day_time(tick)
        end_tick = min(self.ticks - 1, self.matrix_ttl_ticks - 1)

        if tick == 0:
            # MP-003 oath_chain (v0.7.1): 命令権限ランクと役割誓約を決定論的に付与する。
            # MP-006 duel_school (v0.7.4): engagement style と competitive rank を決定論的に付与する。
            # rng を消費しないため既存の rng 消費順序は不変。
            self.matrix_events.append({
                "tick": tick,
                "day": day,
                "time": time_str,
                "type": "takeover_start",
                "agent_id": agent_id,
                "matrix_role": self.matrix_role,
                "ttl_ticks": self.matrix_ttl_ticks,
                "trigger_id": self.matrix_trigger_id,
                "source_layer": "real",
                "target_layer": "virtual",
                "world_layer": "virtual",
                "reason": "sentinel_mvp_attach",
                "hierarchy_rank": self.matrix_oath_chain_rank,
                "sworn_duty": self.matrix_sworn_duty,
                "duel_style": self.matrix_duel_style,
                "duel_rank": self.matrix_duel_rank,
            })
        if tick == end_tick:
            exit_reason = "ttl_expired"
            if exit_reason not in MATRIX_EXIT_REASON_VALUES:
                raise ValueError(f"unsupported matrix exit_reason: {exit_reason}")
            self.matrix_events.append({
                "tick": tick,
                "day": day,
                "time": time_str,
                "type": "takeover_end",
                "agent_id": agent_id,
                "matrix_role": self.matrix_role,
                "exit_reason": exit_reason,
                "trigger_id": self.matrix_trigger_id,
                "source_layer": "virtual",
                "target_layer": "real",
                "world_layer": "real",
                "reason": "sentinel_mvp_release",
            })
        if tick == self.matrix_transition_tick:
            transition_cost = WORLD_LAYER_MODEL[
                self.matrix_source_layer
            ]["transition_cost"][self.matrix_target_layer]
            # MP-002 exchange_pair (v0.7.0): 決定論的に固定値を設定する。
            # rng を消費しないため既存の rng 消費順序は不変。
            exchange_cost_payload = f"cost_unit:{transition_cost}"
            self.matrix_events.append({
                "tick": tick,
                "day": day,
                "time": time_str,
                "type": "world_transition",
                "agent_id": agent_id,
                "matrix_role": "bridge_agent",
                "trigger_id": self.matrix_trigger_id,
                "source_layer": self.matrix_source_layer,
                "target_layer": self.matrix_target_layer,
                "world_layer": self.matrix_target_layer,
                "transition_cost": transition_cost,
                "evidence_type": self.matrix_evidence_type,
                "evidence_ref": self.matrix_evidence_ref,
                "reason": "bridge_agent_transition",
                "exchange_cost_payload": exchange_cost_payload,
                "exchanged": True,
            })
        if tick == self.matrix_guide_tick:
            candidates = self._matrix_candidate_transitions(self.matrix_guide_layer)
            # MP-005 walled_society (v0.7.3): 決定論的に固定値を設定する。
            # rng を消費しないため既存の rng 消費順序は不変。
            self.matrix_events.append({
                "tick": tick,
                "day": day,
                "time": time_str,
                "type": "heartbeat",
                "agent_id": agent_id,
                "matrix_role": "guide_agent",
                "trigger_id": self.matrix_trigger_id,
                "world_layer": self.matrix_guide_layer,
                "guide_summary": (
                    f"{self.matrix_guide_layer} から選べる transition は "
                    f"{len(candidates)} 件です。"
                ),
                "candidate_transitions": candidates,
                "reason": "guide_agent_options",
                "boundary_permeability": self.matrix_boundary_permeability,
                "outside_knowledge_level": self.matrix_outside_knowledge_level,
            })
        if tick == self.matrix_human_gate_tick:
            self.matrix_events.append({
                "tick": tick,
                "day": day,
                "time": time_str,
                "type": "human_gate",
                "agent_id": agent_id,
                "matrix_role": "operator_agent",
                "trigger_id": self.matrix_trigger_id,
                "world_layer": "liminal",
                "gate_action": self.matrix_gate_action,
                "gate_status": self.matrix_gate_status,
                "gate_reason": self.matrix_gate_reason,
                "evidence_type": "human_gate",
                "evidence_ref": "human_gate",
                "reason": "operator_agent_requires_human",
            })
        if tick == self.matrix_swarm_heartbeat_tick:
            status = "alive"
            if status not in MATRIX_SWARM_STATUS_VALUES:
                raise ValueError(f"unsupported matrix swarm_status: {status}")
            self.matrix_events.append({
                "tick": tick,
                "day": day,
                "time": time_str,
                "type": "heartbeat",
                "agent_id": agent_id,
                "matrix_role": "sentinel_swarm",
                "trigger_id": self.matrix_trigger_id,
                "world_layer": "virtual",
                "swarm_status": status,
                "heartbeat_interval_ticks": self.matrix_swarm_heartbeat_interval_ticks,
                "stale_after_ticks": self.matrix_swarm_stale_after_ticks,
                "orphan_tolerance": self.matrix_swarm_orphan_tolerance,
                "reason": "sentinel_swarm_heartbeat",
            })
        if tick == self.matrix_swarm_stale_tick:
            status = "stale"
            if status not in MATRIX_SWARM_STATUS_VALUES:
                raise ValueError(f"unsupported matrix swarm_status: {status}")
            last_heartbeat_tick = self._matrix_swarm_last_heartbeat_tick()
            # MP-004 unstable_city_core (v0.7.2): 決定論的に固定値を設定する。
            # rng を消費しないため既存の rng 消費順序は不変。
            self.matrix_events.append({
                "tick": tick,
                "day": day,
                "time": time_str,
                "type": "stale_report",
                "agent_id": agent_id,
                "matrix_role": "sentinel_swarm",
                "trigger_id": self.matrix_trigger_id,
                "world_layer": "virtual",
                "swarm_status": status,
                "stale_after_ticks": self.matrix_swarm_stale_after_ticks,
                "orphan_tolerance": self.matrix_swarm_orphan_tolerance,
                "last_heartbeat_tick": last_heartbeat_tick,
                "missed_heartbeats": tick - last_heartbeat_tick,
                "reason": "sentinel_swarm_stale",
                "core_instability_level": self.matrix_core_instability_level,
                "stabilization_phase": self.matrix_stabilization_phase,
            })

    def _matrix_candidate_transitions(self, source_layer: str) -> list[dict[str, Any]]:
        """guide_agent 用の rule-based transition 候補を返す。"""
        model = WORLD_LAYER_MODEL[source_layer]
        candidates: list[dict[str, Any]] = []
        for target_layer in model["exit_layers"]:
            target_model = WORLD_LAYER_MODEL[target_layer]
            candidates.append({
                "source_layer": source_layer,
                "target_layer": target_layer,
                "transition_cost": model["transition_cost"][target_layer],
                "evidence_types": list(target_model["evidence_types"]),
            })
        return candidates

    def _matrix_swarm_last_heartbeat_tick(self) -> int:
        """sentinel_swarm stale 判定用の最終 heartbeat tick を返す。"""
        if self.matrix_swarm_heartbeat_tick is None:
            return 0
        return self.matrix_swarm_heartbeat_tick

    def _build_summary(self) -> dict[str, Any]:
        """summary.json dict を作る (data-contract §Summary JSON)。"""
        return {
            "run_id": self.run_id,
            "seed": self.seed,
            "ticks": self.ticks,
            "agents": len(self.profiles),
            "pois": len(self.pois),
            "aois": self.aois,
            "roads": self.roads,
            "interactions": len(self.interaction_events),
            "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def _build_metrics(self) -> dict[str, Any]:
        """LLM社会シミュレーション評価用の replay-derived metrics を作る。

        Individual / Scenario / Society Simulation の三層を、現行 MVP の
        決定論 replay から再計算できる軽量指標へ写像する。
        実行時刻や外部 API 状態は含めず、同一 seed・同一入力では byte 一致する。
        """
        action_counts = Counter(s["action"] for s in self.agent_states)
        status_counts = Counter(s["status"] for s in self.agent_states)
        interaction_counts = Counter(e["type"] for e in self.interaction_events)
        trip_counts = Counter(
            v["reason"] for v in self.visit_records if v.get("reason")
        )
        route_mode_counts = Counter(
            s["route_mode"] for s in self.agent_states if s.get("route_mode")
        )
        visit_counts = Counter(
            v["poi_id"] for v in self.visit_records
            if v.get("poi_id") and v["poi_id"] != "initial_position"
        )
        pair_counts = Counter(tuple(e["agent_ids"]) for e in self.interaction_events)

        total_states = len(self.agent_states)
        total_profiles = len(self.profiles)
        possible_social_edges = total_profiles * (total_profiles - 1) / 2
        social_edges = {
            tuple(sorted((p.id, peer)))
            for p in self.profiles
            for peer in p.social_networks
            if peer in self._profile_ids and peer != p.id
        }

        return {
            "schema_version": "social-simulation-metrics-v0.1",
            "run_id": self.run_id,
            "seed": self.seed,
            "ticks": self.ticks,
            "individual_simulation": {
                "agents_with_state_history": len({
                    s["agent_id"] for s in self.agent_states
                }),
                "action_diversity": len(action_counts),
                "action_count_by_type": dict(sorted(action_counts.items())),
                "profile_coverage": {
                    "agents": total_profiles,
                    "with_role": sum(1 for p in self.profiles if p.role),
                    "with_social_networks": sum(
                        1 for p in self.profiles if p.social_networks
                    ),
                    "with_rich_profile": sum(
                        1 for p in self.profiles
                        if p.occupation or p.personality or p.hobbies or p.day_pattern
                    ),
                },
            },
            "scenario_simulation": {
                "interaction_count_by_type": dict(sorted(interaction_counts.items())),
                "relationship_delta_count": sum(
                    1 for e in self.interaction_events
                    if e.get("relationship_delta", {}).get("from")
                    != e.get("relationship_delta", {}).get("to")
                ),
                "relationship_reason_count": sum(
                    1 for e in self.interaction_events
                    if e.get("relationship_reason")
                ),
                "co_presence_distribution": self._co_presence_distribution(),
                "repeated_interaction_pairs": sum(
                    1 for count in pair_counts.values() if count > 1
                ),
            },
            "society_simulation": {
                "arrival_status_rate": _safe_ratio(
                    status_counts.get("arrived", 0),
                    total_states,
                ),
                "arrival_rate": _safe_ratio(
                    status_counts.get("arrived", 0),
                    sum(route_mode_counts.values()),
                ),
                "no_target_rate": _safe_ratio(
                    action_counts.get("no_target", 0),
                    total_states,
                ),
                "trip_count_by_action": dict(sorted(trip_counts.items())),
                "route_mode_count": dict(sorted(route_mode_counts.items())),
                "route_fallback_rate": _safe_ratio(
                    route_mode_counts.get("linear_fallback", 0),
                    sum(route_mode_counts.values()),
                ),
                "poi_visit_entropy": _normalized_entropy(visit_counts),
                "unique_poi_visit_rate": _safe_ratio(len(visit_counts), len(self.pois)),
                "social_network_density": _safe_ratio(
                    len(social_edges),
                    possible_social_edges,
                ),
            },
        }

    def _co_presence_distribution(self) -> dict[str, int]:
        """同一 tick・同一 POI に同時滞在した group size 分布を返す。"""
        groups: dict[tuple[int, str], set[int]] = {}
        for state in self.agent_states:
            poi_id = state.get("current_poi_id")
            if not poi_id:
                continue
            groups.setdefault((state["tick"], poi_id), set()).add(state["agent_id"])
        counts = Counter(
            len(agent_ids) for agent_ids in groups.values() if len(agent_ids) >= 2
        )
        return {str(size): count for size, count in sorted(counts.items())}

    def run(self, out_dir: str | Path) -> dict[str, Any]:
        """simulate して replay files を out_dir へ書き出す。summary dict を返す。"""
        summary = self.simulate()
        metrics = self._build_metrics()
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        _write_jsonl(out / "agent_states.jsonl", self.agent_states)
        _write_jsonl(out / "poi_visit_records.jsonl", self.visit_records)
        _write_jsonl(out / "interaction_events.jsonl", self.interaction_events)
        if self.matrix_mode:
            _write_jsonl(out / "matrix_events.jsonl", self.matrix_events)
        _write_json(out / "summary.json", summary)
        _write_json(out / "metrics.json", metrics)
        return summary


# ─────────────────────────────────────────────────────────────────────────────
# シリアライズ (決定論: 同一 data → 同一 bytes)
# ─────────────────────────────────────────────────────────────────────────────

def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """JSONL を決定論的に書き出す (1 行 1 JSON / 末尾改行)。"""
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            f.write("\n")


def _write_json(path: Path, data: Any) -> None:
    """JSON を書き出す。"""
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _safe_ratio(numerator: float, denominator: float) -> float:
    """0 除算を避け、metrics 用の安定した比率を返す。"""
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _normalized_entropy(counts: Counter) -> float:
    """Counter の Shannon entropy を 0..1 に正規化して返す。"""
    total = sum(counts.values())
    kinds = len(counts)
    if total == 0 or kinds <= 1:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log(p)
    return entropy / math.log(kinds)


# ─────────────────────────────────────────────────────────────────────────────
# 入力ロードヘルパ
# ─────────────────────────────────────────────────────────────────────────────

def load_inputs(
    pois_path: str | Path,
    profiles_path: str | Path,
) -> tuple[list[POI], list[AgentProfile]]:
    """pois.geojson + agent_profiles*.json を読み込み参照整合を検証する。"""
    pois = load_pois(pois_path)
    poi_ids = frozenset(p.id for p in pois)
    profiles = load_agent_profiles(profiles_path, poi_ids=poi_ids)
    return pois, profiles
