#!/usr/bin/env python3
"""Generate docs/CHANGELOG.md from git history."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "docs" / "CHANGELOG.md"
SKIP_COMMIT_PREFIXES = {
    "eb6cb36",
}


def git_log() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "log",
            "--first-parent",
            "--date=short",
            "--pretty=format:%ad%x09%h%x09%s",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def touches_private_paths(short_hash: str) -> bool:
    exact_private_paths = {
        "docs/" + "NEXT" + "-SESSION.md",
    }
    private_prefixes = (
        ".githooks/",
        "docs/drafts/",
        "docs/local/",
        "docs/private/",
    )
    result = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", short_hash],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    changed_paths = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return bool(exact_private_paths & changed_paths) or any(
        path.startswith(private_prefixes) for path in changed_paths
    )


def main() -> None:
    lines = [
        "# Changelog",
        "",
        "このファイルは `python tools/generate_changelog.py` で生成します。",
        "手で編集せず、Git履歴から更新してください。",
        "",
        "## Git history",
        "",
    ]

    for line in git_log():
        date, short_hash, subject = line.split("\t", 2)
        if short_hash in SKIP_COMMIT_PREFIXES:
            continue
        if touches_private_paths(short_hash):
            continue
        lines.append(f"- {date} `{short_hash}` {subject}")

    CHANGELOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
