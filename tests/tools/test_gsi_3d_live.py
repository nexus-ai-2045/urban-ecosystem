"""
test_gsi_3d_live.py — gsi_3d_live モード (MapLibre + GSI 最適化ベクトルタイル) の基本テスト。

テスト方針:
  (a) 環境変数未設定で /static/app.js の EXPERIMENTAL_GSI_TILE プレースホルダが
      'false' に置換されていること (CI 通常実行の安全確認)。
  (b) gsi_3d_live_adapter.js が GSI tile URL を含むこと。
  (c) index.html に gsi_3d_live option が存在すること。

実タイル接続テストは 'requires_network_tile' マーカーで CI から除外する。

識別子は英語 / コメントは日本語。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# fastapi 未インストール環境では本テストモジュールを skip する。
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

# ─── import path を通す ────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.urban_viewer_server import app

# ─── パス定数 ─────────────────────────────────────────────────────────────────

_VIEWER_DIR = _PROJECT_ROOT / "tools" / "urban_viewer"
_ADAPTER_PATH = _VIEWER_DIR / "gsi_3d_live_adapter.js"
_INDEX_HTML   = _VIEWER_DIR / "index.html"


# ─────────────────────────────────────────────────────────────────────────────
# (a) EXPERIMENTAL_GSI_TILE プレースホルダ置換テスト
# ─────────────────────────────────────────────────────────────────────────────

class TestExperimentalGsiTilePlaceholder:
    def test_app_js_replaces_placeholder_with_false_when_env_not_set(self, monkeypatch):
        """EXPERIMENTAL_GSI_TILE 未設定時、/static/app.js のプレースホルダが 'false' に置換される。

        これが CI 通常実行での安全弁 (1 層目):
        - サーバーが 'false' を注入する
        - app.js の hasGsiTile = false になる
        - gsi_3d_live は一切起動しない
        """
        monkeypatch.delenv("EXPERIMENTAL_GSI_TILE", raising=False)
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        client = TestClient(app)

        res = client.get("/static/app.js")

        assert res.status_code == 200
        # プレースホルダが残っていないこと
        assert "%%EXPERIMENTAL_GSI_TILE%%" not in res.text, (
            "EXPERIMENTAL_GSI_TILE プレースホルダが置換されていない"
        )
        # 'false' が注入されていること (JSON-safe な JS literal として "false")
        assert '"false"' in res.text, (
            "EXPERIMENTAL_GSI_TILE が 'false' に置換されていない"
        )

    def test_app_js_replaces_placeholder_with_true_when_env_set(self, monkeypatch):
        """EXPERIMENTAL_GSI_TILE 設定時、プレースホルダが 'true' に置換される。"""
        monkeypatch.setenv("EXPERIMENTAL_GSI_TILE", "1")
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        client = TestClient(app)

        res = client.get("/static/app.js")

        assert res.status_code == 200
        assert "%%EXPERIMENTAL_GSI_TILE%%" not in res.text
        assert '"true"' in res.text, (
            "EXPERIMENTAL_GSI_TILE が 'true' に置換されていない"
        )

    def test_app_js_has_has_gsi_tile_constant(self):
        """app.js の source に hasGsiTile 定数が定義されている。"""
        app_js_text = (_VIEWER_DIR / "app.js").read_text(encoding="utf-8")
        assert "hasGsiTile" in app_js_text, "app.js に hasGsiTile 定数がない"
        assert "EXPERIMENTAL_GSI_TILE" in app_js_text, (
            "app.js に EXPERIMENTAL_GSI_TILE 定数がない"
        )

    def test_app_js_has_dynamic_import_for_live_adapter(self):
        """app.js が gsi_3d_live_adapter.js を dynamic import() で参照する (CI parse 安全)。"""
        app_js_text = (_VIEWER_DIR / "app.js").read_text(encoding="utf-8")
        assert "gsi_3d_live_adapter.js" in app_js_text, (
            "app.js に gsi_3d_live_adapter.js への参照がない"
        )
        # static import でないこと (import() 形式であること)
        # "import(" が含まれている必要がある
        assert "import(" in app_js_text, (
            "app.js で dynamic import() を使っていない"
        )
        # static import 行に gsi_3d_live_adapter が含まれていないこと
        for line in app_js_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") and "gsi_3d_live_adapter" in stripped:
                raise AssertionError(
                    f"gsi_3d_live_adapter.js が static import されている (CI unsafe): {line!r}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# (b) gsi_3d_live_adapter.js コンテンツテスト
# ─────────────────────────────────────────────────────────────────────────────

class TestGsi3DLiveAdapterContent:
    def test_adapter_file_exists(self):
        """gsi_3d_live_adapter.js が存在する。"""
        assert _ADAPTER_PATH.exists(), f"ファイルが見つからない: {_ADAPTER_PATH}"

    def test_adapter_contains_gsi_tile_url(self):
        """gsi_3d_live_adapter.js が GSI 最適化ベクトルタイル URL を含む。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        assert "cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1" in text, (
            "GSI tile URL が adapter に含まれていない"
        )

    def test_adapter_contains_bldA_layer(self):
        """gsi_3d_live_adapter.js が建物 source-layer 'BldA' を参照する。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        assert "BldA" in text, "建物 source-layer 'BldA' が adapter に含まれていない"

    def test_adapter_contains_rdcl_layer(self):
        """gsi_3d_live_adapter.js が道路 source-layer 'RdCL' を参照する。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        assert "RdCL" in text, "道路 source-layer 'RdCL' が adapter に含まれていない"

    def test_adapter_contains_fill_extrusion(self):
        """gsi_3d_live_adapter.js が fill-extrusion を使う (建物 3D 表現)。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        assert "fill-extrusion" in text, "fill-extrusion が adapter に含まれていない"

    def test_adapter_contains_attribution(self):
        """gsi_3d_live_adapter.js が GSI attribution テキストを含む。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        assert "国土地理院最適化ベクトルタイル" in text, (
            "GSI attribution テキストが adapter に含まれていない"
        )
        assert "実際の建物高さを示すものではない" in text, (
            "建物高さ免責テキストが adapter に含まれていない"
        )

    def test_adapter_does_not_extend(self):
        """gsi_3d_live_adapter.js は FallbackMapAdapter を extends しない (duck-typing)。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        assert "extends FallbackMapAdapter" not in text, (
            "Gsi3DLiveAdapter が FallbackMapAdapter を extends している (duck-typing 違反)"
        )

    def test_adapter_exports_class(self):
        """gsi_3d_live_adapter.js が Gsi3DLiveAdapter クラスを export する。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        assert "export class Gsi3DLiveAdapter" in text, (
            "Gsi3DLiveAdapter が export されていない"
        )

    def test_adapter_has_seven_methods(self):
        """adapter に 7 メソッド (init / setLayer / upsertAgents / highlight /
        onAgentClick / drawSocialLinks / clearSocialLinks) が定義されている。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        required_methods = [
            "init(",
            "setLayer(",
            "upsertAgents(",
            "highlight(",
            "onAgentClick(",
            "drawSocialLinks(",
            "clearSocialLinks(",
        ]
        for method in required_methods:
            assert method in text, f"adapter にメソッド {method!r} が見つからない"

    def test_adapter_throws_on_force_fail_flag(self):
        """adapter の init は __URBAN_FORCE_GSI_LIVE_FAIL__ フラグで throw する旨がコードに含まれる。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        assert "__URBAN_FORCE_GSI_LIVE_FAIL__" in text, (
            "fallback 降格テスト用フラグ __URBAN_FORCE_GSI_LIVE_FAIL__ が adapter に含まれていない"
        )

    def test_adapter_uses_fit_bounds(self):
        """adapter が fitBounds() を使って bounds を自力管理する。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        assert "fitBounds" in text, "adapter に fitBounds が含まれていない"

    def test_adapter_has_building_height_constants(self):
        """adapter に固定建物高さ (10 / 40 / 100) が含まれる。"""
        text = _ADAPTER_PATH.read_text(encoding="utf-8")
        # 固定高さ値の存在を確認 (コメントや変数で記述)
        for height in ("10", "40", "100"):
            assert height in text, f"固定建物高さ {height}m が adapter に含まれていない"


# ─────────────────────────────────────────────────────────────────────────────
# (c) index.html オプションテスト
# ─────────────────────────────────────────────────────────────────────────────

class TestIndexHtmlOption:
    def test_index_html_has_gsi_3d_live_option(self):
        """index.html に gsi_3d_live option が存在する。"""
        text = _INDEX_HTML.read_text(encoding="utf-8")
        assert 'value="gsi_3d_live"' in text, (
            "index.html に gsi_3d_live option が見つからない"
        )

    def test_index_html_live_option_has_experimental_attr(self):
        """gsi_3d_live option に data-experimental 属性が付いている (app.js が制御するため)。"""
        text = _INDEX_HTML.read_text(encoding="utf-8")
        assert "data-experimental" in text, (
            "gsi_3d_live option に data-experimental 属性がない"
        )

    def test_index_html_still_has_gsi_3d_option(self):
        """既存の gsi_3d option が残っている (既存モード維持)。"""
        text = _INDEX_HTML.read_text(encoding="utf-8")
        assert 'value="gsi_3d"' in text, "既存の gsi_3d option が消えている"

    def test_index_html_does_not_expose_maps_googleapis(self):
        """APIキー未設定時の index.html に maps.googleapis.com が含まれない。"""
        monkeypatch_delenv = os.environ.pop("GOOGLE_MAPS_API_KEY", None)
        try:
            monkeypatch_delenv_gsi = os.environ.pop("EXPERIMENTAL_GSI_TILE", None)
            try:
                client = TestClient(app)
                res = client.get("/")
                assert res.status_code == 200
                assert "maps.googleapis.com" not in res.text, (
                    "キー未設定時に maps.googleapis.com が HTML に含まれている"
                )
            finally:
                if monkeypatch_delenv_gsi is not None:
                    os.environ["EXPERIMENTAL_GSI_TILE"] = monkeypatch_delenv_gsi
        finally:
            if monkeypatch_delenv is not None:
                os.environ["GOOGLE_MAPS_API_KEY"] = monkeypatch_delenv


# ─────────────────────────────────────────────────────────────────────────────
# vendored MapLibre テスト
# ─────────────────────────────────────────────────────────────────────────────

class TestVendoredMaplibre:
    def test_maplibre_js_exists(self):
        """vendored maplibre-gl.js が存在する。"""
        js_path = _VIEWER_DIR / "maplibre-gl.js"
        assert js_path.exists(), f"maplibre-gl.js が見つからない: {js_path}"

    def test_maplibre_js_has_version_header(self):
        """maplibre-gl.js のヘッダに MapLibre GL JS と記述がある。"""
        js_path = _VIEWER_DIR / "maplibre-gl.js"
        first_line = js_path.read_text(encoding="utf-8", errors="ignore").split("\n")[1]
        assert "MapLibre GL JS" in first_line, (
            f"maplibre-gl.js のヘッダに 'MapLibre GL JS' が含まれていない: {first_line!r}"
        )

    def test_maplibre_css_exists(self):
        """vendored maplibre-gl.css が存在する。"""
        css_path = _VIEWER_DIR / "maplibre-gl.css"
        assert css_path.exists(), f"maplibre-gl.css が見つからない: {css_path}"

    def test_licenses_txt_exists(self):
        """LICENSES.txt が存在し MapLibre への言及がある。"""
        lic_path = _VIEWER_DIR / "LICENSES.txt"
        assert lic_path.exists(), f"LICENSES.txt が見つからない: {lic_path}"
        text = lic_path.read_text(encoding="utf-8")
        assert "MapLibre" in text, "LICENSES.txt に MapLibre への言及がない"
        assert "BSD" in text, "LICENSES.txt に BSD ライセンス記述がない"

    @pytest.mark.requires_network_tile
    def test_gsi_tile_url_is_reachable(self):
        """GSI 最適化ベクトルタイルの URL が到達可能 (CI 除外)。

        このテストは実ネットワーク接続が必要なため 'requires_network_tile' マーカーで CI をスキップする。
        """
        import urllib.request
        url = "https://cyberjapandata.gsi.go.jp/xyz/optimal_bvmap-v1/14/14552/6451.pbf"
        try:
            req = urllib.request.urlopen(url, timeout=10)
            assert req.status == 200, f"GSI tile URL が 200 を返さない: {req.status}"
        except Exception as exc:
            pytest.skip(f"GSI tile サーバーに接続できない: {exc}")
