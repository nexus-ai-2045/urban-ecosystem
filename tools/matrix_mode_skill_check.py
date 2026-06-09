#!/usr/bin/env python3
"""MATRIXモード skill index の drift を検出する。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROADMAP = PROJECT_ROOT / "docs" / "matrix-mode-roadmap.md"
SKILL_INDEX = PROJECT_ROOT / "docs" / "matrix-mode-skill-index.md"
ISSUE_TEMPLATE = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE" / "matrix_mode_influence.md"

VALID_TODO_STATUS = {"未着手", "進行中", "完了", "保留"}
REQUIRED_PACKETS = {
    "MM-SAFETY",
    "MM-RUNTIME",
    "MM-VIEWER",
    "MM-MOTIF",
    "MM-BENCH",
    "MM-AUDIO",
    "MM-OPS",
}
REQUIRED_PACKET_SECTIONS = ("Allowed files:", "Stop conditions:", "Tests:")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssertionError(f"required file is missing or unreadable: {path}") from exc


def check() -> list[str]:
    errors: list[str] = []
    roadmap = _read(ROADMAP)
    skill_index = _read(SKILL_INDEX)

    if not ISSUE_TEMPLATE.exists():
        errors.append(f"missing public intake surface: {ISSUE_TEMPLATE}")

    todo_rows = re.findall(r"^\| (M\d+-\d+) \| ([^|]+) \|", roadmap, flags=re.MULTILINE)
    seen_todos = {todo_id for todo_id, _ in todo_rows}
    expected_todos = {f"M{i}-001" for i in range(0, 11)}
    expected_todos.add("M0-002")
    expected_todos.add("M0-003")
    expected_todos.add("M0-004")
    expected_todos.add("M0-005")
    expected_todos.add("M0-006")
    expected_todos.add("M0-007")
    expected_todos.add("M1-002")
    expected_todos.add("M1-003")
    expected_todos.add("M2-002")
    missing_todos = sorted(expected_todos - seen_todos)
    if missing_todos:
        errors.append(f"roadmap TODO rows missing: {', '.join(missing_todos)}")

    for todo_id, status in todo_rows:
        clean_status = status.strip()
        if clean_status not in VALID_TODO_STATUS:
            errors.append(f"{todo_id} has invalid status: {clean_status}")

    m10_row = next((row for row in roadmap.splitlines() if row.startswith("| M10-001 ")), "")
    if "docs/matrix-mode-skill-index.md" not in m10_row:
        errors.append("M10-001 must reference docs/matrix-mode-skill-index.md")
    if "tools/matrix_mode_skill_check.py" not in m10_row:
        errors.append("M10-001 must reference tools/matrix_mode_skill_check.py")

    for packet_id in sorted(REQUIRED_PACKETS):
        heading = f"## {packet_id}"
        if heading not in skill_index:
            errors.append(f"missing packet section: {packet_id}")
            continue
        start = skill_index.index(heading)
        next_heading = skill_index.find("\n## ", start + 1)
        section = skill_index[start:] if next_heading == -1 else skill_index[start:next_heading]
        for required in REQUIRED_PACKET_SECTIONS:
            if required not in section:
                errors.append(f"{packet_id} missing required section: {required}")

    if "1 packet / 1 task / 明示 stop" not in skill_index:
        errors.append("skill index must define bounded dispatch rule")
    if "Changed files" not in skill_index or "Tests run" not in skill_index:
        errors.append("skill index must define expected return fields")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MATRIXモード skill index の drift を検出する")
    parser.add_argument("--check", action="store_true", help="skill index と roadmap の同期を確認する")
    args = parser.parse_args(argv)

    if not args.check:
        parser.print_help()
        return 0

    errors = check()
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
