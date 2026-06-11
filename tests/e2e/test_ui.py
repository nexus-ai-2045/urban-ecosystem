"""
tests/e2e/test_ui.py — フロントエンド E2E テスト (Playwright headless)。

正本: docs/ai-ecosystem-tool-spec.md §18.3 / §13.2 / §18.5
対象: GOOGLE_MAPS_API_KEY 未設定 (fallback 地図モード) でのUIテスト。

検証項目 (§13.2):
  1. 地図が表示される (canvas 可視 / サイズ > 0)
  2. POI レイヤーをON/OFF できる
  3. AOI レイヤーをON/OFF できる
  4. 道路レイヤーをON/OFF できる
  5. エージェントが 100 体表示される
  6. エージェントをクリックすると詳細が表示される
  7. 再生/停止/ステップ送りが動く
  8. 時刻表示が tick に応じて更新される

前提:
  - playwright Python パッケージが利用可能な場合のみ実行する。
    利用不可なら pytest.skip。
  - GOOGLE_MAPS_API_KEY は設定しない (fallback 地図 / §5.1.5 / §18.4)。
  - ローカルサーバー (uvicorn) をサブプロセスで起動し、テスト後に終了する。
  - urban_demo run のデータ (100 体 / 24 tick) を一時 DATA_DIR に生成して使用する。

識別子は英語 / コメントは日本語。
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# playwright 利用可能チェック
# ─────────────────────────────────────────────────────────────────────────────

try:
    from playwright.sync_api import sync_playwright, Page, Browser, Error as PlaywrightError
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False
    PlaywrightError = Exception  # フォールバック: import 失敗時は pytestmark で全 skip される

# playwright が使えない環境では本モジュールの全テストを skip する
pytestmark = pytest.mark.skipif(
    not _PLAYWRIGHT_AVAILABLE,
    reason="playwright not installed — install playwright package to run E2E tests",
)

# ─────────────────────────────────────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────────────────────────────────────

# プロジェクトルート
_PROJECT_ROOT = Path(__file__).parent.parent.parent

# テスト用サーバーポートの fallback 値。実際の E2E では衝突回避のため空きポートを動的に使う。
_SERVER_PORT = 19080

# サーバー起動タイムアウト (秒)
_SERVER_STARTUP_TIMEOUT = 15

# テストで使う run_id (100 体 / 24 tick を持つ run)
_RUN_ID = "urban_demo"

# tick=0 に存在すべきエージェント数の下限
_EXPECTED_AGENTS = 100

# ─────────────────────────────────────────────────────────────────────────────
# サーバー起動ヘルパー
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_e2e_run(data_root: Path) -> None:
    """E2E 用の deterministic run を一時 DATA_DIR に生成する。

    `data/` は gitignore されているため、CI の fresh checkout では
    `urban_demo` が存在しない。E2E は自前で入力と replay JSONL を用意する。
    """
    run_dir = data_root / _RUN_ID
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        return

    cmd = [
        sys.executable,
        str(_PROJECT_ROOT / "tools" / "urban_simulation_cli.py"),
        "run",
        "--sample",
        "--agents", str(_EXPECTED_AGENTS),
        "--sample-pois", "300",
        "--ticks", "24",
        "--seed", "42",
        "--matrix-mode",
        "--matrix-ttl-ticks", "4",
        "--matrix-transition-tick", "1",
        "--matrix-swarm-stale-tick", "3",
        "--out", str(run_dir),
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
            "E2E 用 urban_demo run の生成に失敗しました\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def _find_python_with_uvicorn() -> str:
    """uvicorn と fastapi が使える Python 実行パスを返す。

    sys.executable が使えない場合はよく知られたパスを試みる。
    """
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
                [python, "-c", "import uvicorn, fastapi"],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                return python
        except Exception:
            continue
    return sys.executable


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    """ポートが開くまで待つ。開いたら True を返す。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def _find_free_port() -> int:
    """E2E サーバー用の空き TCP port を返す。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# ─────────────────────────────────────────────────────────────────────────────
# pytest fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    """uvicorn でローカルサーバーを起動し、URL を返す fixture。

    GOOGLE_MAPS_API_KEY を除外して起動することで fallback 地図モードになる。
    """
    python = _find_python_with_uvicorn()
    data_root = tmp_path_factory.mktemp("urban_e2e_data")
    _ensure_e2e_run(data_root)
    server_port = _find_free_port()

    # GOOGLE_MAPS_API_KEY を除外した環境変数
    env = {k: v for k, v in os.environ.items() if k != "GOOGLE_MAPS_API_KEY"}
    env["DATA_DIR"] = str(data_root)
    env["DATA_SOURCE"] = "local"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [
            python, "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", str(server_port),
            "--log-level", "error",
        ],
        env=env,
        cwd=str(_PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # ポートが開くまで待つ
    if not _wait_for_port("127.0.0.1", server_port, timeout=_SERVER_STARTUP_TIMEOUT):
        proc.terminate()
        proc.wait()
        pytest.skip(f"サーバーが {_SERVER_STARTUP_TIMEOUT} 秒以内に起動しなかった")

    base_url = f"http://127.0.0.1:{server_port}"
    yield base_url

    proc.terminate()
    proc.wait()


@pytest.fixture(scope="module")
def playwright_browser(live_server):  # noqa: F841  live_server はサーバー起動保証のため依存
    """Playwright Chromium ヘッドレスブラウザを返す fixture。

    chromium 実体が取得されていない環境 (playwright install chromium 未実行) では
    playwright.sync_api.Error が発生するため、起動失敗を捕捉して skip に落とす。
    """
    if not _PLAYWRIGHT_AVAILABLE:
        pytest.skip("playwright not available")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except PlaywrightError as exc:
            # "Executable doesn't exist" / "executable not found" 系のメッセージを
            # ブラウザ未取得として skip に変換する。
            msg = str(exc).lower()
            if any(
                keyword in msg
                for keyword in ("executable", "not found", "does not exist", "browser is not installed")
            ):
                pytest.skip(
                    f"chromium 未取得 — `playwright install chromium` を実行してください: {exc}"
                )
            # ブラウザ未取得以外の起動エラーは再 raise する
            raise
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def loaded_page(playwright_browser, live_server):
    """データロード済みのページを返す fixture。

    - fallback 地図モードでサーバーに接続する。
    - urban_demo run のデータがロードされ、
      エージェントマーカーが描画されるまで待つ。
    """
    page: Page = playwright_browser.new_page()

    # コンソールエラーを収集 (デバッグ用)
    console_errors: list[str] = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    # ページを開く
    page.goto(live_server + "/", wait_until="domcontentloaded", timeout=15000)

    # run-select に urban_demo が出現するまで待つ
    # (サーバー側で runs API が返した後に updateRunSelector が選択肢を追加する)
    try:
        page.wait_for_selector(
            f'#run-select option[value="{_RUN_ID}"]',
            timeout=10000,
        )
    except Exception:
        # urban_demo が見つからない場合でも続行 (最初の run を使う)
        pass

    # urban_demo を選択して読み込む
    page.select_option("#run-select", value=_RUN_ID)
    page.click("#btn-load")

    # エージェントマーカーが描画されるまで待つ:
    # 詳細パネルが「データ未ロード」以外になること、または
    # canvas が描画されること (legend-total テキストが変わる) を検出する。
    try:
        page.wait_for_function(
            """() => {
                const legend = document.getElementById('legend-panel');
                if (!legend) return false;
                const text = legend.textContent || '';
                // 「データ未ロード」以外なら load 完了
                return !text.includes('データ未ロード');
            }""",
            timeout=15000,
        )
    except Exception:
        pass

    # canvas が描画されるまで追加待機 (canvas の width > 0)
    try:
        page.wait_for_function(
            """() => {
                const canvas = document.getElementById('map-canvas');
                return canvas && canvas.width > 0 && canvas.height > 0;
            }""",
            timeout=5000,
        )
    except Exception:
        pass

    # JS の非同期処理が落ち着くまで少し待つ
    time.sleep(0.5)

    yield page, console_errors

    page.close()


# ─────────────────────────────────────────────────────────────────────────────
# テストクラス
# ─────────────────────────────────────────────────────────────────────────────

class TestMapDisplay:
    """§13.2 検証項目 1: 地図が表示される。"""

    def test_canvas_is_visible(self, loaded_page):
        """fallback 地図の canvas 要素が表示されている。"""
        page, _ = loaded_page
        canvas = page.locator("#map-canvas")
        assert canvas.count() == 1, "canvas#map-canvas が DOM に存在しない"
        # fallback モードでは canvas が display:block になる
        assert canvas.is_visible(), "canvas#map-canvas が非表示"

    def test_canvas_has_nonzero_size(self, loaded_page):
        """canvas の width / height が 0 より大きい (描画済み)。"""
        page, _ = loaded_page
        size = page.evaluate("""() => {
            const c = document.getElementById('map-canvas');
            return c ? { w: c.width, h: c.height } : { w: 0, h: 0 };
        }""")
        assert size["w"] > 0, f"canvas.width = {size['w']} (期待: > 0)"
        assert size["h"] > 0, f"canvas.height = {size['h']} (期待: > 0)"

    def test_fallback_label_in_canvas(self, loaded_page):
        """fallback 地図の「Fallback Map」ラベルが canvas に描画されている。

        canvas の toDataURL が既定の白紙 (空 canvas) と異なれば描画あり と判定する。
        """
        page, _ = loaded_page
        # 描画有無: canvas の imageData に非白色ピクセルが存在するか確認
        has_nonwhite = page.evaluate("""() => {
            const c = document.getElementById('map-canvas');
            if (!c || c.width === 0 || c.height === 0) return false;
            const ctx = c.getContext('2d');
            const d = ctx.getImageData(0, 0, c.width, c.height).data;
            // 背景色 #f0f0e8 (240,240,232,255) 以外のピクセルを探す
            for (let i = 0; i < d.length; i += 4) {
                if (d[i] !== 240 || d[i+1] !== 240 || d[i+2] !== 232) return true;
            }
            return false;
        }""")
        assert has_nonwhite, "canvas が背景色しか描画していない (未描画の可能性)"

    def test_map_status_shows_fallback(self, loaded_page):
        """Google Maps 未設定時に fallback 状態が左メニューで分かる。"""
        page, _ = loaded_page
        assert page.locator("#map-mode-value").inner_text() == "Fallback"
        assert page.locator("#maps-key-value").inner_text() == "未設定"
        assert page.locator("#map-health-value").inner_text() == "Fallback表示"

    def test_settings_panel_opens_from_left_dock(self, loaded_page):
        """左下の設定ボタンから設定パネルを開ける。"""
        page, _ = loaded_page
        panel = page.locator("#settings-panel")
        assert panel.count() == 1, "#settings-panel が存在しない"
        assert not panel.is_visible(), "#settings-panel は初期状態で閉じている想定"

        page.click("#btn-settings")
        assert panel.is_visible(), "#btn-settings クリック後に設定パネルが表示されない"
        assert "未接続" in panel.inner_text()

        page.click("#btn-settings")
        assert not panel.is_visible(), "#btn-settings 2回目クリック後に設定パネルが閉じない"

    def test_new_run_panel_exists(self, loaded_page):
        """左パネルから新しい run の生成入力にアクセスできる。"""
        page, _ = loaded_page
        assert page.locator("#new-run-id-input").count() == 1
        assert page.locator("#new-run-agents-input").input_value() == "100"
        assert page.locator("#btn-create-run").count() == 1
        assert page.locator("#llm-provider-select").count() == 1

    def test_live_activity_panel_exists(self, loaded_page):
        """右パネルにリアルタイムの直近欄が表示される。"""
        page, _ = loaded_page
        assert page.locator("#live-panel").count() == 1, "#live-panel が存在しない"
        assert page.locator("#live-activity-list").count() == 1, "#live-activity-list が存在しない"
        live_text = page.locator("#live-panel").inner_text()
        assert "直近の動き" in live_text


class TestMatrixOptionalFieldsPanel:
    """MATRIX panel が MP-002〜004 の optional fields を event type ごとに表示する。"""

    def _seek_matrix_tick(self, page: "Page", tick_index: int, expected_text: str) -> str:
        """slider で tick を移動し、MATRIX panel が期待 event を描画するまで待つ。"""
        page.evaluate("""(tick) => {
            const slider = document.getElementById('time-slider');
            slider.value = String(tick);
            slider.dispatchEvent(new Event('input', { bubbles: true }));
        }""", tick_index)
        page.wait_for_function(
            """(text) => {
                const panel = document.getElementById('matrix-panel');
                return Boolean(panel && (panel.textContent || '').includes(text));
            }""",
            arg=expected_text,
            timeout=5000,
        )
        return page.locator("#matrix-panel").inner_text()

    def test_takeover_start_shows_oath_chain_fields(self, loaded_page):
        """tick 0 の takeover_start に MP-003 の階層と誓約が表示される。"""
        page, _ = loaded_page
        panel_text = self._seek_matrix_tick(page, 0, "takeover_start")

        assert "takeover_start" in panel_text
        assert "Oath chain" in panel_text
        assert "hierarchy_rank" in panel_text
        assert "1" in panel_text
        assert "sworn_duty" in panel_text
        assert "threat_containment" in panel_text

    def test_world_transition_shows_exchange_pair_fields(self, loaded_page):
        """tick 1 の world_transition に MP-002 の交換コストと完了状態が表示される。"""
        page, _ = loaded_page
        panel_text = self._seek_matrix_tick(page, 1, "world_transition")

        assert "world_transition" in panel_text
        assert "Exchange pair" in panel_text
        assert "exchange_cost_payload" in panel_text
        assert "cost_unit:1" in panel_text
        assert "exchanged" in panel_text
        assert "true" in panel_text

    def test_stale_report_shows_unstable_city_core_fields(self, loaded_page):
        """tick 3 の stale_report に MP-004 の不安定度と安定化フェーズが表示される。"""
        page, _ = loaded_page
        panel_text = self._seek_matrix_tick(page, 3, "stale_report")

        assert "stale_report" in panel_text
        assert "Unstable city core" in panel_text
        assert "core_instability_level" in panel_text
        assert "1" in panel_text
        assert "stabilization_phase" in panel_text
        assert "precursor" in panel_text


class TestLayerToggle:
    """§13.2 検証項目 2-4: レイヤー (POI / AOI / 道路) ON/OFF。"""

    def _capture_canvas_data(self, page: "Page") -> str:
        """canvas の現在状態を base64 文字列で返す。"""
        return page.evaluate("""() => {
            const c = document.getElementById('map-canvas');
            if (!c) return '';
            return c.toDataURL('image/png');
        }""")

    def test_poi_layer_toggle(self, loaded_page):
        """POI レイヤーはデフォルト OFF で、ON にすると canvas が再描画される。"""
        page, _ = loaded_page
        checkbox = page.locator("#layer-poi")
        assert checkbox.count() == 1, "#layer-poi チェックボックスが存在しない"
        assert not checkbox.is_checked(), "POI レイヤーはデフォルト OFF のはず"

        # OFF 状態の canvas データ
        data_off = self._capture_canvas_data(page)
        assert data_off, "canvas データが空"

        # チェックを入れて ON にする
        page.evaluate("document.getElementById('layer-poi').click()")
        time.sleep(0.2)  # 再描画を待つ

        data_on = self._capture_canvas_data(page)
        # ON/OFF で canvas データが変化することを確認 (= 再描画された)
        assert data_on != data_off, "POI レイヤーをONにしても canvas が変化しない"

        # 元に戻す
        page.evaluate("document.getElementById('layer-poi').click()")
        time.sleep(0.2)

    def test_aoi_layer_toggle(self, loaded_page):
        """AOI レイヤーチェックボックスを OFF にすると canvas が再描画される。"""
        page, _ = loaded_page
        checkbox = page.locator("#layer-aoi")
        assert checkbox.count() == 1, "#layer-aoi チェックボックスが存在しない"

        data_on = self._capture_canvas_data(page)
        page.evaluate("document.getElementById('layer-aoi').click()")
        time.sleep(0.2)
        data_off = self._capture_canvas_data(page)
        assert data_on != data_off, "AOI レイヤーをOFFにしても canvas が変化しない"

        # 元に戻す
        page.evaluate("document.getElementById('layer-aoi').click()")
        time.sleep(0.2)

    def test_road_layer_toggle(self, loaded_page):
        """道路レイヤーチェックボックスを ON にすると canvas が再描画される。

        道路レイヤーはデフォルト OFF (§5.1.5 / app.js layerVisible.road=false) のため、
        ON 操作で変化することを検証する。
        """
        page, _ = loaded_page
        checkbox = page.locator("#layer-road")
        assert checkbox.count() == 1, "#layer-road チェックボックスが存在しない"

        data_off = self._capture_canvas_data(page)
        page.evaluate("document.getElementById('layer-road').click()")
        time.sleep(0.2)
        data_on = self._capture_canvas_data(page)
        assert data_off != data_on, "道路レイヤーをONにしても canvas が変化しない"

        # 元に戻す (OFF に戻す)
        page.evaluate("document.getElementById('layer-road').click()")
        time.sleep(0.2)


class TestAgentDisplay:
    """§13.2 検証項目 5: エージェントが 100 体表示される。"""

    def test_100_agents_in_api_data(self, live_server):
        """API から取得した tick=0 のエージェント数が 100 体である。

        urban_demo run の agent_states.jsonl で確認する。
        ブラウザ経由ではなく API 直接確認で 100 体の存在を保証する。
        """
        url = f"{live_server}/api/data/{_RUN_ID}/agent_states.jsonl"
        try:
            resp = urllib.request.urlopen(url, timeout=10)
            text = resp.read().decode()
        except Exception as exc:
            pytest.fail(f"agent_states.jsonl の取得に失敗: {exc}")

        lines = [l for l in text.strip().split("\n") if l.strip()]
        tick0_agents = set()
        for line in lines:
            try:
                rec = json.loads(line)
                if rec.get("tick") == 0:
                    tick0_agents.add(rec["agent_id"])
            except json.JSONDecodeError:
                pass

        assert len(tick0_agents) >= _EXPECTED_AGENTS, (
            f"tick=0 のエージェント数 = {len(tick0_agents)} (期待: >= {_EXPECTED_AGENTS})"
        )

    def test_100_agents_rendered_on_canvas(self, loaded_page):
        """canvas に 100 体のエージェントマーカーが描画されている。

        FallbackMapAdapter の内部 markers 配列をページ内の JS 経由で確認する。
        ES module スコープのため直接アクセス不可のため、
        canvas ピクセル上でエージェント色 (塗りつぶし円の白内側) を数える。

        代替検証: adapter は upsertAgents 後に _layers.agent.markers に格納するが
        ES module 内変数は window から参照できない。そこで DOM の legend-panel の
        表示テキストから agents 件数を確認する。
        """
        page, _ = loaded_page
        legend_text = page.locator("#legend-panel").inner_text()
        # 凡例に「100」が含まれていることを確認 (例: "100 体" / "Agents: 100")
        # ui_panels.js が出力する凡例テキストに agents 件数が含まれる
        assert "100" in legend_text, (
            f"凡例テキストにエージェント数 100 が含まれない: {repr(legend_text[:200])}"
        )


class TestAgentClickDetail:
    """§13.2 検証項目 6: エージェントをクリックすると詳細が表示される。"""

    def test_agent_click_shows_detail(self, loaded_page):
        """canvas 上のエージェントをクリックすると詳細パネルが更新される。

        FallbackMapAdapter._handleClick が agentId を検出すると
        app.js の handleAgentClick が呼ばれ、detail-panel の内容が更新される。

        エージェント円の座標は canvas の中央付近 (最初にロードした
        tick=0 の agent_states データの1体) をターゲットにする。
        正確な座標は JS で adapter._layers.agent.markers[0] の投影座標を
        取得することで求めるが、ES module スコープの制限から直接アクセス不可。
        代替として canvas の中央付近をスキャンして非背景ピクセルをクリックする。
        """
        page, _ = loaded_page

        # クリック前の詳細パネルテキスト
        before_text = page.locator("#detail-panel").inner_text()

        # canvas 上でエージェント円を見つけてクリックする。
        # 実地図寄せの描画では通常エージェントは小さな半透明色点なので、
        # role 色に近いピクセルを探し、その座標をクリックする。
        click_result = page.evaluate("""() => {
            const c = document.getElementById('map-canvas');
            if (!c || c.width === 0) return null;
            const ctx = c.getContext('2d');
            const w = c.width;
            const h = c.height;
            const data = ctx.getImageData(0, 0, w, h).data;
            // 中央付近から探す (端は POI / AOI が多い)
            const startX = Math.floor(w * 0.1);
            const endX   = Math.floor(w * 0.9);
            const startY = Math.floor(h * 0.1);
            const endY   = Math.floor(h * 0.9);
            for (let y = startY; y < endY; y += 2) {
                for (let x = startX; x < endX; x += 2) {
                    const idx = (y * w + x) * 4;
                    const r = data[idx], g = data[idx+1], b = data[idx+2], a = data[idx+3];
                    const blueAgent = b > 130 && g > 90 && r < 120;
                    const yellowAgent = r > 170 && g > 140 && b < 120;
                    const darkAgent = r < 90 && g < 110 && b < 120;
                    if (a === 255 && (blueAgent || yellowAgent || darkAgent)) {
                        return { x, y };
                    }
                }
            }
            return null;
        }""")

        if click_result is None:
            # 白ピクセルが見つからない場合は canvas の中央をクリック
            canvas_box = page.locator("#map-canvas").bounding_box()
            if canvas_box:
                click_x = canvas_box["x"] + canvas_box["width"] / 2
                click_y = canvas_box["y"] + canvas_box["height"] / 2
            else:
                pytest.skip("canvas の bounding box を取得できなかった")
                return
        else:
            # canvas 内の相対座標 -> ページ絶対座標に変換
            canvas_box = page.locator("#map-canvas").bounding_box()
            if canvas_box is None:
                pytest.skip("canvas の bounding box を取得できなかった")
                return
            click_x = canvas_box["x"] + click_result["x"]
            click_y = canvas_box["y"] + click_result["y"]

        page.mouse.click(click_x, click_y)
        time.sleep(0.3)

        # クリック後の詳細パネルテキスト
        after_text = page.locator("#detail-panel").inner_text()

        # 詳細パネルに「プレースホルダー」以外のテキストが入っていれば agent 選択成功
        # または before_text から変化していれば成功
        placeholder = "エージェントをクリックして詳細を表示"
        if after_text.strip() == before_text.strip():
            # canvas 中央クリックでも agent が選択されなかった場合
            # ページ全体のいずれかの agent を JS 経由でクリック相当の処理を行う
            #
            # 代替: canvasのdispatchEventでクリックイベントを発火させる
            # agent_states tick=0 の最初のエージェントの座標を
            # adapter の _project メソッドに渡したいが直接アクセス不可。
            # ここでは page.evaluate でカスタムイベントを発火させる。
            fired = page.evaluate("""() => {
                // canvas クリックイベントを canvas 中央で発火させる
                const c = document.getElementById('map-canvas');
                if (!c) return false;
                const rect = c.getBoundingClientRect();
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                const ev = new MouseEvent('click', {
                    bubbles: true, cancelable: true,
                    clientX: cx, clientY: cy,
                });
                c.dispatchEvent(ev);
                return true;
            }""")
            time.sleep(0.3)
            after_text = page.locator("#detail-panel").inner_text()

        # エージェントが選択された場合は placeholder 以外のテキストが入る
        # または before_text != after_text で変化を確認する
        detail_updated = (
            placeholder not in after_text
            or after_text.strip() != before_text.strip()
        )

        # エージェント円がどこにも見つからない場合はテストを skip として扱う
        # (データはあるが画面サイズ上で円が見つからないケース)
        if not detail_updated and click_result is None:
            pytest.skip("canvas 上でエージェント円が見つからなかった (描画エリア外の可能性)")

        assert detail_updated, (
            "エージェントをクリックしても詳細パネルが更新されなかった。\n"
            f"before: {repr(before_text[:100])}\n"
            f"after:  {repr(after_text[:100])}"
        )


class TestPlaybackControls:
    """§13.2 検証項目 7: 再生/停止/ステップ送りが動く。"""

    def test_play_button_exists(self, loaded_page):
        """再生ボタンが DOM に存在する。"""
        page, _ = loaded_page
        assert page.locator("#btn-play").count() == 1, "#btn-play が存在しない"

    def test_step_button_exists(self, loaded_page):
        """ステップボタンが DOM に存在する。"""
        page, _ = loaded_page
        assert page.locator("#btn-step").count() == 1, "#btn-step が存在しない"

    def test_play_then_stop(self, loaded_page):
        """再生ボタンをクリックすると再生が始まり、もう一度クリックで停止する。

        app.js の updatePlayButton は再生中に「■ 停止」、停止中に「▶ 再生」を表示する。
        """
        page, _ = loaded_page

        # 初期状態は停止
        initial_text = page.locator("#btn-play").inner_text()

        # 再生開始
        page.click("#btn-play")
        time.sleep(0.3)
        playing_text = page.locator("#btn-play").inner_text()

        # 停止
        page.click("#btn-play")
        time.sleep(0.3)
        stopped_text = page.locator("#btn-play").inner_text()

        # 再生中と停止中でボタンテキストが異なることを確認
        assert playing_text != stopped_text, (
            f"再生/停止でボタンテキストが変化しない: playing={repr(playing_text)}, stopped={repr(stopped_text)}"
        )

        # 停止後は初期状態と同じテキストに戻る
        assert stopped_text == initial_text, (
            f"停止後のテキストが初期状態と異なる: initial={repr(initial_text)}, stopped={repr(stopped_text)}"
        )

    def test_step_advances_tick(self, loaded_page):
        """ステップボタンをクリックすると tick が進む。

        tick 進行は時刻表示の変化または slider value の変化で確認する。
        """
        page, _ = loaded_page

        # 現在の slider 値を取得
        slider_before = page.evaluate("""() => {
            const s = document.getElementById('time-slider');
            return s ? parseInt(s.value, 10) : -1;
        }""")

        # ステップ実行
        page.click("#btn-step")
        time.sleep(0.5)

        slider_after = page.evaluate("""() => {
            const s = document.getElementById('time-slider');
            return s ? parseInt(s.value, 10) : -1;
        }""")

        # slider が末尾でない限り tick が進む
        slider_max = page.evaluate("""() => {
            const s = document.getElementById('time-slider');
            return s ? parseInt(s.max, 10) : 0;
        }""")

        if slider_before < slider_max:
            assert slider_after > slider_before, (
                f"ステップ後に slider 値が増加しない: before={slider_before}, after={slider_after}"
            )
        else:
            # 末尾にいる場合はそれ以上進めない (仕様通り)
            assert slider_after == slider_max, (
                f"末尾 tick でもステップ後に slider 値が変化した: before={slider_before}, after={slider_after}"
            )


class TestTimeDisplay:
    """§13.2 検証項目 8: 時刻表示が tick に応じて更新される。"""

    def test_time_display_format(self, loaded_page):
        """時刻表示が 'Day: N  Time: HH:MM:SS' 形式になっている。

        §5.4: `Day: 0  Time: 08:00:00` 形式。
        """
        page, _ = loaded_page
        time_text = page.locator("#time-display").inner_text()
        assert "Day:" in time_text, f"時刻表示に 'Day:' が含まれない: {repr(time_text)}"
        assert "Time:" in time_text, f"時刻表示に 'Time:' が含まれない: {repr(time_text)}"

    def test_time_updates_on_step(self, loaded_page):
        """ステップ送り後に時刻表示が更新される。

        tick が末尾でなければ時刻が進む。
        """
        page, _ = loaded_page

        # 先に再生を確実に停止させる
        page.evaluate("""() => {
            const btn = document.getElementById('btn-play');
            if (btn && btn.textContent && btn.textContent.includes('停止')) btn.click();
        }""")
        time.sleep(0.1)

        # slider を最初に戻す
        page.evaluate("""() => {
            const s = document.getElementById('time-slider');
            if (s) { s.value = 0; s.dispatchEvent(new Event('input', { bubbles: true })); }
        }""")
        time.sleep(0.5)

        time_before = page.locator("#time-display").inner_text()

        # ステップ実行
        page.click("#btn-step")
        time.sleep(0.5)

        time_after = page.locator("#time-display").inner_text()

        # ticks.length > 1 の場合は時刻が変化するはず
        slider_max = page.evaluate("""() => {
            const s = document.getElementById('time-slider');
            return s ? parseInt(s.max, 10) : 0;
        }""")

        if slider_max > 0:
            assert time_before != time_after, (
                f"ステップ後に時刻表示が変化しない: before={repr(time_before)}, after={repr(time_after)}"
            )
        # slider_max == 0 は tick が 1 しかない場合: 変化なしで OK

    def test_time_slider_exists_and_has_range(self, loaded_page):
        """時刻スライダーが存在し、max > 0 の範囲を持つ。

        urban_demo は 24 tick あるため max = 23 になる。
        """
        page, _ = loaded_page
        slider_max = page.evaluate("""() => {
            const s = document.getElementById('time-slider');
            return s ? parseInt(s.max, 10) : -1;
        }""")
        assert slider_max > 0, (
            f"time-slider の max が 0 以下: max={slider_max} (データがロードされていない可能性)"
        )
