"""
urban_2d ルールベース行動決定 (§9 / §20)。

正本:
  - docs/ai-ecosystem-tool-spec.md §9 行動ルール MVP / §20 境界ケース補遺
  - docs/subagents/contracts/urban-ecosystem-data-contract.md v0.6.4

本モジュールは LLM を呼ばない決定論的ルール群 (RuleBasedProvider 相当)。
定数・距離計算・時刻帯テーブル・目的地選択・滞在時間・近接判定・
interaction 発生判定・relationship 遷移を提供する。状態保持と tick ループは
simulation.py が担う (本モジュールは純粋関数中心)。

決定論方針:
  - 移動 / 目的地抽選 / 滞在時間は simulation.py が単一 random.Random(seed) を
    agent_id 昇順の固定消費順で消費する (本モジュールは rng を引数で受け取る)。
  - interaction の発生確率 / type 抽選は seeded_rand(run_seed, tick, a_id, b_id)
    によるハッシュ由来の決定論値を使い、bucket の走査順に依存しない (§9.8.1 / §20.3)。
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Optional

from .models import POI, AgentProfile

# ── §9.7 定数まとめ (rules.py 冒頭に定義) ────────────────────────────────────

TICK_MINUTES = 5
WALK_SPEED_MPS = 1.3
STEP_M = 390.0       # WALK_SPEED_MPS * TICK_MINUTES * 60 = 390 m/tick
PROXIMITY_M = 30.0
NEIGHBOR_K = 5

# ── §9.8.1 interaction 確率係数 ───────────────────────────────────────────────

BASE_P = 0.15
SOCIAL_BONUS = 0.55
TIME_BONUS_EVENING = 0.15  # 18:00-22:00
P_MAX = 0.9

# ── §9.8.2 上限 ───────────────────────────────────────────────────────────────

MAX_INTERACTIONS_PER_TICK = 50

# ── §9.10 social 目的地バイアス ───────────────────────────────────────────────

FRIEND_GRAVITY = 3.0

# ── §9.9 relationship score 増減 ─────────────────────────────────────────────

SCORE_DELTA = {
    "meeting": +1,
    "conversation": +2,
    "conflict": -3,
    "farewell": -1,
}

# ── tick/time 定数 (data-contract §Time and Tick) ─────────────────────────────

DAY_START_MINUTES = 8 * 60  # 08:00
TICKS_PER_DAY = (24 * 60 - DAY_START_MINUTES) // TICK_MINUTES  # 192


# ─────────────────────────────────────────────────────────────────────────────
# 距離 / 時刻
# ─────────────────────────────────────────────────────────────────────────────

_EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """2 点間の Haversine 距離 (メートル) を返す (§9.4)。"""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def tick_in_day(tick: int) -> int:
    """ラン通算 tick から当日内 tick を返す。"""
    return tick % TICKS_PER_DAY


def minutes_of_tick(tick: int) -> int:
    """当日内 tick の経過分 (08:00 起点) を返す。"""
    return DAY_START_MINUTES + tick_in_day(tick) * TICK_MINUTES


def is_evening(tick: int) -> bool:
    """18:00-22:00 (social 時間帯) かどうかを返す (§9.8.1 TIME_BONUS)。"""
    m = minutes_of_tick(tick)
    return 18 * 60 <= m < 22 * 60


# ─────────────────────────────────────────────────────────────────────────────
# §9.3 時刻帯 × role 行動テーブル
# ─────────────────────────────────────────────────────────────────────────────

# 時刻帯判定で参照する分境界 (08:00 起点の当日内分)。
_M_10 = 10 * 60
_M_12 = 12 * 60
_M_13 = 13 * 60
_M_18 = 18 * 60
_M_22 = 22 * 60


def schedule_decision(
    minutes: int,
    role: str,
) -> tuple[str, str, str]:
    """時刻帯と role から (mode, categories, reason) を返す (§9.3)。

    mode は目的地解決の方法を表す内部識別子:
      - "fixed_work": work_or_school_poi_id (固定)
      - "fixed_home": home_poi_id (固定)
      - "stay_current": 現 POI 滞在 (移動なし)
      - "nearest": 候補カテゴリの最近傍
      - "weighted": 上位 K 近傍からカテゴリ重み付き抽選
      - "social": social bias 込み最近傍 (§9.10)
      - "wander": 確率 0.3 で近傍へ / 0.7 で現地滞在

    categories はカテゴリ部分一致用の語彙 (空文字列はカテゴリ不問)。
    reason は data-contract §Enumerations の reason 値。

    role は office_worker / student / other を想定。08:00-10:00 で
    office_worker/student は commute、それ以外 role は §9.3 最終行 (wander) に従う
    (§20.2 項3)。
    """
    is_worker = role in ("office_worker", "student")
    study_reason = "study" if role == "student" else "work"

    if DAY_START_MINUTES <= minutes < _M_10:
        # 08:00-10:00
        if is_worker:
            return ("fixed_work", "", "commute")
        # office_worker/student 以外は明示行なし → wander (§20.2 項3)
        return ("wander", "", "wander")

    if _M_10 <= minutes < _M_12:
        # 10:00-12:00
        if is_worker:
            return ("stay_current", "", study_reason)
        return ("wander", "", "wander")

    if _M_12 <= minutes < _M_13:
        # 12:00-13:00 全員 lunch (最近傍)
        return ("nearest", "restaurant|cafe|fast_food", "lunch")

    if _M_13 <= minutes < _M_18:
        # 13:00-18:00
        if is_worker:
            return ("fixed_work", "", study_reason)
        # その他 role: shop/park/cafe カテゴリ重み付き抽選
        return ("weighted", "shop|park|cafe", "errand")

    if _M_18 <= minutes < _M_22:
        # 18:00-22:00 全員 social
        return ("social", "bar|restaurant|cafe", "social")

    # 22:00-08:00 全員 go_home
    return ("fixed_home", "", "go_home")


def category_matches(poi_category: str, vocab: str) -> bool:
    """POI category が vocab (| 区切り) のいずれかに部分一致するか (§9.4 項2)。

    category は "<group>-<sub>" 形式のため部分一致でマッチする。
    vocab が空文字列ならカテゴリ不問 (True)。
    """
    if not vocab:
        return True
    return any(token in poi_category for token in vocab.split("|"))


# ─────────────────────────────────────────────────────────────────────────────
# §9.6 滞在時間
# ─────────────────────────────────────────────────────────────────────────────

def dwell_ticks(reason: str, rng: random.Random) -> Optional[int]:
    """reason から滞在 tick 数を返す (§9.6)。

    None は「時刻ベースで退出 (commute→work は 18:00 まで / go_home は翌 08:00 まで)」を表し、
    simulation.py 側が時刻で消化判定する。それ以外は seeded 一様抽選で固定 tick を返す。

    rng は simulation.py が agent_id 昇順の固定順で消費する単一インスタンス。
    """
    if reason in ("commute", "work", "study", "go_home"):
        # 時刻ベース退出 (固定 tick を持たない)
        return None
    if reason == "lunch":
        return rng.randint(2, 4)
    if reason == "social":
        return rng.randint(4, 12)
    if reason in ("errand", "wander"):
        return rng.randint(1, 3)
    # no_target など: 滞在 tick を持たない (毎 tick 再評価)
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# §9.4 目的地選択
# ─────────────────────────────────────────────────────────────────────────────

def nearest_poi(
    lat: float,
    lon: float,
    candidates: list[POI],
) -> Optional[POI]:
    """候補 POI のうち最近傍を返す (§9.4 項4)。

    距離が同値の場合は id 昇順で安定的に決める (決定論)。
    """
    best: Optional[POI] = None
    best_d = math.inf
    for poi in candidates:
        d = haversine_m(lat, lon, poi.lat, poi.lon)
        if d < best_d or (d == best_d and best is not None and poi.id < best.id):
            best_d = d
            best = poi
    return best


def weighted_nearest_poi(
    lat: float,
    lon: float,
    candidates: list[POI],
    rng: random.Random,
    weight_fn=None,
) -> Optional[POI]:
    """上位 K 近傍から距離逆数を重みにした seeded 抽選を行う (§9.4 項4)。

    weight_fn(poi, base_weight) が与えられた場合、距離逆数の base_weight に
    追加倍率を掛ける (§9.10 social 目的地バイアス用)。
    rng は simulation.py の単一インスタンス。候補空なら None。
    """
    if not candidates:
        return None
    # 距離昇順 (同距離は id 昇順) で上位 K を取る
    ranked = sorted(
        candidates,
        key=lambda p: (haversine_m(lat, lon, p.lat, p.lon), p.id),
    )[:NEIGHBOR_K]

    weights: list[float] = []
    for poi in ranked:
        d = haversine_m(lat, lon, poi.lat, poi.lon)
        base = 1.0 / d if d > 0 else 1e6  # 同一座標は超高重み
        if weight_fn is not None:
            base = weight_fn(poi, base)
        weights.append(base)

    total = sum(weights)
    if total <= 0:
        return ranked[0]
    r = rng.random() * total
    acc = 0.0
    for poi, w in zip(ranked, weights):
        acc += w
        if r <= acc:
            return poi
    return ranked[-1]


# ─────────────────────────────────────────────────────────────────────────────
# §9.5 直線補間移動
# ─────────────────────────────────────────────────────────────────────────────

def step_towards(
    lat: float,
    lon: float,
    target_lat: float,
    target_lon: float,
) -> tuple[float, float, bool]:
    """現在地から目的地へ STEP_M 前進した新座標と到達フラグを返す (§9.5)。

    残距離が STEP_M 以下なら目的地へスナップし arrived=True を返す。
    補間は緯度経度の線形補間 (fraction = min(1, STEP_M / remaining_m))。
    """
    remaining = haversine_m(lat, lon, target_lat, target_lon)
    if remaining <= STEP_M or remaining == 0.0:
        return (target_lat, target_lon, True)
    fraction = STEP_M / remaining
    new_lat = lat + (target_lat - lat) * fraction
    new_lon = lon + (target_lon - lon) * fraction
    return (new_lat, new_lon, False)


# ─────────────────────────────────────────────────────────────────────────────
# §9.8.1 interaction 発生判定 (seeded_rand ハッシュ)
# ─────────────────────────────────────────────────────────────────────────────

def seeded_rand(run_seed: int, tick: int, a_id: int, b_id: int, salt: str = "") -> float:
    """(run_seed, tick, a_id, b_id) から [0,1) の決定論乱数を返す (§9.8.1)。

    bucket 走査順に依存しないハッシュ由来の値。a_id/b_id は呼び出し側で
    min/max 正規化済みであること。salt で同一ペア・同一 tick から複数の独立な
    乱数を引ける (確率判定用 / type 抽選用)。
    """
    key = f"{run_seed}:{tick}:{a_id}:{b_id}:{salt}".encode("utf-8")
    digest = hashlib.sha256(key).digest()
    # 先頭 8 byte を [0,1) に正規化
    val = int.from_bytes(digest[:8], "big")
    return val / float(1 << 64)


def interaction_probability(
    run_seed: int,
    tick: int,
    a_id: int,
    b_id: int,
    in_network: bool,
) -> float:
    """近接ペアの interaction 発生確率を返す (§9.8.1)。"""
    p = BASE_P
    if in_network:
        p += SOCIAL_BONUS
    if is_evening(tick):
        p += TIME_BONUS_EVENING
    return max(0.0, min(P_MAX, p))


# §9.8.2 イベント種別の重みテーブル (関係 state → [(type, weight)])
_TYPE_WEIGHTS: dict[str, list[tuple[str, float]]] = {
    "stranger": [("meeting", 0.7), ("conversation", 0.3)],
    "acquaintance": [("conversation", 0.8), ("conflict", 0.1), ("farewell", 0.1)],
    "friend": [("conversation", 0.85), ("conflict", 0.15)],
    "close_friend": [("conversation", 0.85), ("conflict", 0.15)],
    "rival": [("conflict", 0.6), ("conversation", 0.4)],
}


def pick_interaction_type(state: str, draw: float) -> str:
    """関係 state と [0,1) の抽選値から interaction type を決める (§9.8.2)。

    close_friend は §9.8.2 に明示行がないため friend と同じ重みを使う
    (friend < close_friend は score のみの違いで type 傾向は同等とみなす)。
    """
    table = _TYPE_WEIGHTS.get(state, _TYPE_WEIGHTS["stranger"])
    total = sum(w for _, w in table)
    r = draw * total
    acc = 0.0
    for ev_type, w in table:
        acc += w
        if r <= acc:
            return ev_type
    return table[-1][0]


# ─────────────────────────────────────────────────────────────────────────────
# §9.9 relationship 遷移
# ─────────────────────────────────────────────────────────────────────────────

def state_from_score(score: int) -> str:
    """relationship score から state ラベルを算出する (§9.9 しきい値)。"""
    if score <= -3:
        return "rival"
    if score <= 0:        # -2 .. 0
        return "stranger"
    if score <= 4:        # 1 .. 4
        return "acquaintance"
    if score <= 9:        # 5 .. 9
        return "friend"
    return "close_friend"  # >= 10


def initial_pair_score(in_network: bool) -> int:
    """ペアの初期 score を返す (§9.9)。

    互いが social_networks に入っていれば 3 (acquaintance)、そうでなければ 0 (stranger)。
    """
    return 3 if in_network else 0


def is_in_network(a: AgentProfile, b: AgentProfile) -> bool:
    """a と b が互いの social_networks に入っているか (§9.10)。

    片方向参照でも true とみなす (生成側は無向グラフだが堅牢に両方向を許容)。
    """
    return (b.id in a.social_networks) or (a.id in b.social_networks)
