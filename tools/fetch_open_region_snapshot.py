#!/usr/bin/env python3
"""Open regional fixture snapshot converter.

WO-URBAN-014 の first slice。live network/API には接続せず、OSMnx /
Overture 等から取得済みの小さな fixture を urban-ecosystem data contract
形式として検証・正規化・manifest 化する。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_TOOLS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TOOLS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from environments.urban_2d.data_loader import (  # noqa: E402
    load_agent_profiles,
    load_aois,
    load_pois,
    load_roads,
)

TOOL_VERSION = "open-region-snapshot-v0.1"
MANIFEST_SCHEMA_VERSION = "open-region-snapshot-manifest-v0.1"
DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"

REQUIRED_GEOJSON_FILES = (
    "pois.geojson",
    "aois.geojson",
    "roadnet.geojson",
)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name}: JSON parse error: {exc}") from exc


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _collect_lonlat(geometry: dict[str, Any]) -> list[tuple[float, float]]:
    coords = geometry.get("coordinates")
    points: list[tuple[float, float]] = []

    def _walk(node: Any) -> None:
        if (
            isinstance(node, list)
            and len(node) >= 2
            and isinstance(node[0], (int, float))
            and isinstance(node[1], (int, float))
        ):
            points.append((float(node[0]), float(node[1])))
            return
        if isinstance(node, list):
            for child in node:
                _walk(child)

    _walk(coords)
    return points


def _bbox_from_feature_collections(collections: list[dict[str, Any]]) -> dict[str, float]:
    points: list[tuple[float, float]] = []
    for fc in collections:
        for feature in fc.get("features", []):
            geometry = feature.get("geometry")
            if isinstance(geometry, dict):
                points.extend(_collect_lonlat(geometry))
    if not points:
        return {"lat_min": 0.0, "lat_max": 0.0, "lon_min": 0.0, "lon_max": 0.0}
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return {
        "lat_min": min(lats),
        "lat_max": max(lats),
        "lon_min": min(lons),
        "lon_max": max(lons),
    }


def _load_source_manifest(fixture_dir: Path) -> dict[str, Any]:
    for name in ("snapshot_source_manifest.json", "source_manifest.json"):
        path = fixture_dir / name
        if path.exists():
            data = _read_json(path)
            if not isinstance(data, dict):
                raise ValueError(f"{name}: object expected")
            return data
    return {}


def _profile_files(fixture_dir: Path) -> list[Path]:
    return sorted(fixture_dir.glob("agent_profiles_N*.json"))


def create_snapshot(
    fixture_dir: str | Path,
    out_dir: str | Path,
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    source: str | None = None,
    license_name: str | None = None,
) -> dict[str, Any]:
    """Validate and copy an offline regional fixture into a snapshot directory."""
    fixture = Path(fixture_dir)
    out = Path(out_dir)
    if not fixture.is_dir():
        raise ValueError(f"fixture directory not found: {fixture}")

    missing = [name for name in REQUIRED_GEOJSON_FILES if not (fixture / name).is_file()]
    if missing:
        raise ValueError(f"fixture missing required files: {', '.join(missing)}")

    raw_pois = _read_json(fixture / "pois.geojson")
    raw_aois = _read_json(fixture / "aois.geojson")
    raw_roads = _read_json(fixture / "roadnet.geojson")

    pois = load_pois(fixture / "pois.geojson")
    aois = load_aois(fixture / "aois.geojson")
    roads = load_roads(fixture / "roadnet.geojson")
    poi_ids = frozenset(p.id for p in pois)

    profiles_written: list[str] = []
    agent_count = 0
    for profile_path in _profile_files(fixture):
        profiles = load_agent_profiles(profile_path, poi_ids=poi_ids)
        agent_count += len(profiles)
        _write_json(out / profile_path.name, _read_json(profile_path))
        profiles_written.append(profile_path.name)

    for name, data in (
        ("pois.geojson", raw_pois),
        ("aois.geojson", raw_aois),
        ("roadnet.geojson", raw_roads),
    ):
        _write_json(out / name, data)

    source_manifest = _load_source_manifest(fixture)
    bbox = _bbox_from_feature_collections([raw_pois, raw_aois, raw_roads])
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "retrieval_mode": "fixture",
        "generated_at": generated_at,
        "source": source or source_manifest.get("source", "fixture"),
        "license": license_name or source_manifest.get("license", "unknown"),
        "query": source_manifest.get("query", {}),
        "bbox": bbox,
        "counts": {
            "agents": agent_count,
            "pois": len(pois),
            "aois": len(aois),
            "roads": len(roads),
        },
        "files": {
            "pois": "pois.geojson",
            "aois": "aois.geojson",
            "roadnet": "roadnet.geojson",
            "profiles": profiles_written,
        },
        "scope": {
            "network_accessed": False,
            "google_places_accessed": False,
            "billing_scope_changed": False,
        },
        "deterministic": generated_at == DEFAULT_GENERATED_AT,
    }
    _write_json(out / "snapshot_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and copy an offline open regional fixture snapshot.",
    )
    parser.add_argument("--fixture", required=True, help="fixture directory")
    parser.add_argument("--out", required=True, help="output snapshot directory")
    parser.add_argument(
        "--generated-at",
        default=DEFAULT_GENERATED_AT,
        help="manifest generated_at; default is deterministic fixture timestamp",
    )
    parser.add_argument("--source", help="override manifest source")
    parser.add_argument("--license", dest="license_name", help="override manifest license")
    args = parser.parse_args(argv)

    try:
        manifest = create_snapshot(
            args.fixture,
            args.out,
            generated_at=args.generated_at,
            source=args.source,
            license_name=args.license_name,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
