"""generated docs drift check の単体テスト。"""

from __future__ import annotations

from pathlib import Path

from tools.docs_sync_check import (
    GENERATED_DOC,
    check_cross_world_docs,
    check_document,
    cross_world_drift_errors,
    generate_markdown,
)


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


def test_cross_world_docs_are_in_sync() -> None:
    assert check_cross_world_docs()


def test_cross_world_drift_detects_missing_readme_link(tmp_path: Path) -> None:
    _write_minimal_cross_world_tree(tmp_path)
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    (tmp_path / "README.md").write_text(
        readme.replace("](docs/cross-world-operator-roadmap.html)", "](docs/missing-roadmap.html)"),
        encoding="utf-8",
    )

    errors = cross_world_drift_errors(tmp_path)

    assert any("README.md missing Cross-world link" in error for error in errors)


def test_cross_world_drift_detects_version_mismatch(tmp_path: Path) -> None:
    _write_minimal_cross_world_tree(tmp_path)
    todo = tmp_path / "docs" / "cross-world-operator-todo.md"
    todo.write_text(todo.read_text(encoding="utf-8").replace("- Version: `0.1.7`", "- Version: `0.1.6`"), encoding="utf-8")

    errors = cross_world_drift_errors(tmp_path)

    assert any("Cross-world version mismatch" in error for error in errors)


def test_cross_world_drift_detects_todo_and_mvp_gaps(tmp_path: Path) -> None:
    _write_minimal_cross_world_tree(tmp_path)
    todo = tmp_path / "docs" / "cross-world-operator-todo.md"
    linear = tmp_path / "docs" / "cross-world-operator-linear-drafts.md"
    todo.write_text(todo.read_text(encoding="utf-8").replace("XWORLD-TODO-039", "XWORLD-TODO-999"), encoding="utf-8")
    linear.write_text(linear.read_text(encoding="utf-8").replace("UE-XWORLD-MVP-008", "UE-XWORLD-MVP-999"), encoding="utf-8")

    errors = cross_world_drift_errors(tmp_path)

    assert any("XWORLD-TODO-039" in error for error in errors)
    assert any("UE-XWORLD-MVP-008" in error for error in errors)


def _write_minimal_cross_world_tree(root: Path) -> None:
    docs = root / "docs"
    work_orders = docs / "subagents" / "work-orders"
    work_orders.mkdir(parents=True)

    links = [
        "docs/cross-world-operator-roadmap.html",
        "docs/cross-world-operator-todo.html",
        "docs/cross-world-operator-roadmap.md",
        "docs/cross-world-operator-todo.md",
        "docs/cross-world-operator-linear-drafts.md",
        "docs/cross-world-operator-mvp-001-sentinel-entry.md",
        "docs/cross-world-operator-mvp-002-world-bridge.md",
        "docs/cross-world-operator-mvp-003-guide-agent-roster.md",
        "docs/cross-world-operator-mvp-004-motif-arc-pack.md",
        "docs/cross-world-operator-mvp-005-assessment-benchmark-lab.md",
        "docs/cross-world-operator-mvp-006-governance-fractal-decision.md",
    ]
    (root / "README.md").write_text(
        "\n".join(f"- [{link}]({link})" for link in links),
        encoding="utf-8",
    )

    (docs / "cross-world-operator-roadmap.md").write_text("- Version: `0.1.7`\n", encoding="utf-8")
    (docs / "cross-world-operator-roadmap.html").write_text("<span>Version: 0.1.7</span>\n", encoding="utf-8")
    (docs / "cross-world-operator-todo.html").write_text("<html></html>\n", encoding="utf-8")
    (docs / "cross-world-operator-todo.md").write_text(
        "- Version: `0.1.7`\n" + "\n".join(f"XWORLD-TODO-{index:03d}" for index in range(1, 40)),
        encoding="utf-8",
    )
    (docs / "cross-world-operator-linear-drafts.md").write_text(
        "- Version: `0.1.7`\n"
        + "\n".join(f"UE-XWORLD-MVP-{index:03d}" for index in range(0, 9))
        + "\ncross-world-operator-mvp-001-sentinel-entry.md\n"
        + "wo-urban-020-cross-world-sentinel-entry.yaml\n"
        + "cross-world-operator-mvp-002-world-bridge.md\n"
        + "wo-urban-021-cross-world-bridge-state-model.yaml\n"
        + "cross-world-operator-mvp-003-guide-agent-roster.md\n"
        + "wo-urban-022-cross-world-guide-agent-roster.yaml\n"
        + "cross-world-operator-mvp-004-motif-arc-pack.md\n"
        + "wo-urban-023-cross-world-motif-arc-pack.yaml\n"
        + "cross-world-operator-mvp-005-assessment-benchmark-lab.md\n"
        + "wo-urban-024-cross-world-assessment-benchmark-lab.yaml\n"
        + "cross-world-operator-mvp-006-governance-fractal-decision.md\n"
        + "wo-urban-025-cross-world-governance-fractal-decision.yaml\n",
        encoding="utf-8",
    )
    (docs / "cross-world-operator-mvp-001-sentinel-entry.md").write_text("MVP-001\n", encoding="utf-8")
    (docs / "cross-world-operator-mvp-002-world-bridge.md").write_text("MVP-002\n", encoding="utf-8")
    (docs / "cross-world-operator-mvp-003-guide-agent-roster.md").write_text("MVP-003\n", encoding="utf-8")
    (docs / "cross-world-operator-mvp-004-motif-arc-pack.md").write_text("MVP-004\n", encoding="utf-8")
    (docs / "cross-world-operator-mvp-005-assessment-benchmark-lab.md").write_text("MVP-005\n", encoding="utf-8")
    (docs / "cross-world-operator-mvp-006-governance-fractal-decision.md").write_text("MVP-006\n", encoding="utf-8")
    (work_orders / "wo-urban-020-cross-world-sentinel-entry.yaml").write_text("id: wo-urban-020\n", encoding="utf-8")
    (work_orders / "wo-urban-021-cross-world-bridge-state-model.yaml").write_text("id: wo-urban-021\n", encoding="utf-8")
    (work_orders / "wo-urban-022-cross-world-guide-agent-roster.yaml").write_text("id: wo-urban-022\n", encoding="utf-8")
    (work_orders / "wo-urban-023-cross-world-motif-arc-pack.yaml").write_text("id: wo-urban-023\n", encoding="utf-8")
    (work_orders / "wo-urban-024-cross-world-assessment-benchmark-lab.yaml").write_text("id: wo-urban-024\n", encoding="utf-8")
    (work_orders / "wo-urban-025-cross-world-governance-fractal-decision.yaml").write_text("id: wo-urban-025\n", encoding="utf-8")
