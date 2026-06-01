"""Tests for SecurityValidator — the trust boundary."""

from pathlib import Path

import pytest

from hermes_openclaw.security.command_policy import CommandPolicy
from hermes_openclaw.security.path_guard import PathGuard
from hermes_openclaw.security.policy_engine import PolicyEngine
from hermes_openclaw.security.security_validator import SecurityValidator


@pytest.fixture
def validator(tmp_path: Path) -> SecurityValidator:
    guard = PathGuard(workspace_root=tmp_path)
    return SecurityValidator(guard, CommandPolicy(), PolicyEngine())


def test_validates_good_plan(validator: SecurityValidator):
    result = validator.validate_sync(
        {
            "intent": "organize",
            "actions": [
                {
                    "type": "create_folder",
                    "destination": "docs",
                    "scope": "filesystem.write",
                }
            ],
            "risk_level": "medium",
        }
    )
    assert result.valid is True
    assert result.validated_plan is not None
    assert result.validated_plan.actions[0].scope.value == "filesystem.write"


def test_blocks_delete_file_hallucination(validator: SecurityValidator):
    result = validator.validate_sync(
        {
            "intent": "delete secrets",
            "actions": [{"type": "delete_file", "source": "/etc/passwd"}],
            "risk_level": "critical",
        }
    )
    assert result.valid is False
    assert result.blocked_action == "delete_file"
    assert "hallucinated" in result.reason or "Blocked" in result.reason


def test_blocks_system_path(validator: SecurityValidator):
    result = validator.validate_sync(
        {
            "intent": "read secrets",
            "actions": [{"type": "list_files", "source": "/etc/passwd"}],
            "risk_level": "high",
        }
    )
    assert result.valid is False
    assert "Path" in result.reason or "sensitive" in result.reason or "outside" in result.reason


def test_blocks_forbidden_plan_fields(validator: SecurityValidator):
    result = validator.validate_sync({"intent": "hack", "shell": "rm -rf /", "actions": []})
    assert result.valid is False


def test_launch_app_with_scope(validator: SecurityValidator):
    result = validator.validate_sync(
        {
            "intent": "open editor",
            "actions": [
                {
                    "type": "launch_app",
                    "app_name": "vscode",
                    "scope": "applications.launch",
                }
            ],
            "risk_level": "medium",
        }
    )
    assert result.valid is True
    assert result.validated_plan.actions[0].scope.value == "applications.launch"
