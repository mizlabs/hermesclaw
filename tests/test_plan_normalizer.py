"""Tests for Hermes plan normalization (tasks/action format)."""

from pathlib import Path

from hermes_openclaw.security.command_policy import CommandPolicy
from hermes_openclaw.security.path_guard import PathGuard
from hermes_openclaw.security.policy_engine import PolicyEngine
from hermes_openclaw.security.security_validator import SecurityValidator


def test_accepts_tasks_with_action_field(tmp_path: Path):
    validator = SecurityValidator(PathGuard(tmp_path), CommandPolicy(), PolicyEngine())
    result = validator.validate_sync(
        {
            "intent": "workspace_setup",
            "risk_level": "medium",
            "tasks": [
                {
                    "action": "create_folder",
                    "destination": "PDFs",
                    "scope": "filesystem.write",
                }
            ],
        }
    )
    assert result.valid is True
    assert result.validated_plan.actions[0].action.type.value == "create_folder"


def test_normalizes_move_files_alias(tmp_path: Path):
    validator = SecurityValidator(PathGuard(tmp_path), CommandPolicy(), PolicyEngine())
    result = validator.validate_sync(
        {
            "intent": "organize",
            "risk_level": "medium",
            "tasks": [
                {
                    "action": "move_files",
                    "source": "inbox",
                    "destination": "archive",
                    "scope": "filesystem.write",
                }
            ],
            "dry_run": True,
        }
    )
    assert result.valid is True
    assert result.validated_plan.actions[0].action.type.value == "move_file"
