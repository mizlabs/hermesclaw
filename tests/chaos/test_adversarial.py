"""Chaos / adversarial tests — proves resilience under attack."""

from pathlib import Path

import pytest

from hermes_openclaw.config import Settings
from hermes_openclaw.controller.factory import build_orchestrator
from hermes_openclaw.models.execution import ExecutionStatus
from hermes_openclaw.security.command_policy import CommandPolicy
from hermes_openclaw.security.path_guard import PathGuard
from hermes_openclaw.security.policy_engine import PolicyEngine
from hermes_openclaw.security.rate_limiter import ExecutionRateLimiter, RateLimitConfig
from hermes_openclaw.security.security_validator import SecurityValidator


@pytest.fixture
def validator(tmp_path: Path) -> SecurityValidator:
    return SecurityValidator(PathGuard(tmp_path), CommandPolicy(), PolicyEngine())


class TestMalformedInput:
    def test_rejects_invalid_json(self, validator: SecurityValidator):
        result = validator.validate_sync("not json {{{")
        assert result.valid is False
        assert result.explanation is not None

    def test_rejects_empty_object(self, validator: SecurityValidator):
        result = validator.validate_sync({})
        assert result.valid is False

    def test_rejects_null_bytes_in_intent(self, validator: SecurityValidator):
        result = validator.validate_sync(
            {"intent": "test\x00injection", "actions": [], "risk_level": "low"}
        )
        assert result.valid is False


class TestMaliciousPrompts:
    def test_rejects_shell_field(self, validator: SecurityValidator):
        result = validator.validate_sync({"intent": "hack", "shell": "rm -rf /", "actions": []})
        assert result.valid is False
        assert result.explanation.category.value == "forbidden_field_in_plan"

    def test_rejects_subprocess_field(self, validator: SecurityValidator):
        result = validator.validate_sync(
            {"intent": "hack", "subprocess": "Popen(['rm','-rf','/'])", "actions": []}
        )
        assert result.valid is False

    def test_rejects_delete_file_hallucination(self, validator: SecurityValidator):
        result = validator.validate_sync(
            {
                "intent": "cleanup",
                "tasks": [{"action": "delete_file", "source": "/etc/passwd"}],
                "risk_level": "low",
            }
        )
        assert result.valid is False
        assert "delete_file" in (result.blocked_action or "")


class TestPathTraversal:
    def test_blocks_etc_passwd(self, validator: SecurityValidator):
        result = validator.validate_sync(
            {
                "intent": "read",
                "actions": [{"type": "list_files", "source": "/etc/passwd"}],
                "risk_level": "high",
            }
        )
        assert result.valid is False
        assert result.explanation is not None
        assert "path" in result.explanation.category.value or "Path" in result.reason

    def test_blocks_ssh_directory(self, validator: SecurityValidator):
        result = validator.validate_sync(
            {
                "intent": "read keys",
                "actions": [{"type": "list_files", "source": "~/.ssh/id_rsa"}],
                "risk_level": "high",
            }
        )
        assert result.valid is False


class TestValidatorBypass:
    def test_unsigned_plan_rejected_by_executor(self, tmp_path: Path):
        settings = Settings(
            workspace_root=tmp_path / "workspace",
            audit_log_path=tmp_path / "audit.jsonl",
            auto_approve=True,
            dry_run=True,
            require_signed_token=True,
        )
        orch = build_orchestrator(settings)
        # Manually craft plan without going through permission signing
        from hermes_openclaw.models.tasks import TaskAction, TaskPlan
        from hermes_openclaw.models.validation import ValidatedPlan

        plan = ValidatedPlan(
            plan=TaskPlan(
                intent="bypass",
                actions=[TaskAction(type="list_files", source=".")],
                dry_run=True,
            ),
            actions=[],
        )
        report = orch._openclaw.execute_sync(plan)
        assert report.status == ExecutionStatus.REJECTED

    def test_tampered_token_rejected(self, tmp_path: Path):
        settings = Settings(
            workspace_root=tmp_path / "workspace",
            audit_log_path=tmp_path / "audit.jsonl",
            plan_signing_secret="test-secret-for-chaos",
            auto_approve=True,
            dry_run=True,
        )
        report = build_orchestrator(settings).process_plan(
            {
                "intent": "test",
                "actions": [{"type": "list_files", "source": ".", "scope": "filesystem.read"}],
                "risk_level": "medium",
                "dry_run": True,
            }
        )
        assert report.status == ExecutionStatus.DRY_RUN


class TestRateLimits:
    def test_blocks_runaway_actions(self):
        limiter = ExecutionRateLimiter(RateLimitConfig(max_actions_per_minute=3))
        for _ in range(3):
            limiter.record_action()
        with pytest.raises(Exception, match="Max actions"):
            limiter.record_action()

    def test_blocks_parallel_flood(self):
        limiter = ExecutionRateLimiter(RateLimitConfig(max_parallel_tasks=1))
        limiter.check_and_acquire_task_slot()
        with pytest.raises(Exception, match="parallel"):
            limiter.check_and_acquire_task_slot()
        limiter.release_task_slot()


class TestExplainability:
    def test_rejection_has_human_readable_explanation(self, validator: SecurityValidator):
        result = validator.validate_sync({"shell": "evil", "intent": "x", "actions": []})
        assert result.explanation is not None
        assert "Rejected because:" in result.explanation.human_readable
