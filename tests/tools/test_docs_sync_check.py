"""generated docs drift check の単体テスト。"""

from __future__ import annotations

from pathlib import Path

from tools.docs_sync_check import GENERATED_DOC, check_document, generate_markdown


def test_generated_capabilities_include_current_api_and_settings() -> None:
    markdown = generate_markdown()

    assert "| `POST` | `/api/runs` | `create_run` |" in markdown
    assert "| `POST` | `/api/settings` | `update_settings` |" in markdown
    assert "`activity_plans.jsonl`" in markdown
    assert "`metrics.json`" in markdown
    assert "`LLM_PROVIDER`" in markdown
    assert "`GOOGLE_CLOUD_PROJECT`" in markdown
    assert "`--activity-plans`" in markdown


def test_generated_capabilities_doc_is_in_sync() -> None:
    expected = generate_markdown()

    assert GENERATED_DOC.is_file()
    assert check_document(expected, GENERATED_DOC)


def test_check_document_reports_missing_file_as_drift(tmp_path: Path) -> None:
    missing = tmp_path / "missing.md"

    assert not check_document("expected\n", missing)
