"""Cloud Run local-only preflight の最小テスト。"""

from __future__ import annotations

from tools.cloud_run_preflight import (
    PreflightOptions,
    local_only_env,
    run_preflight,
    to_markdown,
)


def test_local_only_env_removes_gcp_and_secret_keys() -> None:
    env = local_only_env(
        {
            "GOOGLE_MAPS_API_KEY": "dummy",
            "GOOGLE_PLACES_API_KEY": "dummy",
            "GOOGLE_CLOUD_PROJECT": "dummy-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/key.json",
            "DEPLOY_PROJECT": "dummy-project",
            "KEEP_ME": "1",
        }
    )

    assert "KEEP_ME" in env
    assert env["DATA_SOURCE"] == "local"
    assert "GOOGLE_MAPS_API_KEY" not in env
    assert "GOOGLE_PLACES_API_KEY" not in env
    assert "GOOGLE_CLOUD_PROJECT" not in env
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env
    assert "DEPLOY_PROJECT" not in env


def test_run_preflight_skip_smoke_reports_no_remote_execution() -> None:
    report = run_preflight(
        PreflightOptions(
            issue="NEX-29",
            run_smoke=False,
            smoke_port=18085,
            smoke_agents=2,
            smoke_seed=42,
        )
    )

    assert report["schema"] == "urban-cloud-run-preflight/v1"
    assert report["issue"] == "NEX-29"
    assert report["scope"]["gcp_executed"] is False
    assert report["scope"]["cloud_run_deployed"] is False
    assert report["scope"]["secret_manager_accessed"] is False
    assert report["scope"]["public_access_changed"] is False
    assert report["scope"]["billing_scope_changed"] is False
    assert "gcloud" in report["commands_not_executed"]
    assert any(check["name"] == "fallback viewer smoke" and check["status"] == "skipped" for check in report["checks"])


def test_markdown_evidence_contains_issue_and_local_only_scope() -> None:
    report = run_preflight(
        PreflightOptions(
            issue="NEX-29",
            run_smoke=False,
            smoke_port=18085,
            smoke_agents=2,
            smoke_seed=42,
        )
    )

    markdown = to_markdown(report)

    assert "Cloud Run local preflight evidence (NEX-29)" in markdown
    assert "mode: `local-only`" in markdown
    assert "GCP executed: `False`" in markdown
