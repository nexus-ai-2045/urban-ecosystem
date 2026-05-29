#!/usr/bin/env python3
"""fetch_places_sample.py — Google Places API (New) で渋谷の実 POI を取得し
静的入力データを生成する (WO-URBAN-002 実データ版)。

正本:
  - docs/ai-ecosystem-tool-spec.md §19 (カテゴリ分布 §19.3.1 / bbox §19.2)
  - docs/subagents/contracts/urban-ecosystem-data-contract.md v0.2.0

設計方針:
  - Places API (New): POST https://places.googleapis.com/v1/places:searchNearby
  - HTTP は stdlib urllib.request のみ (requirements に追加しない)
  - API キーは環境変数 GOOGLE_PLACES_API_KEY から読む / print しない
  - 実 POI (lat/lon/category) + 合成 road/aoi/agent_profiles で 5 ファイル出力
  - source="google_places_new" を POI properties に記録
  - キャッシュ: data/.places_cache/ に raw JSON を保存して再課金を避ける

CLI:
  python fetch_places_sample.py \\
      [--out-dir OUT] [--refresh] [--dry-run] [--max-per-category N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# ── プロジェクトルートを sys.path に追加 (テスト / 直接実行 両対応) ──────────────
_TOOLS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TOOLS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.generate_urban_sample import (  # noqa: E402
    BBOX,
    SEED,
    RUN_ID,
    DEFAULT_AGENTS,
    DEFAULT_TICKS,
    _build_agents_core,
    _build_aois,
    _build_roads,
    _fill_demographics,
    _format_profiles,
    _feature_collection,
    _poi_feature,
    _write_json,
)

# ── 定数 ──────────────────────────────────────────────────────────────────────

PLACES_ENDPOINT = "https://places.googleapis.com/v1/places:searchNearby"

# Places API (New) の includedTypes → data-contract カテゴリ 変換表
# 逆正規化: Places type → <group>-<sub> 形式
PLACES_TYPE_TO_CATEGORY: dict[str, str] = {
    "cafe":                  "amenity-cafe",
    "coffee_shop":           "amenity-cafe",
    "restaurant":            "amenity-restaurant",
    "japanese_restaurant":   "amenity-restaurant",
    "italian_restaurant":    "amenity-restaurant",
    "chinese_restaurant":    "amenity-restaurant",
    "fast_food_restaurant":  "amenity-fast_food",
    "hamburger_restaurant":  "amenity-fast_food",
    "ramen_restaurant":      "amenity-fast_food",
    "bar":                   "amenity-bar",
    "pub":                   "amenity-bar",
    "izakaya_restaurant":    "amenity-bar",
    "convenience_store":     "shop-convenience",
    "clothing_store":        "shop-clothing",
    "supermarket":           "shop-supermarket",
    "grocery_store":         "shop-supermarket",
    "park":                  "leisure-park",
    "national_park":         "leisure-park",
    "school":                "amenity-school",
    "primary_school":        "amenity-school",
    "secondary_school":      "amenity-school",
    "university":            "amenity-school",
    "office":                "office-building",
    "corporate_office":      "office-building",
    "apartment_building":    "home-residential",
    "apartment_complex":     "home-residential",
    "residential_area":      "home-residential",
}

# カテゴリ → Places API の includedTypes (検索に使う)
CATEGORY_TO_PLACES_TYPES: dict[str, list[str]] = {
    "amenity-cafe":         ["cafe"],
    "amenity-restaurant":   ["restaurant"],
    "amenity-fast_food":    ["fast_food_restaurant"],
    "amenity-bar":          ["bar"],
    "shop-convenience":     ["convenience_store"],
    "shop-clothing":        ["clothing_store"],
    "shop-supermarket":     ["supermarket"],
    "leisure-park":         ["park"],
    "amenity-school":       ["school"],
    "office-building":      ["corporate_office"],
    "home-residential":     ["apartment_building"],
    "other-misc":           [],  # Places に直接対応しない / 合成で補完
}

# デフォルト上限 (カテゴリ毎、1 リクエスト最大 20 件 / API 制約)
DEFAULT_MAX_PER_CATEGORY = 20

# 渋谷 bbox を円タイルに分割するグリッド設定
# bbox ≒ 1.67km × 1.35km。半径 400m の円で 2×2 = 4 タイルで概ね覆える
TILE_GRID_ROWS = 2
TILE_GRID_COLS = 2
TILE_RADIUS_METERS = 600  # 重複を許容して網羅性を上げる


# ── .env ローダー (stdlib のみ / 依存ゼロ) ──────────────────────────────────────

def _load_dotenv(env_path: Path) -> None:
    """.env ファイルを行パースして os.environ に載せる。

    既存の環境変数は上書きしない (setdefault 相当)。
    key の print は一切しない。
    """
    if not env_path.is_file():
        return
    with env_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            # コメント行・空行をスキップ
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            # export プレフィックスを除去
            if key.startswith("export "):
                key = key[7:].strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _get_api_key() -> str:
    """GOOGLE_PLACES_API_KEY を取得する。未設定なら SystemExit で案内。

    値は返却するが print / log は一切しない。
    """
    # まず .env を試みる
    _load_dotenv(_PROJECT_ROOT / ".env")
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not key:
        sys.exit(
            "ERROR: 環境変数 GOOGLE_PLACES_API_KEY が設定されていません。\n"
            "  export GOOGLE_PLACES_API_KEY=<your_key> を実行するか、\n"
            "  プロジェクトルートの .env に GOOGLE_PLACES_API_KEY=<your_key> を記述してください。\n"
            "  API キーは Google Cloud Console > Places API (New) で取得できます。"
        )
    return key


# ── タイル分割 ─────────────────────────────────────────────────────────────────

def _build_tiles(
    bbox: dict[str, float],
    rows: int,
    cols: int,
) -> list[tuple[float, float]]:
    """bbox を rows × cols グリッドに分割し、各セルの中心 (lat, lon) を返す。"""
    dlat = (bbox["lat_max"] - bbox["lat_min"]) / rows
    dlon = (bbox["lon_max"] - bbox["lon_min"]) / cols
    centers: list[tuple[float, float]] = []
    for r in range(rows):
        for c in range(cols):
            lat = bbox["lat_min"] + (r + 0.5) * dlat
            lon = bbox["lon_min"] + (c + 0.5) * dlon
            centers.append((lat, lon))
    return centers


# ── Places API 呼び出し ────────────────────────────────────────────────────────

def _search_nearby(
    api_key: str,
    included_types: list[str],
    lat: float,
    lon: float,
    radius_m: float,
    max_result_count: int,
) -> dict[str, Any]:
    """Places API (New) searchNearby を呼び出し、レスポンス dict を返す。

    ライブ呼び出し部を関数に分離し、テストから mock 可能にする。
    api_key は HTTP ヘッダーにのみ渡す。print しない。
    """
    body = {
        "includedTypes": included_types,
        "maxResultCount": min(max_result_count, 20),  # API 上限 20 件
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": radius_m,
            }
        },
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        PLACES_ENDPOINT,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "places.id,places.location,places.types,"
                "places.displayName,places.primaryType"
            ),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Places API HTTP {exc.code}: {body_text}"
        ) from exc


# ── キャッシュ ────────────────────────────────────────────────────────────────

def _cache_key(included_types: list[str], lat: float, lon: float, radius_m: float) -> str:
    """キャッシュファイル名のキーを生成する (API キーは含めない)。"""
    raw = f"{sorted(included_types)}:{lat:.6f}:{lon:.6f}:{radius_m}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_path(cache_dir: Path, included_types: list[str], lat: float, lon: float, radius_m: float) -> Path:
    """キャッシュファイルのパスを返す。"""
    return cache_dir / f"places_{_cache_key(included_types, lat, lon, radius_m)}.json"


def _fetch_or_cache(
    api_key: str,
    included_types: list[str],
    lat: float,
    lon: float,
    radius_m: float,
    max_result_count: int,
    cache_dir: Path,
    refresh: bool,
    fetcher: Callable[..., dict[str, Any]] = _search_nearby,
) -> dict[str, Any]:
    """キャッシュがあれば返し、なければ API を呼び出してキャッシュに保存する。

    fetcher 引数で依存性注入 (テスト用 mock に差し替え可)。
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_dir, included_types, lat, lon, radius_m)

    if path.is_file() and not refresh:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)

    result = fetcher(api_key, included_types, lat, lon, radius_m, max_result_count)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    return result


