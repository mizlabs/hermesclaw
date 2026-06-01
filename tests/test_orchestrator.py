"""Tests for the orchestrator pipeline."""

from pathlib import Path

import pytest

from hermes_openclaw.config import Settings
from hermes_openclaw.controller.factory import build_orchestrator
from hermes_openclaw.models.execution import ExecutionStatus


@pytest.fixture
def orchestrator(tmp_path: Path):
    settings = Settings(
        workspace_root=tmp_path / "workspace",
        audit_log_path=tmp_path / "audit.jsonl",
        auto_approve=True,
        dry_run=True,
    )
    return build_orchestrator(settings)


def test_dry_run_pipeline(orchestrator):
    report = orchestrator.process_plan(
        {
            "intent": "test dry run",
            "actions": [{"type": "create_folder", "destination": "test"}],
            "risk_level": "medium",
            "dry_run": True,
        }
    )
    assert report.status == ExecutionStatus.DRY_RUN
    assert len(report.results) == 1


def test_rejects_invalid_plan(orchestrator):
    report = orchestrator.process_plan({"shell": "rm -rf /"})
    assert report.status == ExecutionStatus.REJECTED


def test_approval_denied(tmp_path: Path):
    settings = Settings(
        workspace_root=tmp_path / "workspace",
        audit_log_path=tmp_path / "audit.jsonl",
        auto_approve=False,
    )
    orch = build_orchestrator(settings)

    def deny(_plan):
        from hermes_openclaw.security.approval_gate import ApprovalDecision

        return ApprovalDecision.DENIED

    orch._permission._approval.request_approval = deny  # type: ignore[method-assign]

    report = orch.process_plan(
        {
            "intent": "needs approval",
            "actions": [{"type": "list_files", "source": "."}],
            "risk_level": "high",
        }
    )
    assert report.status == ExecutionStatus.REJECTED
