from pathlib import Path

from tools import matrix_mode_skill_check


def test_matrix_mode_skill_check_current_repo_passes():
    assert matrix_mode_skill_check.check() == []


def test_matrix_mode_skill_check_detects_missing_packet_section(monkeypatch, tmp_path):
    roadmap = tmp_path / "matrix-mode-roadmap.md"
    index = tmp_path / "matrix-mode-skill-index.md"
    issue_template = tmp_path / "matrix_mode_influence.md"

    roadmap.write_text(
        "\n".join([
            "| M0-001 | 完了 | x | y | z |",
            "| M0-002 | 完了 | x | y | z |",
            "| M0-003 | 完了 | x | y | z |",
            "| M0-004 | 完了 | x | y | z |",
            "| M0-005 | 完了 | x | y | z |",
            "| M0-006 | 完了 | x | y | z |",
            "| M0-007 | 完了 | x | y | z |",
            "| M1-001 | 完了 | x | y | z |",
            "| M1-002 | 完了 | x | y | z |",
            "| M1-003 | 完了 | x | y | z |",
            "| M2-001 | 完了 | x | y | z |",
            "| M2-002 | 完了 | x | y | z |",
            "| M3-001 | 完了 | x | y | z |",
            "| M4-001 | 完了 | x | y | z |",
            "| M5-001 | 完了 | x | y | z |",
            "| M6-001 | 完了 | x | y | z |",
            "| M7-001 | 完了 | x | y | z |",
            "| M8-001 | 完了 | x | y | z |",
            "| M9-001 | 完了 | x | y | z |",
            "| M10-001 | 完了 | x | y | docs/matrix-mode-skill-index.md / tools/matrix_mode_skill_check.py |",
        ]),
        encoding="utf-8",
    )
    index.write_text(
        "\n".join([
            "1 packet / 1 task / 明示 stop",
            "Changed files",
            "Tests run",
            "## MM-SAFETY",
            "Allowed files:",
            "Stop conditions:",
            "## MM-RUNTIME",
            "Allowed files:",
            "Stop conditions:",
            "Tests:",
            "## MM-VIEWER",
            "Allowed files:",
            "Stop conditions:",
            "Tests:",
            "## MM-MOTIF",
            "Allowed files:",
            "Stop conditions:",
            "Tests:",
            "## MM-BENCH",
            "Allowed files:",
            "Stop conditions:",
            "Tests:",
            "## MM-AUDIO",
            "Allowed files:",
            "Stop conditions:",
            "Tests:",
            "## MM-OPS",
            "Allowed files:",
            "Stop conditions:",
            "Tests:",
        ]),
        encoding="utf-8",
    )
    issue_template.write_text("issue", encoding="utf-8")

    monkeypatch.setattr(matrix_mode_skill_check, "ROADMAP", roadmap)
    monkeypatch.setattr(matrix_mode_skill_check, "SKILL_INDEX", index)
    monkeypatch.setattr(matrix_mode_skill_check, "ISSUE_TEMPLATE", issue_template)

    errors = matrix_mode_skill_check.check()
    assert "MM-SAFETY missing required section: Tests:" in errors