# ── Places レスポンス → flat POI dict ─────────────────────────────────────────

def _places_type_to_category(place: dict[str, Any]) -> str:
    """Places の types / primaryType を data-contract カテゴリに変換する。

    優先度: primaryType → types の順に変換表を引く。
    マッチなしなら "other-misc" を返す。
    """
    primary = place.get("primaryType", "")
    if primary in PLACES_TYPE_TO_CATEGORY:
        return PLACES_TYPE_TO_CATEGORY[primary]
    for t in place.get("types", []):
        if t in PLACES_TYPE_TO_CATEGORY:
            return PLACES_TYPE_TO_CATEGORY[t]
    return "other-misc"


def _normalize_place(place: dict[str, Any], category: str) -> dict[str, Any]:
    """Places API レスポンスの place を flat POI dict に正規化する。

    flat dict: {place_id, category, lat, lon, name}
    """
    loc = place.get("location", {})
    return {
        "place_id": place["id"],
        "category": category,
        "lat": float(loc.get("latitude", 0.0)),
        "lon": float(loc.get("longitude", 0.0)),
        "name": place.get("displayName", {}).get("text", ""),
    }


def _is_in_bbox(lat: float, lon: float, bbox: dict[str, float]) -> bool:
    """座標が bbox 内かを確認する。"""
    return (
        bbox["lat_min"] <= lat <= bbox["lat_max"]
        and bbox["lon_min"] <= lon <= bbox["lon_max"]
    )


