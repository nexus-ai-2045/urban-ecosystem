"""
docs_sync_check.py — 実装から生成した capabilities docs の drift を検出する。

このツールは docs/generated/current-capabilities.md を生成し、committed docs が
現在の API / CLI / data allowlist と一致しているか確認する。
"""

from __future__ import annotations

import argparse
import difflib
import inspect
import sys
from pathlib import Path

from fastapi.routing import APIRoute

from tools.urban_simulation_cli import build_parser
from tools.urban_viewer_server import ALLOWED_FILES, AGENT_PROFILES_RE, SUPPORTED_DATA_SOURCES, app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DOC = PROJECT_ROOT / "docs" / "generated" / "current-capabilities.md"


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
