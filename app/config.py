"""
app/config.py — Cloud Run 環境変数の集約モジュール。

正本: docs/ai-ecosystem-tool-spec.md §17.4 / §17.5

設計方針:
  - 環境変数の存在確認 (present/absent) のみを公開する。
    GOOGLE_MAPS_API_KEY の値は呼び出し側に渡さない (§17.5 / §5.1.1)。
  - 値を直接返す場合は DATA_DIR / DATA_SOURCE / PORT のみとし、
    秘密情報 (API key / SA key) は一切返さない。
  - ログ・print に秘密値を出力しない。

識別子は英語 / コメントは日本語。
"""

from __future__ import annotations

import os

# ─────────────────────────────────────────────────────────────────────────────
# ポート
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_PORT: int = 8080


def get_port() -> int:
    """Cloud Run が注入する $PORT 環境変数を返す。未設定時は 8080。

    Cloud Run は起動時に $PORT を注入する (WO-005 yaml notes)。
    """
    raw = os.environ.get("PORT", str(DEFAULT_PORT))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PORT


# ─────────────────────────────────────────────────────────────────────────────
# Google Maps API Key (present/absent 判定のみ / 値は返さない)
# ─────────────────────────────────────────────────────────────────────────────

def is_maps_api_key_present() -> bool:
    """GOOGLE_MAPS_API_KEY が環境変数に設定されているかを返す。

    値は返さない。ログにも出力しない (§17.5 / §5.1.1)。
    """
    return bool(os.environ.get("GOOGLE_MAPS_API_KEY", ""))


# ─────────────────────────────────────────────────────────────────────────────
# データ取得経路
# ─────────────────────────────────────────────────────────────────────────────

def get_data_source() -> str:
    """DATA_SOURCE 環境変数 ('local' | 'gcs') を返す。デフォルト 'local'。

    §17.2: local=同梱パス / gcs=GCS SDK 経由 (スケール時)。
    """
    return os.environ.get("DATA_SOURCE", "local")


def get_data_dir() -> str:
    """DATA_DIR 環境変数を返す。未設定時は空文字列。

    呼び出し側は空文字列の場合にデフォルトパス (data/) を使う。
    """
    return os.environ.get("DATA_DIR", "")
