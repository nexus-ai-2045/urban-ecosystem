"""
app/main.py — Cloud Run entrypoint。

正本: docs/ai-ecosystem-tool-spec.md §17 / WO-005 yaml

設計方針:
  - tools.urban_viewer_server で定義済みの FastAPI `app` を import して再利用する。
    エンドポイントの重複実装は禁止 (DRY)。
    WO-003 の 46 テスト (tests/tools/test_urban_viewer_server.py) を壊さない。
  - Cloud Run は $PORT 環境変数を注入する。uvicorn は 0.0.0.0:$PORT に bind する。
  - 秘密情報 (API key / SA key) をコード・ログ・出力に出さない (§17.5 / §5.1.1)。

Cloud Run Job について (§17.1):
  同一イメージを `tools/urban_simulation_cli.py` のエントリポイント差し替えで
  Cloud Run Service (このファイル) / Job (simulation CLI) を兼用する。
  Job のエントリポイントは Dockerfile CMD / --command で上書きする。

識別子は英語 / コメントは日本語。
"""

from __future__ import annotations

import os

# tools.urban_viewer_server の FastAPI app を再利用する (DRY / WO-003 互換)。
# このモジュールは entrypoint のみを担い、エンドポイントを独自定義しない。
from tools.urban_viewer_server import app  # noqa: F401 (re-export)

# ─────────────────────────────────────────────────────────────────────────────
# ローカル起動 / 開発用エントリポイント
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    # Cloud Run は $PORT を注入する (WO-005 yaml notes)。
    # ローカル開発では PORT 未設定 = 8080 にフォールバックする。
    port = int(os.environ.get("PORT", "8080"))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