# ── メイン取得ロジック ────────────────────────────────────────────────────────

def fetch_pois(
    api_key: str,
    cache_dir: Path,
    refresh: bool = False,
    max_per_category: int = DEFAULT_MAX_PER_CATEGORY,
    dry_run: bool = False,
    fetcher: Callable[..., dict[str, Any]] = _search_nearby,
) -> list[dict[str, Any]]:
    """渋谷 bbox 内の実 POI を取得し、重複除去した flat POI dict リストを返す。

    dry_run=True の時はライブ API を呼ばずキャッシュのみ参照する。
    fetcher 引数でライブ呼び出しを差し替え可能にする (依存性注入)。

    戻り値の各 dict: {place_id, category, lat, lon, name}
    bbox 外の座標は除外する。
    """
    tiles = _build_tiles(BBOX, TILE_GRID_ROWS, TILE_GRID_COLS)

    # place_id で重複除去するための dict
    seen: dict[str, dict[str, Any]] = {}

    for category, places_types in CATEGORY_TO_PLACES_TYPES.items():
        if not places_types:
            # other-misc は Places に直接対応しない / スキップ
            continue

        for (tile_lat, tile_lon) in tiles:
            cache_path = _cache_path(cache_dir, places_types, tile_lat, tile_lon, TILE_RADIUS_METERS)

            if dry_run and not cache_path.is_file():
                # dry_run でキャッシュなし → スキップ
                continue

            # dry_run 時は fetcher を使わず cache 専用の fetcher を渡す
            if dry_run:
                def _cache_only_fetcher(*args: Any, **kwargs: Any) -> dict[str, Any]:
                    raise RuntimeError("dry_run 中はライブ API を呼ばない")
                effective_fetcher = _cache_only_fetcher
            else:
                effective_fetcher = fetcher

            try:
                result = _fetch_or_cache(
                    api_key=api_key,
                    included_types=places_types,
                    lat=tile_lat,
                    lon=tile_lon,
                    radius_m=TILE_RADIUS_METERS,
                    max_result_count=max_per_category,
                    cache_dir=cache_dir,
                    refresh=refresh,
                    fetcher=effective_fetcher,
                )
            except RuntimeError:
                if dry_run:
                    continue
                raise

            for place in result.get("places", []):
                place_id = place.get("id", "")
                if not place_id or place_id in seen:
                    continue

                normalized = _normalize_place(place, category)

                # bbox 外は除外 (§19.2)
                if not _is_in_bbox(normalized["lat"], normalized["lon"], BBOX):
                    continue

                seen[place_id] = normalized

    return list(seen.values())


