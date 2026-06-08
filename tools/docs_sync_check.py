"""
docs_sync_check.py — 実装から生成した capabilities docs の drift を検出する。

このツールは docs/generated/current-capabilities.md を生成し、committed docs が
現在の API / CLI / data allowlist と一致しているか確認する。
"""

from __future__ import annotations

import argparse
import difflib
import inspect
import re
import sys
from pathlib import Path

from fastapi.routing import APIRoute


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.urban_simulation_cli import build_parser
from tools.urban_viewer_server import ALLOWED_FILES, AGENT_PROFILES_RE, SUPPORTED_DATA_SOURCES, app


GENERATED_DOC = PROJECT_ROOT / "docs" / "generated" / "current-capabilities.md"

CROSS_WORLD_CORE_DOCS = [
    PROJECT_ROOT / "docs" / "cross-world-operator-roadmap.md",
    PROJECT_ROOT / "docs" / "cross-world-operator-roadmap.html",
    PROJECT_ROOT / "docs" / "cross-world-operator-todo.md",
    PROJECT_ROOT / "docs" / "cross-world-operator-linear-drafts.md",
]

CROSS_WORLD_README_LINKS = [
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
    "docs/cross-world-operator-mvp-007-repo-skill-distributed-ops.md",
    "docs/cross-world-operator-mvp-008-intake-lifecycle-worldbuilding.md",
]

CROSS_WORLD_SCAN_TERMS = [
    "Mat" "rix",
    "N" "eo",
    "Agent " "Sm" "ith",
    "Sm" "ith",
    "Jo" "nes",
    "Br" "own",
    "John" "son",
    "Jack" "son",
    "Thomp" "son",
    "Mor" "pheus",
    "Tri" "nity",
    "Kusa" "nagi",
    "Ba" "tou",
    "Ara" "maki",
    "Sai" "to",
    "Ex " "Mach" "ina",
    "Three " "Body",
    "Your " "Name",
    "Miya" "zaki",
    "GT" "R",
    "VT" "uber",
    "Full" "metal",
    "Demon " "Slayer",
    "AK" "IRA",
    "Attack " "on " "Titan",
    "Street " "Fighter",
    "Black " "Mirror",
    "Death " "Note",
    "Nau" "sicaa",
    "Ev" "a",
    "Ev" "angelion",
    "Shin" "ji",
    "R" "ei",
    "As" "uka",
    "qv" "eria",
    "Qv" "eria",
    "ka2" "aki86",
    "2063665" "137991762380",
    "x" ".com",
    "twitter" ".com",
    "C:" r"\\Users",
    "Desk" "top",
    "Ob" "sidian",
    "Discord" "投稿本文",
]
CROSS_WORLD_SCAN_PATTERN = re.compile("|".join(re.escape(term) for term in CROSS_WORLD_SCAN_TERMS))


def _first_doc_line(callable_obj: object) -> str:
    doc = inspect.getdoc(callable_obj)
    if not doc:
        return ""
    return doc.splitlines()[0].strip()


def _api_rows() -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = sorted(method for method in route.methods if method not in {"HEAD", "OPTIONS"})
        if not methods:
            continue
        if not (route.path == "/" or route.path.startswith("/api/")):
            continue
        description = _first_doc_line(route.endpoint)
        rows.append((", ".join(methods), route.path, route.name, description))
    return sorted(rows, key=lambda row: (row[1], row[0], row[2]))


def _cli_run_flags() -> list[tuple[str, str, str]]:
    parser = build_parser()
    subparsers_action = next(
        action for action in parser._actions  # noqa: SLF001 - argparse has no public subparser iterator.
        if isinstance(action, argparse._SubParsersAction)  # noqa: SLF001
    )
    run_parser = subparsers_action.choices["run"]
    rows: list[tuple[str, str, str]] = []
    for action in run_parser._actions:  # noqa: SLF001 - argparse stores option metadata here.
        option = next((opt for opt in action.option_strings if opt.startswith("--")), "")
        if not option:
            continue
        if option == "--help":
            continue
        default = "" if action.default is None else str(action.default)
        rows.append((option, default, action.help or ""))
    return sorted(rows, key=lambda row: row[0])


