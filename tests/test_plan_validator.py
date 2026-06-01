"""Tests for plan validation — the trust boundary."""

from pathlib import Path

import pytest

from hermes_openclaw.security.command_policy import CommandPolicy
from hermes_openclaw.security.path_guard import PathGuard
from hermes_openclaw.security.plan_validator import PlanValidationError, PlanValidator


@pytest.fixture
def validator(tmp_path: Path) -> PlanValidator:
    guard = PathGuard(workspace_root=tmp_path)
    return PlanValidator(guard, CommandPolicy())


def test_validates_good_plan(validator: PlanValidator):
    plan = validator.parse_and_validate(
        {
            "intent": "organize",
            "actions": [{"type": "create_folder", "destination": "docs"}],
            "risk_level": "medium",
        }
    )
    assert plan.intent == "organize"


def test_rejects_forbidden_fields(validator: PlanValidator):
    with pytest.raises(PlanValidationError, match="Forbidden fields"):
        validator.parse_and_validate({"intent": "hack", "shell": "rm -rf /", "actions": []})


def test_rejects_invalid_json(validator: PlanValidator):
    with pytest.raises(PlanValidationError, match="Invalid JSON"):
        validator.parse_and_validate("not json {{{")


def test_rejects_blocked_command(validator: PlanValidator, tmp_path: Path):
    with pytest.raises(PlanValidationError, match="Command policy"):
        validator.parse_and_validate(
            {
                "intent": "delete all",
                "actions": [{"type": "exec", "command": "rm -rf /"}],
                "risk_level": "critical",
            }
        )


def test_rejects_sensitive_path(validator: PlanValidator):
    with pytest.raises(PlanValidationError, match="Path validation"):
        validator.parse_and_validate(
            {
                "intent": "read secrets",
                "actions": [{"type": "list_files", "source": "/etc/passwd"}],
                "risk_level": "high",
            }
        )
