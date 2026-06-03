"""WO-URBAN-014 open regional fixture snapshot tests.

Live network/API is never used. Tests build tiny fixture directories in tmp_path.
"""

from __future__ import annotations

import filecmp
import json
import subprocess
import sys
from pathlib import Path

import pytest

from environments.urban_2d.data_loader import (
    load_agent_profiles,
    load_aois,
    load_pois,
    load_roads,
)
from tools.fetch_open_region_snapshot import (
    DEFAULT_GENERATED_AT,
    MANIFEST_SCHEMA_VERSION,
    create_snapshot,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CLI = _PROJECT_ROOT / "tools" / "fetch_open_region_snapshot.py"
_SIM_CLI = _PROJECT_ROOT / "tools" / "urban_simulation_cli.py"


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _poi_feature(poi_id: str, category: str, lon: float, lat: float) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "id": poi_id,
            "category": category,
            "name": poi_id.replace("_", " ").title(),
            "source": "test_open_fixture",
        },
    }


def _fixture_dir(base: Path) -> Path:
    fixture = base / "fixture"
    pois = {
        "type": "FeatureCollection",
        "features": [
            _poi_feature("poi_home_001", "home-residential", 139.7000, 35.6600),
            _poi_feature("poi_work_001", "office-building", 139.7010, 35.6600),
            _poi_feature("poi_cafe_001", "amenity-cafe", 139.7010, 35.6610),
        ],
    }
    aois = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [139.6995, 35.6595],
                    [139.7015, 35.6595],
                    [139.7015, 35.6615],
                    [139.6995, 35.6615],
                    [139.6995, 35.6595],
                ]],
            },
            "properties": {"id": "aoi_001", "name": "Fixture District", "category": "district"},
        }],
    }
    roads = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[139.7000, 35.6600], [139.7010, 35.6600]],
                },
                "properties": {"id": "road_001", "walkable": True},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[139.7010, 35.6600], [139.7010, 35.6610]],
                },
                "properties": {"id": "road_002", "walkable": True},
            },
        ],
    }
    profiles = [
        {
            "id": 0,
            "name": "佐藤一",
            "surname": "佐藤",
            "given": "一",
            "role": "office_worker",
            "home_poi_id": "poi_home_001",
            "work_or_school_poi_id": "poi_work_001",
            "initial_position": {"lat": 35.6600, "lon": 139.7000},
            "social_networks": [1],
        },
        {
            "id": 1,
            "name": "鈴木二",
            "surname": "鈴木",
            "given": "二",
            "role": "other",
            "home_poi_id": "poi_home_001",
            "initial_position": {"lat": 35.6600, "lon": 139.7000},
            "social_networks": [0],
        },
    ]
    source_manifest = {
        "source": "test-osm-fixture",
        "license": "ODbL-compatible-test-fixture",
        "query": {"place": "Fixture District", "bbox": [139.6995, 35.6595, 139.7015, 35.6615]},
    }
    _write_json(fixture / "pois.geojson", pois)
    _write_json(fixture / "aois.geojson", aois)
    _write_json(fixture / "roadnet.geojson", roads)
    _write_json(fixture / "agent_profiles_N2.json", profiles)
    _write_json(fixture / "source_manifest.json", source_manifest)
    return fixture


def test_create_snapshot_validates_and_writes_contract_files(tmp_path: Path) -> None:
    fixture = _fixture_dir(tmp_path)
    out = tmp_path / "snapshot"

    manifest = create_snapshot(fixture, out)

    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["retrieval_mode"] == "fixture"
    assert manifest["generated_at"] == DEFAULT_GENERATED_AT
    assert manifest["source"] == "test-osm-fixture"
    assert manifest["license"] == "ODbL-compatible-test-fixture"
    assert manifest["scope"]["network_accessed"] is False
    assert manifest["scope"]["google_places_accessed"] is False
    assert manifest["counts"] == {"agents": 2, "pois": 3, "aois": 1, "roads": 2}

    pois = load_pois(out / "pois.geojson")
    aois = load_aois(out / "aois.geojson")
    roads = load_roads(out / "roadnet.geojson")
    profiles = load_agent_profiles(out / "agent_profiles_N2.json", frozenset(p.id for p in pois))
    assert len(pois) == 3
    assert len(aois) == 1
    assert len(roads) == 2
    assert len(profiles) == 2
    assert (out / "snapshot_manifest.json").is_file()


def test_create_snapshot_is_byte_deterministic_for_fixture(tmp_path: Path) -> None:
    fixture = _fixture_dir(tmp_path)
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"

    create_snapshot(fixture, out_a)
    create_snapshot(fixture, out_b)

    for name in (
        "pois.geojson",
        "aois.geojson",
        "roadnet.geojson",
        "agent_profiles_N2.json",
        "snapshot_manifest.json",
    ):
        assert filecmp.cmp(out_a / name, out_b / name, shallow=False), name


def test_create_snapshot_rejects_missing_required_geojson(tmp_path: Path) -> None:
    fixture = _fixture_dir(tmp_path)
    (fixture / "roadnet.geojson").unlink()

    with pytest.raises(ValueError, match="roadnet.geojson"):
        create_snapshot(fixture, tmp_path / "out")


def test_create_snapshot_rejects_invalid_profile_reference(tmp_path: Path) -> None:
    fixture = _fixture_dir(tmp_path)
    profiles = json.loads((fixture / "agent_profiles_N2.json").read_text(encoding="utf-8"))
    profiles[0]["home_poi_id"] = "poi_missing"
    _write_json(fixture / "agent_profiles_N2.json", profiles)

    with pytest.raises(Exception, match="poi_missing"):
        create_snapshot(fixture, tmp_path / "out")


def test_cli_fixture_mode_outputs_manifest(tmp_path: Path) -> None:
    fixture = _fixture_dir(tmp_path)
    out = tmp_path / "cli_snapshot"

    result = subprocess.run(
        [sys.executable, str(_CLI), "--fixture", str(fixture), "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
    )

    assert result.returncode == 0, result.stderr
    manifest = json.loads(result.stdout)
    assert manifest["retrieval_mode"] == "fixture"
    assert manifest["scope"]["network_accessed"] is False
    assert (out / "snapshot_manifest.json").is_file()


def test_snapshot_can_feed_simulation_cli(tmp_path: Path) -> None:
    fixture = _fixture_dir(tmp_path)
    snapshot = tmp_path / "snapshot"
    run_out = tmp_path / "region_run"
    create_snapshot(fixture, snapshot)

    result = subprocess.run(
        [
            sys.executable,
            str(_SIM_CLI),
            "run",
            "--pois",
            str(snapshot / "pois.geojson"),
            "--profiles",
            str(snapshot / "agent_profiles_N2.json"),
            "--aois",
            str(snapshot / "aois.geojson"),
            "--roadnet",
            str(snapshot / "roadnet.geojson"),
            "--ticks",
            "6",
            "--seed",
            "42",
            "--out",
            str(run_out),
        ],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["agents"] == 2
    assert summary["pois"] == 3
    metrics = json.loads((run_out / "metrics.json").read_text(encoding="utf-8"))
    assert "route_mode_count" in metrics["society_simulation"]
