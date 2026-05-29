"""test_fetch_places_sample.py — fetch_places_sample.py の検証。

ライブ API は呼ばない。小さな fixture レスポンスを使い、
以下を検証する:
  - タイル分割が bbox を覆う
  - place.id 重複除去
  - Places types → data-contract カテゴリ 逆正規化
  - 出力 5 ファイルがデータ契約を満たす (§13.1 / data_loader が読める)
  - dangling 参照ゼロ
  - summary counts 一致
  - API キーが出力ファイルに含まれない
  - bbox 外の POI が除外される
  - dry_run 時はライブ API を呼ばない
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.fetch_places_sample import (
    BBOX,
    CATEGORY_TO_PLACES_TYPES,
    PLACES_TYPE_TO_CATEGORY,
    TILE_GRID_COLS,
    TILE_GRID_ROWS,
    _assign_poi_ids,
    _build_tiles,
    _is_in_bbox,
    _places_type_to_category,
    _supplement_pois,
    fetch_and_generate,
    fetch_pois,
)
from environments.urban_2d.data_loader import (
    load_agent_profiles,
    load_aois,
    load_pois,
    load_roads,
)

# ── fixture helper ────────────────────────────────────────────────────────────

DUMMY_API_KEY = "DUMMY_TEST_KEY_DO_NOT_USE"

# 渋谷 bbox 内の座標 (テスト用ダミー)
_IN_LAT = (BBOX["lat_min"] + BBOX["lat_max"]) / 2
_IN_LON = (BBOX["lon_min"] + BBOX["lon_max"]) / 2

# bbox 外の座標
_OUT_LAT = BBOX["lat_min"] - 0.01
_OUT_LON = BBOX["lon_min"] - 0.01


def _make_place(
    place_id: str,
    lat: float = _IN_LAT,
    lon: float = _IN_LON,
    primary_type: str = "cafe",
    types: list[str] | None = None,
    name: str = "Test Place",
) -> dict[str, Any]:
    """Places API レスポンスの 1 件を模したダミー dict。

    API キーは含まない。
    """
    return {
        "id": place_id,
        "location": {"latitude": lat, "longitude": lon},
        "primaryType": primary_type,
        "types": types or [primary_type],
        "displayName": {"text": name},
    }


def _make_api_response(places: list[dict[str, Any]]) -> dict[str, Any]:
    """Places API レスポンス全体を模したダミー dict。"""
    return {"places": places}


def _mock_fetcher_factory(responses: dict[str, dict[str, Any]]):
    """included_types の最初の要素をキーに固定レスポンスを返す fetcher を生成する。

    responses: {places_type_string: api_response_dict}
    マッチしない場合は空レスポンスを返す。
    """
    def _fetcher(
        api_key: str,
        included_types: list[str],
        lat: float,
        lon: float,
        radius_m: float,
        max_result_count: int,
    ) -> dict[str, Any]:
        # API キーを print / log しない
        key = included_types[0] if included_types else ""
        return responses.get(key, {"places": []})
    return _fetcher


# ── タイル分割 ─────────────────────────────────────────────────────────────────

class TestBuildTiles:
    """_build_tiles が bbox を覆うことを検証する。"""

    def test_tile_count(self) -> None:
        """TILE_GRID_ROWS × TILE_GRID_COLS のタイル数になる。"""
        tiles = _build_tiles(BBOX, TILE_GRID_ROWS, TILE_GRID_COLS)
        assert len(tiles) == TILE_GRID_ROWS * TILE_GRID_COLS

    def test_all_tiles_in_bbox(self) -> None:
        """全タイルの中心座標が bbox 内に収まる。"""
        tiles = _build_tiles(BBOX, TILE_GRID_ROWS, TILE_GRID_COLS)
        for lat, lon in tiles:
            assert _is_in_bbox(lat, lon, BBOX), f"タイル中心 ({lat}, {lon}) が bbox 外"

    def test_tiles_cover_bbox_corners(self) -> None:
        """タイルの lat/lon が bbox の全範囲をほぼ覆う (端まで届く)。"""
        tiles = _build_tiles(BBOX, TILE_GRID_ROWS, TILE_GRID_COLS)
        lats = [t[0] for t in tiles]
        lons = [t[1] for t in tiles]
        # bbox の min/max に最大タイル幅の半分以内で近いこと
        dlat = (BBOX["lat_max"] - BBOX["lat_min"]) / TILE_GRID_ROWS
        dlon = (BBOX["lon_max"] - BBOX["lon_min"]) / TILE_GRID_COLS
        assert min(lats) <= BBOX["lat_min"] + dlat
        assert max(lats) >= BBOX["lat_max"] - dlat
        assert min(lons) <= BBOX["lon_min"] + dlon
        assert max(lons) >= BBOX["lon_max"] - dlon


# ── Places types → spec category 逆正規化 ──────────────────────────────────────

class TestPlacesTypeToCategory:
    """_places_type_to_category の変換を検証する。"""

    def test_primary_type_cafe(self) -> None:
        place = _make_place("p1", primary_type="cafe", types=["cafe"])
        assert _places_type_to_category(place) == "amenity-cafe"

    def test_primary_type_restaurant(self) -> None:
        place = _make_place("p1", primary_type="restaurant", types=["restaurant"])
        assert _places_type_to_category(place) == "amenity-restaurant"

    def test_primary_type_fast_food(self) -> None:
        place = _make_place("p1", primary_type="fast_food_restaurant")
        assert _places_type_to_category(place) == "amenity-fast_food"

    def test_primary_type_convenience_store(self) -> None:
        place = _make_place("p1", primary_type="convenience_store")
        assert _places_type_to_category(place) == "shop-convenience"

    def test_primary_type_park(self) -> None:
        place = _make_place("p1", primary_type="park")
        assert _places_type_to_category(place) == "leisure-park"

    def test_fallback_to_types_list(self) -> None:
        """primaryType が変換表になければ types リストを参照する。"""
        place = _make_place("p1", primary_type="unknown_type", types=["cafe"])
        assert _places_type_to_category(place) == "amenity-cafe"

    def test_unknown_type_returns_other(self) -> None:
        """変換表にない type は 'other-misc' を返す。"""
        place = _make_place("p1", primary_type="totally_unknown", types=["also_unknown"])
        assert _places_type_to_category(place) == "other-misc"

    def test_all_mapped_types_are_valid_categories(self) -> None:
        """変換表の全 value が '<group>-<sub>' 形式である。"""
        for places_type, category in PLACES_TYPE_TO_CATEGORY.items():
            assert "-" in category, f"{places_type} → '{category}' がハイフン区切りでない"

    def test_school_mapping(self) -> None:
        place = _make_place("p1", primary_type="school")
        assert _places_type_to_category(place) == "amenity-school"

    def test_office_mapping(self) -> None:
        place = _make_place("p1", primary_type="corporate_office")
        assert _places_type_to_category(place) == "office-building"


# ── place.id 重複除去 ─────────────────────────────────────────────────────────

class TestFetchPoisDeduplication:
    """同一 place.id が複数タイルから返された場合に重複除去される。"""

    def test_dedup_same_place_id(self, tmp_path: Path) -> None:
        """同一 place_id は 1 件しか残らない。"""
        dup_place = _make_place("poi_dup_001", primary_type="cafe")
        responses = {"cafe": _make_api_response([dup_place, dup_place])}
        fetcher = _mock_fetcher_factory(responses)

        pois = fetch_pois(
            api_key=DUMMY_API_KEY,
            cache_dir=tmp_path / "cache",
            refresh=True,
            max_per_category=20,
            dry_run=False,
            fetcher=fetcher,
        )
        ids = [p["place_id"] for p in pois]
        assert ids.count("poi_dup_001") == 1

    def test_dedup_across_tiles(self, tmp_path: Path) -> None:
        """複数タイルで同じ place_id が返されても 1 件に絞られる。"""
        shared = _make_place("shared_001", primary_type="cafe")
        responses = {"cafe": _make_api_response([shared])}
        fetcher = _mock_fetcher_factory(responses)

        pois = fetch_pois(
            api_key=DUMMY_API_KEY,
            cache_dir=tmp_path / "cache",
            refresh=True,
            max_per_category=20,
            dry_run=False,
            fetcher=fetcher,
        )
        ids = [p["place_id"] for p in pois]
        # TILE_GRID_ROWS × TILE_GRID_COLS = 4 タイルで同じ place_id が返っても 1 件
        assert ids.count("shared_001") == 1


# ── bbox 外の POI 除外 ─────────────────────────────────────────────────────────

class TestBboxFilter:
    def test_outside_bbox_excluded(self, tmp_path: Path) -> None:
        """bbox 外の座標を持つ place は除外される。"""
        outside = _make_place("out_001", lat=_OUT_LAT, lon=_OUT_LON, primary_type="cafe")
        inside = _make_place("in_001", lat=_IN_LAT, lon=_IN_LON, primary_type="cafe")
        responses = {"cafe": _make_api_response([outside, inside])}
        fetcher = _mock_fetcher_factory(responses)

        pois = fetch_pois(
            api_key=DUMMY_API_KEY,
            cache_dir=tmp_path / "cache",
            refresh=True,
            max_per_category=20,
            dry_run=False,
            fetcher=fetcher,
        )
        ids = [p["place_id"] for p in pois]
        assert "out_001" not in ids
        assert "in_001" in ids


# ── POI id 採番 ───────────────────────────────────────────────────────────────

class TestAssignPoiIds:
    def test_home_prefix(self) -> None:
        raw = [{"place_id": "x", "category": "home-residential", "lat": _IN_LAT, "lon": _IN_LON, "name": ""}]
        pois = _assign_poi_ids(raw)
        assert pois[0]["id"].startswith("poi_home_")

    def test_work_prefix(self) -> None:
        raw = [{"place_id": "x", "category": "office-building", "lat": _IN_LAT, "lon": _IN_LON, "name": ""}]
        pois = _assign_poi_ids(raw)
        assert pois[0]["id"].startswith("poi_work_")

    def test_school_prefix(self) -> None:
        raw = [{"place_id": "x", "category": "amenity-school", "lat": _IN_LAT, "lon": _IN_LON, "name": ""}]
        pois = _assign_poi_ids(raw)
        assert pois[0]["id"].startswith("poi_school_")

    def test_cafe_prefix(self) -> None:
        raw = [{"place_id": "x", "category": "amenity-cafe", "lat": _IN_LAT, "lon": _IN_LON, "name": ""}]
        pois = _assign_poi_ids(raw)
        assert pois[0]["id"].startswith("poi_")
        assert not pois[0]["id"].startswith("poi_home_")
        assert not pois[0]["id"].startswith("poi_work_")
        assert not pois[0]["id"].startswith("poi_school_")

    def test_sequential_numbering(self) -> None:
        """同一 prefix は連番になる。"""
        raw = [
            {"place_id": "a", "category": "amenity-cafe", "lat": _IN_LAT, "lon": _IN_LON, "name": ""},
            {"place_id": "b", "category": "amenity-cafe", "lat": _IN_LAT, "lon": _IN_LON, "name": ""},
        ]
        pois = _assign_poi_ids(raw)
        assert pois[0]["id"] == "poi_001"
        assert pois[1]["id"] == "poi_002"

    def test_ids_start_with_poi(self) -> None:
        """全 id が 'poi_' で始まる (data-contract §Naming Conventions)。"""
        raw = [
            {"place_id": "a", "category": "amenity-cafe", "lat": _IN_LAT, "lon": _IN_LON, "name": ""},
            {"place_id": "b", "category": "home-residential", "lat": _IN_LAT, "lon": _IN_LON, "name": ""},
            {"place_id": "c", "category": "office-building", "lat": _IN_LAT, "lon": _IN_LON, "name": ""},
        ]
        pois = _assign_poi_ids(raw)
        for p in pois:
            assert p["id"].startswith("poi_"), f"'{p['id']}' が 'poi_' で始まらない"


# ── 5 ファイル出力 + data_loader 通過 ──────────────────────────────────────────

def _make_fixture_response() -> dict[str, dict[str, Any]]:
    """各カテゴリに 1 件ずつ fixture place を返す mock responses。"""
    responses: dict[str, dict[str, Any]] = {}
    # café、restaurant、bar、home、work、school 等をダミーで生成
    samples = [
        ("cafe",               "amenity-cafe",        "poi_cafe_001"),
        ("restaurant",         "amenity-restaurant",  "poi_rest_001"),
        ("fast_food_restaurant", "amenity-fast_food", "poi_ff_001"),
        ("bar",                "amenity-bar",         "poi_bar_001"),
        ("convenience_store",  "shop-convenience",    "poi_conv_001"),
        ("clothing_store",     "shop-clothing",       "poi_cloth_001"),
        ("supermarket",        "shop-supermarket",    "poi_super_001"),
        ("park",               "leisure-park",        "poi_park_001"),
        ("school",             "amenity-school",      "poi_school_001"),
        ("corporate_office",   "office-building",     "poi_office_001"),
        ("apartment_building", "home-residential",    "poi_home_001"),
    ]
    for places_type, _category, place_id in samples:
        place = _make_place(place_id, primary_type=places_type)
        responses[places_type] = _make_api_response([place])
    return responses


@pytest.fixture
def gp_dir(tmp_path: Path) -> Path:
    """fixture fetcher を使って 5 ファイルを生成し出力ディレクトリを返す。"""
    fetcher = _mock_fetcher_factory(_make_fixture_response())
    fetch_and_generate(
        out_dir=tmp_path,
        seed=42,
        agents=10,
        ticks=24,
        refresh=True,
        dry_run=False,
        max_per_category=20,
        api_key=DUMMY_API_KEY,
        cache_dir=tmp_path / "cache",
        fetcher=fetcher,
    )
    return tmp_path


class TestOutputFiles:
    """5 ファイルが生成されることを検証する。"""

    EXPECTED_FILES = (
        "pois.geojson",
        "aois.geojson",
        "roadnet.geojson",
        "agent_profiles_N10.json",
        "summary.json",
    )

    def test_all_five_files_exist(self, gp_dir: Path) -> None:
        for fname in self.EXPECTED_FILES:
            assert (gp_dir / fname).is_file(), f"{fname} が生成されていない"

    def test_no_behavioral_files(self, gp_dir: Path) -> None:
        """挙動ログは生成しない (WO-004 の責務)。"""
        for fname in ("agent_states.jsonl", "poi_visit_records.jsonl", "interaction_events.jsonl"):
            assert not (gp_dir / fname).exists(), f"{fname} が不正に生成されている"


class TestDataContract:
    """data_loader が出力ファイルを読めることを検証する (§13.1)。"""

    def test_load_pois(self, gp_dir: Path) -> None:
        pois = load_pois(gp_dir / "pois.geojson")
        assert len(pois) > 0

    def test_load_aois(self, gp_dir: Path) -> None:
        aois = load_aois(gp_dir / "aois.geojson")
        assert len(aois) == 10  # §19.6.1: 2 行 × 5 列

    def test_load_roads(self, gp_dir: Path) -> None:
        roads = load_roads(gp_dir / "roadnet.geojson")
        assert len(roads) > 0

    def test_load_agent_profiles_with_dangling_check(self, gp_dir: Path) -> None:
        """poi_ids を渡して dangling 参照ゼロを検証する。"""
        pois = load_pois(gp_dir / "pois.geojson")
        poi_ids = frozenset(p.id for p in pois)
        profiles = load_agent_profiles(
            gp_dir / "agent_profiles_N10.json",
            poi_ids=poi_ids,
        )
        assert len(profiles) == 10

    def test_poi_ids_start_with_poi(self, gp_dir: Path) -> None:
        """全 POI id が 'poi_' で始まる (data-contract §Naming Conventions)。"""
        pois = load_pois(gp_dir / "pois.geojson")
        for p in pois:
            assert p.id.startswith("poi_"), f"'{p.id}' が 'poi_' で始まらない"

    def test_poi_source_is_google_places_new(self, gp_dir: Path) -> None:
        """POI の source が 'google_places_new' または None である。"""
        data = json.loads((gp_dir / "pois.geojson").read_text(encoding="utf-8"))
        for feat in data["features"]:
            src = feat["properties"].get("source")
            # 合成補完 POI は source が設定されている場合がある
            assert src == "google_places_new" or src is None, (
                f"source='{src}' が期待外"
            )

    def test_pois_coordinates_in_bbox(self, gp_dir: Path) -> None:
        """全 POI 座標が bbox 内 (§19.2)。"""
        data = json.loads((gp_dir / "pois.geojson").read_text(encoding="utf-8"))
        for feat in data["features"]:
            lon, lat = feat["geometry"]["coordinates"]
            assert _is_in_bbox(lat, lon, BBOX), (
                f"POI 座標 ({lat}, {lon}) が bbox 外"
            )


class TestSummaryCounts:
    """summary.json の counts が実ファイルと一致することを検証する。"""

    def test_summary_matches_files(self, gp_dir: Path) -> None:
        summary = json.loads((gp_dir / "summary.json").read_text(encoding="utf-8"))
        pois = load_pois(gp_dir / "pois.geojson")
        aois = load_aois(gp_dir / "aois.geojson")
        roads = load_roads(gp_dir / "roadnet.geojson")
        poi_ids = frozenset(p.id for p in pois)
        profiles = load_agent_profiles(gp_dir / "agent_profiles_N10.json", poi_ids=poi_ids)

        assert summary["pois"] == len(pois)
        assert summary["aois"] == len(aois)
        assert summary["roads"] == len(roads)
        assert summary["agents"] == len(profiles)

    def test_summary_source_field(self, gp_dir: Path) -> None:
        """summary.json に source="google_places_new" が記録されている。"""
        summary = json.loads((gp_dir / "summary.json").read_text(encoding="utf-8"))
        assert summary.get("source") == "google_places_new"


# ── API キーが出力ファイルに含まれない ──────────────────────────────────────────

class TestApiKeyNotInOutput:
    """API キー文字列が生成ファイルに含まれないことを検証する。"""

    _OUTPUT_FILES = (
        "pois.geojson",
        "aois.geojson",
        "roadnet.geojson",
        "agent_profiles_N10.json",
        "summary.json",
    )

    def test_api_key_not_in_any_output(self, gp_dir: Path) -> None:
        for fname in self._OUTPUT_FILES:
            content = (gp_dir / fname).read_text(encoding="utf-8")
            assert DUMMY_API_KEY not in content, (
                f"API キーが {fname} に含まれている"
            )


# ── dry_run はライブ API を呼ばない ──────────────────────────────────────────────

class TestDryRun:
    def test_dry_run_does_not_call_live_api(self, tmp_path: Path) -> None:
        """dry_run=True の時、ライブ API 呼び出し関数が一切呼ばれない。"""
        # キャッシュなし・dry_run=True → POI 0 件でも crash しない
        # (supplement で home/work/school が補完される)
        called = []

        def _spy_fetcher(*args: Any, **kwargs: Any) -> dict[str, Any]:
            called.append(True)
            return {"places": []}

        fetch_and_generate(
            out_dir=tmp_path,
            seed=42,
            agents=5,
            ticks=24,
            refresh=False,
            dry_run=True,
            max_per_category=20,
            api_key=DUMMY_API_KEY,
            cache_dir=tmp_path / "cache",
            fetcher=_spy_fetcher,
        )
        assert len(called) == 0, "dry_run=True なのにライブ fetcher が呼ばれた"

    def test_dry_run_produces_valid_files(self, tmp_path: Path) -> None:
        """dry_run=True でも 5 ファイルが生成される。"""
        fetch_and_generate(
            out_dir=tmp_path,
            seed=42,
            agents=5,
            ticks=24,
            refresh=False,
            dry_run=True,
            max_per_category=20,
            api_key=DUMMY_API_KEY,
            cache_dir=tmp_path / "cache",
        )
        for fname in ("pois.geojson", "aois.geojson", "roadnet.geojson",
                       "agent_profiles_N5.json", "summary.json"):
            assert (tmp_path / fname).is_file(), f"{fname} が生成されていない"


# ── supplement_pois が home/work/school を保証する ───────────────────────────

class TestSupplementPois:
    def test_supplements_missing_categories(self) -> None:
        """home/work/school がない場合に合成 POI が追加される。"""
        import random as _random
        rng = _random.Random(42)
        pois = [
            {"id": "poi_001", "category": "amenity-cafe", "lat": _IN_LAT, "lon": _IN_LON, "name": ""},
        ]
        result = _supplement_pois(pois, rng)
        cats = {p["category"] for p in result}
        assert "home-residential" in cats
        assert "office-building" in cats
        assert "amenity-school" in cats

    def test_no_supplement_when_all_present(self) -> None:
        """必要カテゴリが揃っている場合は件数が増えない。"""
        import random as _random
        rng = _random.Random(42)
        pois = [
            {"id": "poi_home_001", "category": "home-residential", "lat": _IN_LAT, "lon": _IN_LON, "name": ""},
            {"id": "poi_work_001", "category": "office-building",  "lat": _IN_LAT, "lon": _IN_LON, "name": ""},
            {"id": "poi_school_001", "category": "amenity-school", "lat": _IN_LAT, "lon": _IN_LON, "name": ""},
        ]
        result = _supplement_pois(pois, rng)
        assert len(result) == len(pois)


# ── category_to_places_types のマッピング整合性 ──────────────────────────────

class TestCategoryMapping:
    def test_all_spec_categories_in_mapping(self) -> None:
        """§19.3.1 の全カテゴリが CATEGORY_TO_PLACES_TYPES に存在する。"""
        spec_categories = {
            "amenity-cafe", "amenity-restaurant", "amenity-fast_food",
            "amenity-bar", "shop-convenience", "shop-clothing",
            "shop-supermarket", "leisure-park", "amenity-school",
            "office-building", "home-residential", "other-misc",
        }
        for cat in spec_categories:
            assert cat in CATEGORY_TO_PLACES_TYPES, (
                f"spec カテゴリ '{cat}' が CATEGORY_TO_PLACES_TYPES にない"
            )