# ── POI id 採番 ───────────────────────────────────────────────────────────────

def _assign_poi_ids(raw_pois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """raw POI に data-contract 準拠の id を割当てる。

    id_prefix 規則 (§19.3.3 / Naming Conventions):
      home-residential → poi_home_NNN
      office-building  → poi_work_NNN
      amenity-school   → poi_school_NNN
      その他           → poi_NNN
    """
    _PREFIX_MAP: dict[str, str] = {
        "home-residential": "poi_home",
        "office-building":  "poi_work",
        "amenity-school":   "poi_school",
    }

    counters: dict[str, int] = {}
    pois: list[dict[str, Any]] = []
    for raw in raw_pois:
        category = raw["category"]
        prefix = _PREFIX_MAP.get(category, "poi")
        counters[prefix] = counters.get(prefix, 0) + 1
        poi_id = f"{prefix}_{counters[prefix]:03d}"
        pois.append({
            "id": poi_id,
            "category": category,
            "lat": raw["lat"],
            "lon": raw["lon"],
            "name": raw.get("name", ""),
        })
    return pois


# ── 合成補完: other-misc POI を足して最小要件を満たす ─────────────────────────

def _supplement_pois(
    pois: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """home/work/school 等の最低件数を保証するため合成 POI を補完する。

    home-residential / office-building / amenity-school が 0 件だと
    _build_agents_core が ValueError になるため、各 1 件以上を保証する。
    補完 POI の id は "{prefix}_supp_001" 形式で、実 POI と区別できる。
    """
    needed: dict[str, str] = {
        "home-residential": "poi_home",
        "office-building":  "poi_work",
        "amenity-school":   "poi_school",
    }
    existing_cats = {p["category"] for p in pois}
    supplemented = list(pois)
    for category, prefix in needed.items():
        if category not in existing_cats:
            lat = rng.uniform(BBOX["lat_min"], BBOX["lat_max"])
            lon = rng.uniform(BBOX["lon_min"], BBOX["lon_max"])
            supplemented.append({
                "id": f"{prefix}_supp_001",
                "category": category,
                "lat": lat,
                "lon": lon,
                "name": f"(補完) {category}",
            })
    return supplemented


# ── POI Feature 変換 (source="google_places_new") ─────────────────────────────

def _poi_feature_gp(poi: dict[str, Any]) -> dict[str, Any]:
    """flat POI dict を GeoJSON Feature に変換する (source="google_places_new")。"""
    props: dict[str, Any] = {
        "id": poi["id"],
        "category": poi["category"],
        "source": "google_places_new",
    }
    if poi.get("name"):
        props["name"] = poi["name"]
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [poi["lon"], poi["lat"]]},
        "properties": props,
    }


# ── メインの生成エントリポイント ──────────────────────────────────────────────

