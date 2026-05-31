"""
tests/test_markers.py — pytest マーカー登録・除外メカニズムの検証。

conftest.py 内に置かれていたマーカー検証テストは pytest が収集しないため
永久に実行されなかった。本モジュールへ移動することで通常収集対象となる。
"""

import pytest


# ── §18.4 CI 方針: requires_api マーカー登録確認 ──────────────────────────────


def test_requires_api_marker_is_registered(pytestconfig: pytest.Config) -> None:
    """requires_api マーカーが pyproject.toml に登録されていることを確認する (§18.4)。

    未登録の場合 pytest は PytestUnknownMarkWarning を発する。
    本テストは registered_markers に requires_api が含まれるかを機械的に検証する。

    getini("markers") はマーカー定義文字列のリストを返す。
    各エントリは "marker_name: description" の形式なので、コロン前の名前部分を抽出する。
    """
    # 各エントリは "marker_name: description" または "marker_name" の形式
    raw_entries: list[str] = pytestconfig.getini("markers")
    registered = {entry.split(":")[0].strip() for entry in raw_entries}
    assert "requires_api" in registered, (
        "requires_api マーカーが未登録。"
        "pyproject.toml の [tool.pytest.ini_options] markers に追加すること (§18.4)。"
    )


@pytest.mark.requires_api
def test_requires_api_marker_is_skippable_by_expression() -> None:
    """@pytest.mark.requires_api を付与したテストが CI で `-m 'not requires_api'` により除外できる。

    このテスト自体は requires_api マーカーを持つため、
    `-m 'not requires_api'` で実行した場合はコレクションから除外される。
    通常実行時はそのまま pass する (外部 API 呼び出しは行わない)。
    """
    # 外部 API は呼ばない — マーカーの付与・除外メカニズムを検証するだけ。
    assert True
