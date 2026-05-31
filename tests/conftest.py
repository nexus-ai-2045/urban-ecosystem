"""
pytest conftest.py — urban-ecosystem テスト共通設定。

import path を通す: urban-ecosystem ルートから実行した場合も
environments/ が import できるように sys.path を追加する。

注: §18.4 マーカー検証テストは conftest.py だと pytest に収集されないため
tests/test_markers.py へ移設済み (本ファイルには置かない)。
"""

import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
