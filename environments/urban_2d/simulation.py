"""
urban_2d ルールベースシミュレーション (§9 / §13.3 / §20)。

正本:
  - docs/ai-ecosystem-tool-spec.md §9 行動ルール / §13.3 シミュレーション検証 / §20 境界ケース
  - docs/subagents/contracts/urban-ecosystem-data-contract.md v0.2.0

責務:
  profiles + POI から tick ループを回し、agent_states.jsonl /
  poi_visit_records.jsonl / interaction_events.jsonl / summary.json を生成する。
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
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from . import rules
from .data_loader import (
    load_pois,
    load_agent_profiles,
)
from .models import POI, AgentProfile
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
    # 当 tick に出力する status (contract 語彙)
    out_status: str = "staying"
    # WO-009: 道路追従用の残りウェイポイント列 [(lat, lon), ...]
    # 空リスト = 直線補間フォールバック (road graph なし / 到達不能)
    route_waypoints: list[tuple[float, float]] = field(default_factory=list)


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
        llm_provider: Optional[Any] = None,
        enable_summaries: bool = True,
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
            llm_provider: LLMProvider インスタンス (spec §10.1)。
                None の場合は RuleBasedProvider を使う (MVP 既定)。
                RuleBasedProvider 経路では決定論が保たれる (byte 一致 §13.3.2)。
            enable_summaries: True (既定) で interaction summary を生成する。
                False にすると summary は空文字になり、LLM 呼び出しをスキップする。
        """
        if ticks < 1:
            raise ValueError("ticks は 1 以上が必要")
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

        # LLMProvider: None の場合は遅延生成で RuleBasedProvider を使う
        self._llm_provider: Optional[Any] = llm_provider

        # summary 生成の on/off (#1 会話オプション)
        self._enable_summaries = enable_summaries

        self._poi_by_id: dict[str, POI] = {p.id: p for p in pois}
        self._profile_ids = frozenset(p.id for p in profiles)
        self.rng = random.Random(seed)

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
    ) -> dict:
        """§10.3 コンテキスト dict を組む (choose_destination_category 用)。

        WO-008: occupation / personality / hobbies / day_pattern / current_time を
        context に含める (acceptance criterion 1)。
        各フィールドは AgentProfile (WO-006 追加) から取得し、存在する場合のみ注入する。
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
        return ctx

    def _llm_narrow_candidates(
        self,
        agent: _AgentRuntime,
        tick: int,
        cands: list[POI],
    ) -> list[POI]:
        """LLMProvider で候補 POI を 1 カテゴリに絞り込む。

        RuleBasedProvider は "" を返すため候補は変化しない (決定論維持 §13.3.2)。
        VertexGeminiProvider が有効カテゴリを返した場合のみ絞り込む。
        不正カテゴリ/例外は §9.3 ルール (cands 全体) にフォールバックし、
        fallback を debug ログに記録する (プロンプト本文は出力しない)。
        """
        if not cands:
            return cands

        # 候補の distinct カテゴリリストを allowed_categories として渡す
        allowed = sorted({p.category for p in cands})
        ctx = self._build_destination_context(agent, tick)

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
            cands = self._llm_narrow_candidates(agent, tick, cands)
            poi = rules.nearest_poi(agent.lat, agent.lon, cands)
            if poi is None:
                return (None, "no_target", mode)
            return (poi, reason, mode)

        if mode == "weighted":
            cands = [p for p in self.pois if rules.category_matches(p.category, vocab)]
            # LLM カテゴリ絞り込み (RuleBased は no-op)
            cands = self._llm_narrow_candidates(agent, tick, cands)
            poi = rules.weighted_nearest_poi(agent.lat, agent.lon, cands, self.rng)
            if poi is None:
                return (None, "no_target", mode)
            return (poi, reason, mode)

        if mode == "social":
            cands = [p for p in self.pois if rules.category_matches(p.category, vocab)]
            # LLM カテゴリ絞り込み (RuleBased は no-op)
            cands = self._llm_narrow_candidates(agent, tick, cands)
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
            elif target.id == agent.current_poi_id and self._at_poi_coords(agent, target):
                # 既に目的地 POI に居る (stay_current 等): 移動せず滞在
                agent.internal = "at_poi"
                agent.dwell_remaining = self._dwell_for(action)
                agent.route_waypoints = []
            else:
                agent.internal = "moving"
                # WO-009: 道路追従ルートを計算して waypoints に格納する。
                # road_graph がない場合は空リスト → 既存の直線補間フォールバック。
                agent.route_waypoints = self._compute_route(
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
    ) -> list[tuple[float, float]]:
        """road_graph で src → dst のウェイポイント列を返す。

        road_graph がない場合は空リストを返す (直線補間フォールバック)。
        到達不能の場合も空リストを返す (RoadGraph.route は [(dst_lat, dst_lon)] を返すが、
        それは dst スナップなので最終目的地 = dst_lat/dst_lon と同等 → 直線で十分)。

        ウェイポイントは「まだ向かうべき残り点列」。先頭から順に消費する。
        最終要素に近づいたら到達判定を行う。
        """
        if self.road_graph is None or self.road_graph.is_empty():
            return []
        waypoints = self.road_graph.route(src_lat, src_lon, dst_lat, dst_lon)
        # フォールバック (グラフ空 / 到達不能): [(dst_lat, dst_lon)] を 1 要素で返すが
        # そのまま使うと「waypoints がある」と判定されてしまう。
        # 到達不能は直線フォールバックに委ねるため空リストを返す。
        # ただし到達可能 (>=2 ノード) のみ道路追従を使う。
        if len(waypoints) <= 1:
            # 1 要素 = 直線フォールバック (到達不能) または同一ノード
            return []
        return list(waypoints)

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
            # 直前 tick が moving で当 tick にスナップ → arrived
            if prev_internal == "moving":
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
            # interaction 処理 (rng 非依存 / seeded_rand)
            events = self._process_interactions(runtimes, tick)
            self.interaction_events.extend(events)

        return self._build_summary()

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

    def run(self, out_dir: str | Path) -> dict[str, Any]:
        """simulate して 4 ファイルを out_dir へ書き出す。summary dict を返す。"""
        summary = self.simulate()
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        _write_jsonl(out / "agent_states.jsonl", self.agent_states)
        _write_jsonl(out / "poi_visit_records.jsonl", self.visit_records)
        _write_jsonl(out / "interaction_events.jsonl", self.interaction_events)
        _write_json(out / "summary.json", summary)
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
