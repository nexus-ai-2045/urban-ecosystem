"""APIキーなし fallback viewer smoke check.

This script exercises the public-collaboration starter path without touching
Google Cloud, Google Maps, Places, Vertex AI, Cloud Run, secrets, or Discord.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], env: dict[str, str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=True)


def _get_json(url: str, timeout: float = 2.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def _wait_json(url: str, deadline_seconds: float) -> dict:
    deadline = time.monotonic() + deadline_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return _get_json(url)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _smoke_env(data_root: Path, port: int) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("GOOGLE_MAPS_API_KEY", "GOOGLE_PLACES_API_KEY", "GOOGLE_CLOUD_PROJECT"):
        env.pop(key, None)
    env["DATA_DIR"] = str(data_root)
    env["PORT"] = str(port)
    return env


@contextmanager
def _tmp_root(keep_tmp: bool) -> Iterator[Path]:
    if keep_tmp:
        yield Path(tempfile.mkdtemp(prefix="urban-fallback-smoke-"))
        return
    with tempfile.TemporaryDirectory(prefix="urban-fallback-smoke-") as tmp:
        yield Path(tmp)


def run_smoke(port: int, agents: int, seed: int, keep_tmp: bool) -> int:
    with _tmp_root(keep_tmp) as tmp_root:
        data_root = tmp_root / "data"
        out_dir = data_root / "sample"
        out_dir.mkdir(parents=True, exist_ok=True)
        env = _smoke_env(data_root, port)
        python = sys.executable

        _run(
            [
                python,
                "tools/generate_urban_sample.py",
                "--agents",
                str(agents),
                "--seed",
                str(seed),
                "--out-dir",
                str(out_dir),
            ],
            env,
        )
        _run(
            [
                python,
                "tools/urban_simulation_cli.py",
                "run",
                "--pois",
                str(out_dir / "pois.geojson"),
                "--profiles",
                str(out_dir / f"agent_profiles_N{agents}.json"),
                "--aois",
                str(out_dir / "aois.geojson"),
                "--roadnet",
                str(out_dir / "roadnet.geojson"),
                "--out",
                str(out_dir),
            ],
            env,
        )

        log_path = tmp_root / "server.log"
        with log_path.open("w", encoding="utf-8") as log_file:
            server = subprocess.Popen(
                [python, "-m", "app.main"],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )

        try:
            base_url = f"http://127.0.0.1:{port}"
            health = _wait_json(f"{base_url}/api/health", deadline_seconds=20)
            runs = _get_json(f"{base_url}/api/runs")
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)

        errors: list[str] = []
        if health.get("status") != "ok":
            errors.append(f"health.status expected ok, got {health.get('status')!r}")
        if health.get("data_source") != "local":
            errors.append(f"health.data_source expected local, got {health.get('data_source')!r}")
        if health.get("maps_key") != "absent":
            errors.append(f"health.maps_key expected absent, got {health.get('maps_key')!r}")

        run_ids = [item.get("run_id") for item in runs.get("runs", [])]
        if "sample" not in run_ids:
            errors.append(f"/api/runs expected sample in {run_ids!r}")

        result = {
            "status": "fail" if errors else "ok",
            "tmp": str(tmp_root),
            "health": health,
            "run_ids": run_ids,
            "untouched": [
                "GOOGLE_MAPS_API_KEY",
                "GOOGLE_PLACES_API_KEY",
                "GOOGLE_CLOUD_PROJECT",
                "Cloud Run",
                "Secret Manager",
                "Discord",
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))

        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18084)
    parser.add_argument("--agents", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--keep-tmp", action="store_true")
    args = parser.parse_args()
    return run_smoke(args.port, args.agents, args.seed, args.keep_tmp)


if __name__ == "__main__":
    raise SystemExit(main())