def _settings_rows() -> list[tuple[str, str, str]]:
    return [
        ("GOOGLE_MAPS_API_KEY", "maps.api_key", "Google Maps JS API key。GET /api/settings は実値を返さず present/absent のみ返す。"),
        ("GOOGLE_MAPS_MAP_ID", "maps.map_id", "Google Maps Map ID。DEMO_MAP_ID は UI へ実値表示しない。"),
        ("DATA_SOURCE", "data.source", "現在の実装済み値は local のみ。"),
        ("DATA_DIR", "data.root", "run directory を探すローカル data root。"),
        ("LLM_PROVIDER", "llm.provider", "rule / local / vertex。"),
        ("LLM_MODEL", "llm.model", "local / cloud provider の model identifier。"),
        ("LLM_BASE_URL", "llm.base_url", "local OpenAI-compatible endpoint。"),
        ("LLM_MODEL_DIR", "llm.model_dir", "local model path fallback。"),
        ("GOOGLE_CLOUD_PROJECT", "cloud.google_cloud_project", "Vertex AI 利用時の Google Cloud project。"),
    ]


def generate_markdown() -> str:
    lines: list[str] = [
        "# Current Capabilities",
        "",
        "このファイルは `tools/docs_sync_check.py` で生成する。手で直さない。",
        "実装を変えたら `python tools/docs_sync_check.py --write` で更新する。",
        "",
        "## Viewer API",
        "",
        "| Method | Path | Handler | Summary |",
        "| --- | --- | --- | --- |",
    ]

    for method, path, handler, summary in _api_rows():
        lines.append(f"| `{method}` | `{path}` | `{handler}` | {summary} |")

    lines.extend([
        "",
        "## Data File Allowlist",
        "",
        "生成元: `tools/urban_viewer_server.py` の `ALLOWED_FILES` / `AGENT_PROFILES_RE`。",
        "",
        "| File | Mode |",
        "| --- | --- |",
    ])
    for filename in sorted(ALLOWED_FILES):
        lines.append(f"| `{filename}` | exact |")
    lines.append(f"| `{AGENT_PROFILES_RE.pattern}` | regex |")

    lines.extend([
        "",
        "## Runtime Settings",
        "",
        "`POST /api/settings` は process-local 更新のみ行う。`.env`、OS keychain、Secret Manager には保存しない。",
        "",
        "| Env Var | Settings Field | Note |",
        "| --- | --- | --- |",
    ])
    for env_var, field, note in _settings_rows():
        lines.append(f"| `{env_var}` | `{field}` | {note} |")

    lines.extend([
        "",
        "## Supported Data Sources",
        "",
        "| Value | Status |",
        "| --- | --- |",
    ])
    for source in sorted(SUPPORTED_DATA_SOURCES):
        lines.append(f"| `{source}` | implemented |")

    lines.extend([
        "",
        "## Simulation CLI: `run`",
        "",
        "| Flag | Default | Help |",
        "| --- | --- | --- |",
    ])
    for option, default, help_text in _cli_run_flags():
        lines.append(f"| `{option}` | `{default}` | {help_text} |")

    lines.extend([
        "",
        "## Drift Gate",
        "",
        "CI は `python tools/docs_sync_check.py --check` を実行する。",
        "このファイルが実装から再生成した内容と一致しない場合、PR は docs drift として失敗する。",
        "",
    ])
    return "\n".join(lines)


def check_document(expected: str, path: Path = GENERATED_DOC) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if current == expected:
        return True
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile=str(path),
        tofile=f"{path} (generated)",
    )
    sys.stderr.writelines(diff)
    return False


