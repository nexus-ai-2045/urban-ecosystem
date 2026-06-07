"""
tests/e2e/test_variable_agent_profiles.py — 可変 agent profile ファイルの E2E。

viewer は summary.json の agents 数から agent_profiles_N<N>.json を読む。
README 手順の 10 体 run で agent_profiles_N10.json が読めることを確認する。
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

try:
    from playwright.sync_api import Error as PlaywrightError, Page, sync_playwright

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False
    PlaywrightError = Exception

pytestmark = pytest.mark.skipif(
    not _PLAYWRIGHT_AVAILABLE,
    reason="playwright not installed",
)

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_SERVER_PORT = 19081
_RUN_ID = "urban_small"


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def _ensure_small_run(data_root: Path) -> None:
    run_dir = data_root / _RUN_ID
    if (run_dir / "summary.json").exists():
        return

    cmd = [
        sys.executable,
        str(_PROJECT_ROOT / "tools" / "urban_simulation_cli.py"),
        "run",
        "--sample",
        "--agents",
        "10",
        "--sample-pois",
        "300",
        "--ticks",
        "24",
        "--seed",
        "42",
        "--out",
        str(run_dir),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "urban_small run の生成に失敗しました\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def _find_python_with_uvicorn() -> str:
    candidates = [
        sys.executable,
        "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
        "/usr/local/bin/python3",
    ]
    for python in candidates:
        if not Path(python).exists():
            continue
        try:
            result = subprocess.run(
                [python, "-c", "import fastapi, uvicorn"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return python
        except Exception:
            continue
    return sys.executable


@pytest.fixture(scope="module")
def variable_profile_server(tmp_path_factory):
    python = _find_python_with_uvicorn()
    data_root = tmp_path_factory.mktemp("urban_variable_profile_data")
    _ensure_small_run(data_root)

    env = {k: v for k, v in os.environ.items() if k != "GOOGLE_MAPS_API_KEY"}
    env["DATA_DIR"] = str(data_root)
    env["DATA_SOURCE"] = "local"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [
            python,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(_SERVER_PORT),
            "--log-level",
            "error",
        ],
        env=env,
        cwd=str(_PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not _wait_for_port("127.0.0.1", _SERVER_PORT, timeout=15):
        proc.terminate()
        proc.wait()
        pytest.skip("viewer server did not start")

    yield f"http://127.0.0.1:{_SERVER_PORT}"

    proc.terminate()
    proc.wait()


def test_small_run_loads_agent_profiles_n10(variable_profile_server):
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            pytest.skip(f"chromium is not available: {exc}")

        page: Page = browser.new_page()
        try:
            page.goto(variable_profile_server + "/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_selector(
                f'#run-select option[value="{_RUN_ID}"]',
                state="attached",
                timeout=10000,
            )
            page.select_option("#run-select", value=_RUN_ID)
            page.click("#btn-load")
            page.wait_for_function(
                """() => {
                    const legend = document.getElementById('legend-panel');
                    const status = document.getElementById('load-status');
                    return legend && status && (legend.textContent || '').includes('住人 10');
                }""",
                timeout=15000,
            )

            load_status = page.locator("#load-status").inner_text()
            legend_text = page.locator("#legend-panel").inner_text()

            assert "agent_profiles_N10.json" in load_status
            assert "読込失敗" not in load_status
            assert "住人 10" in legend_text
        finally:
            page.close()
            browser.close()
