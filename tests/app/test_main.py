"""
tests/app/test_main.py — Cloud Run entrypoint (app.main) のテスト。

正本: docs/subagents/work-orders/wo-urban-005-cloud-run-deploy.yaml §acceptance
仕様参照: docs/ai-ecosystem-tool-spec.md §17 / §5.1.5 fallback / §18

テスト対象:
  - GET /api/health    : 200 / レスポンス形式
  - GET /              : APIキー未設定時 fallback HTML / 500 にならない / キー値非露出
  - GET /api/runs      : 200
  - app/config.py      : PORT 既定 8080

前提:
  - fastapi 未インストール環境ではモジュールごと skip する。
  - GOOGLE_MAPS_API_KEY は設定しない (offline テスト)。
  - /tmp/urban-venv に fastapi 入りの venv を想定して実行する。

識別子は英語 / コメントは日本語。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# fastapi 未インストール環境では本テストモジュールを skip する (WO-005 要件)。
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

# ─── import path を通す ────────────────────────────────────────────────────
# conftest.py (tests/) が PROJECT_ROOT を sys.path に追加済みだが、
# tests/app/ サブパッケージから直接 pytest を起動した場合も確実に通す。
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# app.main から app を import する (Cloud Run entrypoint 経由で確認)。
from app.main import app  # noqa: E402
from app.config import DEFAULT_PORT, get_port  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# テストクライアント
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """TestClient を返す。GOOGLE_MAPS_API_KEY は設定しない (fallback 経路)。"""
    # API キーを確実に未設定にする
    os.environ.pop("GOOGLE_MAPS_API_KEY", None)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# /api/health
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    """GET /api/health のテスト。"""

    def test_status_200(self, client: TestClient) -> None:
        """ヘルスチェックは 200 を返す。"""
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_response_has_status_ok(self, client: TestClient) -> None:
        """`status` フィールドが "ok" であること。"""
        resp = client.get("/api/health")
        data = resp.json()
        assert data.get("status") == "ok"

    def test_maps_key_absent_when_not_set(self, client: TestClient) -> None:
        """APIキー未設定時は maps_key が "absent" を返す (値は返さない)。"""
        os.environ.pop("GOOGLE_MAPS_API_KEY", None)
        resp = client.get("/api/health")
        data = resp.json()
        assert data.get("maps_key") == "absent"

    def test_response_body_does_not_contain_key_value(self, client: TestClient) -> None:
        """レスポンスボディに "GOOGLE_MAPS_API_KEY" という文字列を含まない。

        誤って env 変数名ごと露出していないことを確認する。
        """
        resp = client.get("/api/health")
        assert "GOOGLE_MAPS_API_KEY" not in resp.text


# ─────────────────────────────────────────────────────────────────────────────
# GET /  (fallback HTML)
# ─────────────────────────────────────────────────────────────────────────────

class TestRoot:
    """GET / のテスト。APIキー未設定 = fallback 経路。"""

    def test_not_500_when_no_api_key(self, client: TestClient) -> None:
        """GOOGLE_MAPS_API_KEY 未設定でも 500 を返さない (§5.1.5 / §17.4)。

        WO-005 acceptance: fallback HTML を返す。
        """
        os.environ.pop("GOOGLE_MAPS_API_KEY", None)
        resp = client.get("/")
        assert resp.status_code != 500
        # 200 か 302 相当であること (HTML が返る)
        assert resp.status_code < 400

    def test_returns_html_content_type(self, client: TestClient) -> None:
        """レスポンスの Content-Type が text/html を含む。"""
        resp = client.get("/")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_fallback_html_does_not_expose_maps_googleapis(self, client: TestClient) -> None:
        """APIキー未設定時の HTML が maps.googleapis.com の URL を含まない。

        fallback 経路では Maps bootstrap loader を出力しない (§5.1.1 / §5.1.5)。
        WO-005 acceptance: 「出力に maps.googleapis.com を含まない」を機械検証する。
        """
        os.environ.pop("GOOGLE_MAPS_API_KEY", None)
        resp = client.get("/")
        # ボディ文字列に Maps CDN URL が含まれないことを確認
        assert "maps.googleapis.com" not in resp.text


# ─────────────────────────────────────────────────────────────────────────────
# /api/runs
# ─────────────────────────────────────────────────────────────────────────────

class TestRuns:
    """GET /api/runs のテスト。"""

    def test_status_200(self, client: TestClient) -> None:
        """runs エンドポイントは 200 を返す。run が 0 件でも 4xx/5xx にならない。"""
        resp = client.get("/api/runs")
        assert resp.status_code == 200

    def test_response_has_runs_key(self, client: TestClient) -> None:
        """レスポンスボディに 'runs' キーが含まれる。"""
        resp = client.get("/api/runs")
        data = resp.json()
        assert "runs" in data

    def test_runs_is_list(self, client: TestClient) -> None:
        """runs の値はリスト型である。"""
        resp = client.get("/api/runs")
        data = resp.json()
        assert isinstance(data["runs"], list)


# ─────────────────────────────────────────────────────────────────────────────
# config: PORT 既定値
# ─────────────────────────────────────────────────────────────────────────────

class TestConfig:
    """app.config の環境変数集約のテスト。"""

    def test_default_port_is_8080(self) -> None:
        """PORT 未設定時のデフォルトは 8080 (WO-005 acceptance)。"""
        assert DEFAULT_PORT == 8080

    def test_get_port_returns_8080_when_env_unset(self) -> None:
        """PORT 環境変数が未設定の場合、get_port() は 8080 を返す。"""
        os.environ.pop("PORT", None)
        assert get_port() == 8080

    def test_get_port_respects_env_variable(self) -> None:
        """PORT 環境変数が設定されていれば、get_port() はその値を返す。"""
        os.environ["PORT"] = "9090"
        try:
            assert get_port() == 9090
        finally:
            os.environ.pop("PORT", None)

    def test_get_port_fallback_on_invalid_value(self) -> None:
        """PORT に非整数が設定された場合、get_port() は 8080 にフォールバックする。"""
        os.environ["PORT"] = "not_a_number"
        try:
            assert get_port() == 8080
        finally:
            os.environ.pop("PORT", None)


# ─────────────────────────────────────────────────────────────────────────────
# /api/labels (WO-010)
# ─────────────────────────────────────────────────────────────────────────────

class TestLabels:
    """GET /api/labels — app.main 経由でラベルエンドポイントが稼働すること。"""

    def test_status_200(self, client: TestClient) -> None:
        """/api/labels は 200 を返す。"""
        resp = client.get("/api/labels")
        assert resp.status_code == 200

    def test_response_has_category_section(self, client: TestClient) -> None:
        """レスポンスに category セクションが含まれる。"""
        resp = client.get("/api/labels")
        data = resp.json()
        assert "category" in data

    def test_category_cafe_is_japanese(self, client: TestClient) -> None:
        """amenity-cafe のラベルが日本語 (カフェ) である。"""
        resp = client.get("/api/labels")
        data = resp.json()
        assert data["category"].get("amenity-cafe") == "カフェ"

    def test_role_office_worker_is_japanese(self, client: TestClient) -> None:
        """office_worker のラベルが日本語 (会社員) である。"""
        resp = client.get("/api/labels")
        data = resp.json()
        assert data["role"].get("office_worker") == "会社員"