def write_document(content: str, path: Path = GENERATED_DOC) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _cross_world_version(path: Path) -> str:
    text = _read(path)
    if path.suffix == ".html":
        match = re.search(r"Version:\s*([0-9]+\.[0-9]+\.[0-9]+)", text)
    else:
        match = re.search(r"^- Version: `([^`]+)`", text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def cross_world_drift_errors(project_root: Path = PROJECT_ROOT) -> list[str]:
    errors: list[str] = []
    readme = _read(project_root / "README.md")

    for link in CROSS_WORLD_README_LINKS:
        if f"]({link})" not in readme:
            errors.append(f"README.md missing Cross-world link: {link}")
        if not (project_root / link).is_file():
            errors.append(f"Cross-world linked file missing: {link}")

    version_paths = [
        project_root / "docs" / "cross-world-operator-roadmap.md",
        project_root / "docs" / "cross-world-operator-roadmap.html",
        project_root / "docs" / "cross-world-operator-todo.md",
        project_root / "docs" / "cross-world-operator-linear-drafts.md",
    ]
    versions = {path.relative_to(project_root).as_posix(): _cross_world_version(path) for path in version_paths}
    if any(not version for version in versions.values()):
        errors.append(f"Cross-world version missing: {versions}")
    if len(set(versions.values())) != 1:
        errors.append(f"Cross-world version mismatch: {versions}")

    todo = _read(project_root / "docs" / "cross-world-operator-todo.md")
    missing_todos = [f"XWORLD-TODO-{index:03d}" for index in range(1, 40) if f"XWORLD-TODO-{index:03d}" not in todo]
    if missing_todos:
        errors.append(f"Cross-world TODO missing: {', '.join(missing_todos)}")

    linear = _read(project_root / "docs" / "cross-world-operator-linear-drafts.md")
    missing_mvps = [f"UE-XWORLD-MVP-{index:03d}" for index in range(0, 9) if f"UE-XWORLD-MVP-{index:03d}" not in linear]
    if missing_mvps:
        errors.append(f"Cross-world MVP missing: {', '.join(missing_mvps)}")

    required_linear_links = [
        "cross-world-operator-mvp-001-sentinel-entry.md",
        "wo-urban-020-cross-world-sentinel-entry.yaml",
        "wo-urban-028-cross-world-sentinel-entry-prototype.yaml",
        "cross-world-operator-mvp-002-world-bridge.md",
        "wo-urban-021-cross-world-bridge-state-model.yaml",
        "wo-urban-029-cross-world-world-bridge-prototype.yaml",
        "cross-world-operator-mvp-003-guide-agent-roster.md",
        "wo-urban-022-cross-world-guide-agent-roster.yaml",
        "wo-urban-030-cross-world-guide-roster-prototype.yaml",
        "cross-world-operator-mvp-004-motif-arc-pack.md",
        "wo-urban-023-cross-world-motif-arc-pack.yaml",
        "wo-urban-031-cross-world-motif-arc-prototype.yaml",
        "cross-world-operator-mvp-005-assessment-benchmark-lab.md",
        "wo-urban-024-cross-world-assessment-benchmark-lab.yaml",
        "cross-world-operator-mvp-006-governance-fractal-decision.md",
        "wo-urban-025-cross-world-governance-fractal-decision.yaml",
        "cross-world-operator-mvp-007-repo-skill-distributed-ops.md",
        "wo-urban-026-cross-world-repo-skill-distributed-ops.yaml",
        "cross-world-operator-mvp-008-intake-lifecycle-worldbuilding.md",
        "wo-urban-027-cross-world-intake-lifecycle-worldbuilding.yaml",
    ]
    for link in required_linear_links:
        if link not in linear:
            errors.append(f"Linear draft missing artifact/work-order link: {link}")

    scan_paths = CROSS_WORLD_CORE_DOCS + [
        project_root / "docs" / "cross-world-operator-mvp-001-sentinel-entry.md",
        project_root / "docs" / "cross-world-operator-mvp-002-world-bridge.md",
        project_root / "docs" / "cross-world-operator-mvp-003-guide-agent-roster.md",
        project_root / "docs" / "cross-world-operator-mvp-004-motif-arc-pack.md",
        project_root / "docs" / "cross-world-operator-mvp-005-assessment-benchmark-lab.md",
        project_root / "docs" / "cross-world-operator-mvp-006-governance-fractal-decision.md",
        project_root / "docs" / "cross-world-operator-mvp-007-repo-skill-distributed-ops.md",
        project_root / "docs" / "cross-world-operator-mvp-008-intake-lifecycle-worldbuilding.md",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-020-cross-world-sentinel-entry.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-021-cross-world-bridge-state-model.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-022-cross-world-guide-agent-roster.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-023-cross-world-motif-arc-pack.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-024-cross-world-assessment-benchmark-lab.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-025-cross-world-governance-fractal-decision.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-026-cross-world-repo-skill-distributed-ops.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-027-cross-world-intake-lifecycle-worldbuilding.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-028-cross-world-sentinel-entry-prototype.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-029-cross-world-world-bridge-prototype.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-030-cross-world-guide-roster-prototype.yaml",
        project_root / "docs" / "subagents" / "work-orders" / "wo-urban-031-cross-world-motif-arc-prototype.yaml",
    ]
    for path in scan_paths:
        text = _read(path)
        match = CROSS_WORLD_SCAN_PATTERN.search(text)
        if match:
            errors.append(f"Cross-world protected/private term in {path.relative_to(project_root).as_posix()}: {match.group(0)}")

    return errors


def check_cross_world_docs(project_root: Path = PROJECT_ROOT) -> bool:
    errors = cross_world_drift_errors(project_root)
    if not errors:
        return True
    for error in errors:
        print(error, file=sys.stderr)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="generated docs の drift を検出する")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="生成結果と committed docs の一致を確認する")
    group.add_argument("--write", action="store_true", help="生成結果で docs/generated/current-capabilities.md を更新する")
    args = parser.parse_args(argv)

    content = generate_markdown()
    if args.write:
        write_document(content)
        return 0
    if not check_document(content):
        return 1
    if not check_cross_world_docs():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