def fetch_and_generate(
    out_dir: str | Path,
    *,
    seed: int = SEED,
    agents: int = DEFAULT_AGENTS,
    ticks: int = DEFAULT_TICKS,
    run_id: str = RUN_ID,
    refresh: bool = False,
    dry_run: bool = False,
    max_per_category: int = DEFAULT_MAX_PER_CATEGORY,
    api_key: str | None = None,
    cache_dir: Path | None = None,
    fetcher: Callable[..., dict[str, Any]] = _search_nearby,
) -> dict[str, Any]:
    """実 POI を取得して静的入力データ 5 ファイルを生成し summary dict を返す。

    dry_run=True の時はライブ API 呼び出しをスキップし、キャッシュから読む。
    fetcher 引数でライブ呼び出しを差し替え可能 (テスト用依存性注入)。
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # API キー (dry_run 時はダミーでも動く)
    if api_key is None:
        if dry_run:
            api_key = "DRY_RUN_DUMMY_KEY"
        else:
            api_key = _get_api_key()

    # キャッシュディレクトリ
    if cache_dir is None:
        cache_dir = _PROJECT_ROOT / "data" / ".places_cache"

    # ── POI 取得 ────────────────────────────────────────────────────────────
    raw_pois = fetch_pois(
        api_key=api_key,
        cache_dir=cache_dir,
        refresh=refresh,
        max_per_category=max_per_category,
        dry_run=dry_run,
        fetcher=fetcher,
    )

    # id 採番
    poi_list = _assign_poi_ids(raw_pois)

    # rng (合成補完・agent_profiles・roads に使う)
    rng = random.Random(seed)

    # home/work/school が 0 件の場合に合成補完
    poi_list = _supplement_pois(poi_list, rng)

    # ── 合成補完: roads / aois / agent_profiles ───────────────────────────
    # generate_urban_sample.py の生成関数を再利用する。
    # rng を渡して決定論的に生成する (seed 固定)。
    agent_list = _build_agents_core(rng, agents, poi_list)  # Step 2-5
    road_list = _build_roads(rng, poi_list)                  # Step 6
    _fill_demographics(rng, agent_list)                      # Step 7-9
    profiles = _format_profiles(agent_list, poi_list)
    aoi_list = _build_aois()

    # ── ファイル書き出し ──────────────────────────────────────────────────
    pois_path = out / "pois.geojson"
    aois_path = out / "aois.geojson"
    roads_path = out / "roadnet.geojson"
    profiles_path = out / f"agent_profiles_N{agents}.json"
    summary_path = out / "summary.json"

    _write_json(pois_path, _feature_collection([_poi_feature_gp(p) for p in poi_list]))
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
        "interactions": 0,
        "source": "google_places_new",
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _write_json(summary_path, summary)
    return summary


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント。"""
    parser = argparse.ArgumentParser(
        description=(
            "Google Places API (New) で渋谷の実 POI を取得し、"
            "静的入力データ 5 ファイルを生成する。"
        )
    )
    parser.add_argument("--out-dir", default="data/places_sample", help="出力ディレクトリ")
    parser.add_argument(
        "--refresh", action="store_true", help="キャッシュを無視して API を再取得"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="ライブ API を呼ばずキャッシュのみ使用 (fixture テスト用)",
    )
    parser.add_argument(
        "--max-per-category", type=int, default=DEFAULT_MAX_PER_CATEGORY,
        help=f"カテゴリ毎の最大取得件数 (既定 {DEFAULT_MAX_PER_CATEGORY})",
    )
    parser.add_argument("--seed", type=int, default=SEED, help=f"乱数 seed (既定 {SEED})")
    parser.add_argument("--agents", type=int, default=DEFAULT_AGENTS, help="エージェント数")
    parser.add_argument("--ticks", type=int, default=DEFAULT_TICKS, help="summary 記録用 tick 数")
    parser.add_argument("--run-id", default=RUN_ID, help="run 識別子")

    args = parser.parse_args(argv)

    summary = fetch_and_generate(
        out_dir=args.out_dir,
        seed=args.seed,
        agents=args.agents,
        ticks=args.ticks,
        run_id=args.run_id,
        refresh=args.refresh,
        dry_run=args.dry_run,
        max_per_category=args.max_per_category,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
