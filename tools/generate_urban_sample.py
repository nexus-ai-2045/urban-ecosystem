#!/usr/bin/env python3
"""generate_urban_sample.py — WO-URBAN-002 合成データ生成 (静的データ)。

正本:
  - docs/ai-ecosystem-tool-spec.md §19 (合成データ生成仕様)
  - docs/subagents/contracts/urban-ecosystem-data-contract.md v0.2.0

scope (2026-05-29 CEO 確定 / §19 準拠):
  本スクリプトは「静的入力データ」のみを生成する。
    出力: pois.geojson / aois.geojson / roadnet.geojson /
          agent_profiles_N{n}.json / summary.json
  挙動ログ (agent_states.jsonl / poi_visit_records.jsonl /
  interaction_events.jsonl) は WO-URBAN-004 Rule Simulation の責務であり、
  本スクリプトは生成しない (§13.3 シミュレーション検証 = WO-004)。

決定論 (§19.1 / §19.7):
  random.Random(SEED) を 1 インスタンスとして固定順で消費する。
  同一 seed で静的ファイル (pois/aois/roadnet/agent_profiles) は byte 一致再現する。
  summary.json は started_at (実行時刻) を含むため再現性検証対象外。

rng 消費順序:
  §19.7 が定義する 6 step (POI座標 → role shuffle → home → work/school →
  social → road shuffle) を記載順で消費する (変更禁止)。§19.7 が明示していない
  name/age/gender は、6 step の rng 位置を保存するため road shuffle の後に
  step 7-9 として追記する (本実装の確定事項)。
  WO-006 追加フィールド (occupation/personality/hobbies/day_pattern) は
  既存 step 7-9 の後に step 10-13 として追記する (変更禁止)。
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── 既定値 (§19.1 / §19.8) ──────────────────────────────────────────────────

SEED = 42
RUN_ID = "urban_demo"
DEFAULT_AGENTS = 100
DEFAULT_POIS = 300
DEFAULT_TICKS = 24  # MVP 受け入れは 24 tick 以上 (= 2h@5min / contract §Time and Tick)
DEFAULT_OUT_DIR = "data"

# ── 合成都市 bbox (§19.2 / 渋谷駅周辺の合成 / 実在地物は再現しない) ──────────
BBOX = {
    "lat_min": 35.655,
    "lat_max": 35.670,
    "lon_min": 139.695,
    "lon_max": 139.710,
}

# ── POI カテゴリ分布 (§19.3.1 / 計 300 件) ─────────────────────────────────────
# (category, count@300, id_prefix)。home/work/school は専用 prefix (§19.3.3)。
POI_DISTRIBUTION: list[tuple[str, int, str]] = [
    ("amenity-cafe", 30, "poi"),
    ("amenity-restaurant", 30, "poi"),
    ("amenity-fast_food", 20, "poi"),
    ("amenity-bar", 20, "poi"),
    ("shop-convenience", 20, "poi"),
    ("shop-clothing", 15, "poi"),
    ("shop-supermarket", 10, "poi"),
    ("leisure-park", 15, "poi"),
    ("amenity-school", 5, "poi_school"),
    ("office-building", 25, "poi_work"),
    ("home-residential", 75, "poi_home"),
    ("other-misc", 35, "poi"),
]
_DIST_TOTAL = sum(c for _, c, _ in POI_DISTRIBUTION)  # 300

# ── role 分布 (§19.4.1 / office 60% / student 20% / other 20%) ────────────────
ROLE_RATIOS: list[tuple[str, float]] = [
    ("office_worker", 0.60),
    ("student", 0.20),
    ("other", 0.20),
]

# ── 氏名 (§19.4.1 / 実在人物の直接再現は意図しない / 定数ハードコード) ─────────
SURNAMES = [
    "田中", "佐藤", "鈴木", "高橋", "渡辺", "伊藤", "山本", "中村",
    "小林", "加藤", "吉田", "山田", "佐々木", "山口", "松本", "井上",
    "木村", "林", "清水", "斎藤",
]
GIVEN_NAMES = [
    "健", "誠", "拓也", "翔", "大輝", "蓮", "颯", "陸", "優斗", "海斗",
    "さくら", "葵", "陽菜", "美咲", "彩", "結衣", "莉子", "七海", "凜", "ひかり",
]

# ── WO-006: 職業リスト (role 別に分類 / step 10 で role に応じて選択) ────────────
OCCUPATIONS_OFFICE = [
    "会社員", "エンジニア", "営業職", "管理職", "経理担当", "人事担当",
    "マーケター", "デザイナー", "コンサルタント", "プロジェクトマネージャー",
]
OCCUPATIONS_STUDENT = [
    "大学生", "専門学校生", "高校生", "大学院生",
]
OCCUPATIONS_OTHER = [
    "フリーランス", "自営業", "アルバイト", "無職", "主婦・主夫",
    "クリエイター", "ライター", "カメラマン",
]

# ── WO-006: 性格リスト (step 11) ──────────────────────────────────────────────
PERSONALITIES = [
    "几帳面", "おおらか", "内向的", "外向的", "好奇心旺盛", "慎重派",
    "楽観的", "現実主義", "負けず嫌い", "温厚", "感情的", "論理的",
]

# ── WO-006: 趣味リスト (step 12 / 1〜3 個をランダム選択) ───────────────────────
HOBBIES_POOL = [
    "読書", "ランニング", "料理", "音楽鑑賞", "ゲーム", "映画鑑賞",
    "旅行", "写真撮影", "サイクリング", "登山", "ヨガ", "カフェ巡り",
    "アニメ", "DIY", "ガーデニング", "釣り", "ボードゲーム", "プログラミング",
]

# ── WO-006: 行動傾向 (day_pattern / §9.3 時刻帯テーブルと矛盾しない傾向値) ─────
# 朝型 / 夜型 / 標準 の 3 パターン。シミュレーション側で optional hint として使う。
DAY_PATTERNS = ["morning", "night", "balanced"]

# ── social_networks (§19.5) ───────────────────────────────────────────────────
SOCIAL_MEAN_DEGREE = 5

# ── AOI 分割 (§19.6.1 / 2 行 × 5 列 = 10 枚) ─────────────────────────────────
AOI_ROWS, AOI_COLS = 2, 5


# ─────────────────────────────────────────────────────────────────────────────
# POI 生成
# ─────────────────────────────────────────────────────────────────────────────

def _build_category_counts(n_pois: int) -> list[tuple[str, int, str]]:
    """n_pois に応じたカテゴリ別件数を返す。

    n_pois == 300 のとき §19.3.1 の表を厳密に再現する。それ以外は比率で按分し、
    端数は other-misc に寄せる。home/work/school は最低 1 件を保証する。
    """
    if n_pois == _DIST_TOTAL:
        return list(POI_DISTRIBUTION)

    scale = n_pois / _DIST_TOTAL
    scaled: list[list[Any]] = []
    for category, count, prefix in POI_DISTRIBUTION:
        c = max(1, round(count * scale)) if prefix != "poi" else round(count * scale)
        scaled.append([category, c, prefix])

    # 合計を n_pois に合わせる (差分は other-misc = 末尾で吸収)
    diff = n_pois - sum(c for _, c, _ in scaled)
    scaled[-1][1] = max(0, scaled[-1][1] + diff)
    return [(cat, c, pre) for cat, c, pre in scaled]


def _gen_poi_coords(rng: random.Random, n: int) -> list[tuple[float, float]]:
    """bbox 内に一様乱数で n 点を散布する (§19.3.2)。

    rng 消費順序: lat を n 回、続けて lon を n 回 (§19.3.2 のコードに一致)。
    """
    lats = [rng.uniform(BBOX["lat_min"], BBOX["lat_max"]) for _ in range(n)]
    lons = [rng.uniform(BBOX["lon_min"], BBOX["lon_max"]) for _ in range(n)]
    return list(zip(lats, lons))


def _build_pois(rng: random.Random, n_pois: int) -> list[dict[str, Any]]:
    """POI を生成する (§19.3)。内部表現は flat dict {id, category, lat, lon}。"""
    coords = _gen_poi_coords(rng, n_pois)  # Step 1
    counts = _build_category_counts(n_pois)

    pois: list[dict[str, Any]] = []
    counters: dict[str, int] = {}
    idx = 0
    for category, count, prefix in counts:
        for _ in range(count):
            counters[prefix] = counters.get(prefix, 0) + 1
            poi_id = f"{prefix}_{counters[prefix]:03d}"
            lat, lon = coords[idx]
            pois.append({"id": poi_id, "category": category, "lat": lat, "lon": lon})
            idx += 1
    return pois


# ─────────────────────────────────────────────────────────────────────────────
# AgentProfile 生成
# ─────────────────────────────────────────────────────────────────────────────

def _build_roles(rng: random.Random, n_agents: int) -> list[str]:
    """role リストを生成しシャッフルする (§19.4.1 / Step 2)。"""
    roles: list[str] = []
    for role, ratio in ROLE_RATIOS[:-1]:
        roles.extend([role] * round(ratio * n_agents))
    roles.extend([ROLE_RATIOS[-1][0]] * (n_agents - len(roles)))  # 端数は最終 role
    rng.shuffle(roles)  # Step 2
    return roles


def _build_social_networks(
    rng: random.Random, n: int, mean_degree: int
) -> dict[int, list[int]]:
    """Erdős-Rényi G(n, p) 無向グラフを生成する (§19.5.2 / Step 5)。"""
    p = mean_degree / (n - 1) if n > 1 else 0.0
    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p:  # C(n,2) calls
                adj[i].add(j)
                adj[j].add(i)
    return {i: sorted(adj[i]) for i in range(n)}


def _build_agents_core(
    rng: random.Random, n_agents: int, pois: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """AgentProfile の core 属性 (role/home/work/social) を生成する。

    rng 消費: Step 2 (role shuffle) → Step 3 (home) → Step 4 (work/school)
    → Step 5 (social)。§19.7 の Step 6 (road shuffle) はこの後に呼び出し側で消費する。
    """
    roles = _build_roles(rng, n_agents)  # Step 2

    home_pois = [p["id"] for p in pois if p["category"] == "home-residential"]
    work_pois = [p["id"] for p in pois if p["category"] == "office-building"]
    school_pois = [p["id"] for p in pois if p["category"] == "amenity-school"]

    if not home_pois:
        raise ValueError("home-residential POI が 0 件: home_poi_id を割当てられない")

    agents: list[dict[str, Any]] = [
        {"id": i, "role": roles[i]} for i in range(n_agents)
    ]

    # Step 3: home_poi_id 割当て (n_agents × choice)
    for agent in agents:
        agent["home_poi_id"] = rng.choice(home_pois)

    # Step 4: work_or_school_poi_id 割当て (office + student のみ × choice)
    for agent in agents:
        if agent["role"] == "office_worker" and work_pois:
            agent["work_or_school_poi_id"] = rng.choice(work_pois)
        elif agent["role"] == "student" and school_pois:
            agent["work_or_school_poi_id"] = rng.choice(school_pois)
        # other は割当てない (§19.4.3)

    # Step 5: social_networks (C(n,2) × random)
    social = _build_social_networks(rng, n_agents, SOCIAL_MEAN_DEGREE)
    for agent in agents:
        agent["social_networks"] = social[agent["id"]]
    return agents


def _fill_demographics(rng: random.Random, agents: list[dict[str, Any]]) -> None:
    """name / age / gender / rich profile を埋める (§19.4.1 + WO-006)。

    rng 消費:
      Step 7 (name/surname/given) → Step 8 (age) → Step 9 (gender shuffle)
      → Step 10 (occupation) → Step 11 (personality) → Step 12 (hobbies)
      → Step 13 (day_pattern shuffle)。
    §19.7 が明示する 6 step (Step 6 = road shuffle まで) を消費し終えた後に呼ぶことで、
    6 step の rng 位置を保存する。

    決定論保証: 消費順序を変えると出力が変わるため変更禁止。
    """
    n_agents = len(agents)

    # Step 7: 姓 → 名 の順 (n_agents × 2 choice)
    for agent in agents:
        surname = rng.choice(SURNAMES)
        given = rng.choice(GIVEN_NAMES)
        agent["surname"] = surname
        agent["given"] = given
        agent["name"] = surname + given

    # Step 8: age (n_agents × randint)
    for agent in agents:
        agent["age"] = rng.randint(20, 65)

    # Step 9: gender shuffle
    genders = ["male"] * (n_agents // 2) + ["female"] * (n_agents - n_agents // 2)
    rng.shuffle(genders)
    for agent, g in zip(agents, genders):
        agent["gender"] = g

    # Step 10: occupation (role に応じた選択肢から choice)
    for agent in agents:
        if agent["role"] == "office_worker":
            agent["occupation"] = rng.choice(OCCUPATIONS_OFFICE)
        elif agent["role"] == "student":
            agent["occupation"] = rng.choice(OCCUPATIONS_STUDENT)
        else:
            agent["occupation"] = rng.choice(OCCUPATIONS_OTHER)

    # Step 11: personality (n_agents × choice)
    for agent in agents:
        agent["personality"] = rng.choice(PERSONALITIES)

    # Step 12: hobbies (1〜3 個 / sample)
    for agent in agents:
        k = rng.randint(1, 3)
        agent["hobbies"] = rng.sample(HOBBIES_POOL, k)

    # Step 13: day_pattern shuffle
    patterns = [DAY_PATTERNS[i % len(DAY_PATTERNS)] for i in range(n_agents)]
    rng.shuffle(patterns)
    for agent, dp in zip(agents, patterns):
        agent["day_pattern"] = dp


def _format_profiles(
    agents: list[dict[str, Any]], pois: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """agents core + demographics を contract §Agent Profile に整形する。

    initial_position は home POI 座標と同一にする (§19.4.4)。
    """
    poi_coords = {p["id"]: (p["lat"], p["lon"]) for p in pois}
    profiles: list[dict[str, Any]] = []
    for agent in agents:
        lat, lon = poi_coords[agent["home_poi_id"]]
        profile: dict[str, Any] = {
            "id": agent["id"],
            "name": agent["name"],
            "surname": agent["surname"],
            "given": agent["given"],
            "age": agent["age"],
            "gender": agent["gender"],
            "occupation": agent["occupation"],
            "personality": agent["personality"],
            "hobbies": agent["hobbies"],
            "day_pattern": agent["day_pattern"],
            "role": agent["role"],
            "home_poi_id": agent["home_poi_id"],
            "initial_position": {"lat": lat, "lon": lon},
            "social_networks": agent["social_networks"],
        }
        if "work_or_school_poi_id" in agent:
            profile["work_or_school_poi_id"] = agent["work_or_school_poi_id"]
        profiles.append(profile)
    return profiles


# ─────────────────────────────────────────────────────────────────────────────
# AOI / Road 生成
# ─────────────────────────────────────────────────────────────────────────────

def _build_aois() -> list[dict[str, Any]]:
    """bbox を規則分割した矩形 AOI を生成する (§19.6.1 / rng 非消費)。"""
    aois: list[dict[str, Any]] = []
    dlat = (BBOX["lat_max"] - BBOX["lat_min"]) / AOI_ROWS
    dlon = (BBOX["lon_max"] - BBOX["lon_min"]) / AOI_COLS
    n = 1
    for r in range(AOI_ROWS):
        for c in range(AOI_COLS):
            lat0 = BBOX["lat_min"] + r * dlat
            lat1 = lat0 + dlat
            lon0 = BBOX["lon_min"] + c * dlon
            lon1 = lon0 + dlon
            ring = [
                [lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0],
            ]
            aois.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "id": f"aoi_{n:03d}", "name": f"District {n}", "category": "district",
                },
            })
            n += 1
    return aois


def _build_roads(
    rng: random.Random, pois: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """POI をシャッフルし隣接ペア間を結ぶ LineString を生成する (§19.6.2 / Step 6)。"""
    shuffled = pois[:]
    rng.shuffle(shuffled)  # Step 6
    roads: list[dict[str, Any]] = []
    for i, (a, b) in enumerate(zip(shuffled, shuffled[1:]), 1):
        coords = [[a["lon"], a["lat"]], [b["lon"], b["lat"]]]
        roads.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {"id": f"road_{i:03d}", "walkable": True},
        })
    return roads


# ─────────────────────────────────────────────────────────────────────────────
# シリアライズ
# ─────────────────────────────────────────────────────────────────────────────

def _poi_feature(poi: dict[str, Any]) -> dict[str, Any]:
    """flat POI dict を GeoJSON Feature に変換する (coordinates = [lon, lat])。"""
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [poi["lon"], poi["lat"]]},
        "properties": {"id": poi["id"], "category": poi["category"], "source": "synthetic"},
    }


def _feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def _write_json(path: Path, data: Any) -> None:
    """決定論的に JSON を書き出す (同一 data → 同一 bytes)。"""
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ─────────────────────────────────────────────────────────────────────────────
# 生成エントリポイント
# ─────────────────────────────────────────────────────────────────────────────

def generate(
    out_dir: str | Path,
    *,
    seed: int = SEED,
    agents: int = DEFAULT_AGENTS,
    pois: int = DEFAULT_POIS,
    ticks: int = DEFAULT_TICKS,
    run_id: str = RUN_ID,
) -> dict[str, Any]:
    """静的合成データを out_dir に生成し summary dict を返す。

    rng 消費順序 (§19.7 + WO-006):
      Step 1 POI 座標 → Step 2 role shuffle → Step 3 home → Step 4 work/school
      → Step 5 social → Step 6 road shuffle → Step 7-9 name/age/gender
      → Step 10 occupation → Step 11 personality → Step 12 hobbies → Step 13 day_pattern。
    """
    if agents < 1:
        raise ValueError("agents は 1 以上が必要")
    if pois < 1:
        raise ValueError("pois は 1 以上が必要")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)

    # rng 消費は §19.7 の順序を厳守する: Step1 → 2 → 3 → 4 → 5 → 6 → (7-9)。
    poi_list = _build_pois(rng, pois)                       # Step 1: POI 座標
    agent_list = _build_agents_core(rng, agents, poi_list)  # Step 2-5: role/home/work/social
    road_list = _build_roads(rng, poi_list)                 # Step 6: road POI shuffle
    _fill_demographics(rng, agent_list)                     # Step 7-9: name/age/gender
    profiles = _format_profiles(agent_list, poi_list)
    aoi_list = _build_aois()                                # rng 非消費

    pois_path = out / "pois.geojson"
    aois_path = out / "aois.geojson"
    roads_path = out / "roadnet.geojson"
    profiles_path = out / f"agent_profiles_N{agents}.json"
    summary_path = out / "summary.json"

    _write_json(pois_path, _feature_collection([_poi_feature(p) for p in poi_list]))
    _write_json(aois_path, _feature_collection(aoi_list))
    _write_json(roads_path, _feature_collection(road_list))
    _write_json(profiles_path, profiles)

    summary = {
        "run_id": run_id,
        "seed": seed,
        "ticks": ticks,
        "agents": len(profiles),
        "pois": len(poi_list),
        "aois": len(aoi_list),
        "roads": len(road_list),
        "interactions": 0,  # 静的生成では挙動イベントを出さない (WO-004 の責務)
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _write_json(summary_path, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="urban-ecosystem 合成データ生成 (静的データ / §19 / WO-URBAN-002)",
    )
    parser.add_argument("--seed", type=int, default=SEED, help=f"乱数 seed (既定 {SEED})")
    parser.add_argument("--agents", type=int, default=DEFAULT_AGENTS, help="エージェント数")
    parser.add_argument("--pois", type=int, default=DEFAULT_POIS, help="POI 数")
    parser.add_argument("--ticks", type=int, default=DEFAULT_TICKS, help="summary 記録用 tick 数")
    parser.add_argument("--run-id", default=RUN_ID, help="run 識別子")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="出力ディレクトリ")
    args = parser.parse_args(argv)

    summary = generate(
        args.out_dir,
        seed=args.seed,
        agents=args.agents,
        pois=args.pois,
        ticks=args.ticks,
        run_id=args.run_id,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
