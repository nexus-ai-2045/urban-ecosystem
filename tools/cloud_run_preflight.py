"""Cloud Run deploy 前の local-only preflight。

NEX-29 の承認ゲート用に、GCP / Cloud Run / Secret Manager / Google Maps /
Vertex AI を実行せず、ローカルで確認できる evidence を出力する。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SENSITIVE_ENV_KEYS = (
    "GOOGLE_MAPS_API_KEY",
    "GOOGLE_PLACES_API_KEY",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "VERTEX_AI_PROJECT",
    "DEPLOY_PROJECT",
)

REQUIRED_FILES = (
    "Dockerfile",
    "cloudbuild.yaml",
    "app/main.py",
    "app/config.py",
    "tools/smoke_fallback_viewer.py",
    "docs/deploy.md",
)

DEPLOY_DOC_REQUIRED_MARKERS = (
    "maintainer の明示承認",
    "Secret Manager",
    "--allow-unauthenticated",
    "auto mode での自動実行は禁止",
)

FORBIDDEN_REMOTE_COMMANDS = (
    "gcloud",
    "gsutil",
    "docker push",
    "cloudbuild",
)

REQUIRED_PYTHON_MODULES = (
    "fastapi",
    "uvicorn",
)


@dataclass(frozen=True)
class PreflightOptions:
    issue: str
    run_smoke: bool
    smoke_port: int
    smoke_agents: int
    smoke_seed: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def local_only_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Child process 用 env。GCP / Secret 系の値は引き継がない。"""
    env = dict(os.environ if base_env is None else base_env)
    for key in SENSITIVE_ENV_KEYS:
        env.pop(key, None)
    env["DATA_SOURCE"] = "local"
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _file_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for rel_path in REQUIRED_FILES:
        path = PROJECT_ROOT / rel_path
        checks.append(
            {
                "name": f"required file: {rel_path}",
                "status": "ok" if path.exists() else "fail",
                "path": rel_path,
            }
        )
    return checks


def _deploy_doc_checks() -> list[dict[str, Any]]:
    path = PROJECT_ROOT / "docs" / "deploy.md"
    if not path.exists():
        return [
            {
                "name": "deploy doc approval gate markers",
                "status": "fail",
                "path": "docs/deploy.md",
                "missing": list(DEPLOY_DOC_REQUIRED_MARKERS),
            }
        ]

    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in DEPLOY_DOC_REQUIRED_MARKERS if marker not in text]
    return [
        {
            "name": "deploy doc approval gate markers",
            "status": "ok" if not missing else "fail",
            "path": "docs/deploy.md",
            "missing": missing,
        }
    ]


def _environment_checks(env: dict[str, str]) -> list[dict[str, Any]]:
    present = [key for key in SENSITIVE_ENV_KEYS if key in env]
    return [
        {
            "name": "preflight child env has no GCP or secret keys",
            "status": "ok" if not present else "fail",
            "removed_keys": [key for key in SENSITIVE_ENV_KEYS if key not in env],
            "unexpected_present_keys": present,
        }
    ]


def _python_dependency_checks(env: dict[str, str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for module in REQUIRED_PYTHON_MODULES:
        completed = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        checks.append(
            {
                "name": f"python module import: {module}",
                "status": "ok" if completed.returncode == 0 else "fail",
                "python": sys.executable,
                "stderr_tail": completed.stderr[-1000:],
            }
        )
    return checks


def _tooling_boundary_checks() -> list[dict[str, Any]]:
    docker_path = shutil.which("docker")
    return [
        {
            "name": "local Docker is optional for this preflight",
            "status": "ok",
            "required": False,
            "available": bool(docker_path),
            "path": docker_path,
            "reason": "local-only preflight uses Python smoke; Cloud Run --source builds remotely with Cloud Build.",
        }
    ]


def _run_fallback_smoke(options: PreflightOptions, env: dict[str, str]) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "tools/smoke_fallback_viewer.py",
        "--port",
        str(options.smoke_port),
        "--agents",
        str(options.smoke_agents),
        "--seed",
        str(options.smoke_seed),
    ]
    completed = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "name": "fallback viewer smoke",
        "status": "ok" if completed.returncode == 0 else "fail",
        "command": " ".join(cmd),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def run_preflight(options: PreflightOptions) -> dict[str, Any]:
    child_env = local_only_env()
    checks: list[dict[str, Any]] = []
    checks.extend(_file_checks())
    checks.extend(_deploy_doc_checks())
    checks.extend(_environment_checks(child_env))
    checks.extend(_python_dependency_checks(child_env))
    checks.extend(_tooling_boundary_checks())
    if options.run_smoke:
        checks.append(_run_fallback_smoke(options, child_env))
    else:
        checks.append({"name": "fallback viewer smoke", "status": "skipped"})

    status = "ok" if all(check["status"] in {"ok", "skipped"} for check in checks) else "fail"
    return {
        "schema": "urban-cloud-run-preflight/v1",
        "status": status,
        "issue": options.issue,
        "created_at": _utc_now(),
        "project_root": str(PROJECT_ROOT),
        "scope": {
            "mode": "local-only",
            "gcp_executed": False,
            "cloud_run_deployed": False,
            "secret_manager_accessed": False,
            "public_access_changed": False,
            "billing_scope_changed": False,
            "local_docker_required": False,
        },
        "commands_not_executed": list(FORBIDDEN_REMOTE_COMMANDS),
        "checks": checks,
    }


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Cloud Run local preflight evidence ({report['issue']})",
        "",
        f"- status: `{report['status']}`",
        f"- created_at: `{report['created_at']}`",
        f"- mode: `{report['scope']['mode']}`",
        f"- GCP executed: `{report['scope']['gcp_executed']}`",
        f"- Cloud Run deployed: `{report['scope']['cloud_run_deployed']}`",
        f"- Secret Manager accessed: `{report['scope']['secret_manager_accessed']}`",
        f"- public access changed: `{report['scope']['public_access_changed']}`",
        f"- billing scope changed: `{report['scope']['billing_scope_changed']}`",
        f"- local Docker required: `{report['scope']['local_docker_required']}`",
        "",
        "## checks",
    ]
    for check in report["checks"]:
        lines.append(f"- `{check['status']}` {check['name']}")
        if check["status"] == "fail" and check.get("stderr_tail"):
            lines.append("")
            lines.append("```text")
            lines.append(check["stderr_tail"].strip())
            lines.append("```")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", default="NEX-29")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--smoke-port", type=int, default=18085)
    parser.add_argument("--smoke-agents", type=int, default=10)
    parser.add_argument("--smoke-seed", type=int, default=42)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--evidence-file", type=Path)
    args = parser.parse_args()

    options = PreflightOptions(
        issue=args.issue,
        run_smoke=not args.skip_smoke,
        smoke_port=args.smoke_port,
        smoke_agents=args.smoke_agents,
        smoke_seed=args.smoke_seed,
    )
    report = run_preflight(options)
    output = to_markdown(report) if args.format == "markdown" else json.dumps(report, ensure_ascii=False, indent=2)
    if args.evidence_file:
        args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_file.write_text(output + ("\n" if not output.endswith("\n") else ""), encoding="utf-8")
    print(output)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
