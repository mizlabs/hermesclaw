"""Tests for the full agent pipeline."""

from pathlib import Path

import pytest

from hermes_openclaw.config import Settings
from hermes_openclaw.controller.factory import build_pipeline
from hermes_openclaw.feedback.engine import FeedbackEngine
from hermes_openclaw.models.execution import ActionResult, ExecutionReport, ExecutionStatus
from hermes_openclaw.models.feedback import FeedbackDecision
from hermes_openclaw.models.tasks import ActionType, RiskLevel, TaskAction, TaskPlan
from hermes_openclaw.security.audit import AuditLogger


@pytest.fixture
def pipeline(tmp_path: Path):
    settings = Settings(
        workspace_root=tmp_path / "workspace",
        audit_log_path=tmp_path / "audit.jsonl",
        auto_approve=True,
        dry_run=True,
        hermes_mock_mode=True,
    )
    return build_pipeline(settings)


def test_full_pipeline_with_mock_hermes(pipeline):
    result = pipeline.run("organize my project files")
    assert result.success is True
    assert result.final_plan is not None
    assert result.execution_report is not None
    assert result.execution_report.status == ExecutionStatus.DRY_RUN
    assert result.feedback is not None
    assert result.feedback.decision == FeedbackDecision.COMPLETE


def test_run_plan_directly(pipeline):
    result = pipeline.run_plan(
        {
            "intent": "list files",
            "actions": [{"type": "list_files", "source": "."}],
            "risk_level": "medium",
            "dry_run": True,
        }
    )
    assert result.success is True


def test_feedback_engine_replan_on_failure(tmp_path: Path):
    audit = AuditLogger(tmp_path / "audit.jsonl")
    engine = FeedbackEngine(audit, max_retries=3)

    plan = TaskPlan(
        intent="test",
        actions=[
            TaskAction(type=ActionType.LIST_FILES, source="."),
            TaskAction(type=ActionType.CREATE_FOLDER, destination="out"),
        ],
        risk_level=RiskLevel.MEDIUM,
    )
    report = ExecutionReport(
        task_id=plan.task_id,
        status=ExecutionStatus.FAILURE,
        results=[
            ActionResult(
                action_index=0,
                action_type="list_files",
                status=ExecutionStatus.FAILURE,
                message="not found",
            ),
            ActionResult(
                action_index=1,
                action_type="create_folder",
                status=ExecutionStatus.SKIPPED,
                message="",
            ),
        ],
    )

    feedback = engine.evaluate(plan, report, retry_count=0)
    assert feedback.decision == FeedbackDecision.REPLAN

    context = engine.build_replan_context(feedback)
    assert "Do not output executable code" in context
    assert "not found" in context
