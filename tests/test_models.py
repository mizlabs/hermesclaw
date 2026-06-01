"""Tests for Pydantic task schemas."""

import json

import pytest
from pydantic import ValidationError

from hermes_openclaw.models.tasks import ActionType, RiskLevel, TaskAction, TaskPlan


def test_valid_plan():
    plan = TaskPlan(
        intent="organize downloads",
        actions=[
            TaskAction(type=ActionType.CREATE_FOLDER, destination="Documents/PDFs"),
            TaskAction(type=ActionType.LIST_FILES, source="."),
        ],
        risk_level=RiskLevel.MEDIUM,
    )
    assert plan.risk_level == RiskLevel.MEDIUM
    assert len(plan.actions) == 2


def test_rejects_unknown_action_type():
    with pytest.raises(ValidationError):
        TaskAction(type="delete_everything", source="/")


def test_rejects_shell_metacharacters():
    with pytest.raises(ValidationError):
        TaskAction(type=ActionType.LIST_FILES, source="/tmp; rm -rf /")


def test_exec_requires_confirmation():
    plan = TaskPlan(
        intent="run command",
        actions=[TaskAction(type=ActionType.EXEC, command="ls", args=["-la"])],
        risk_level=RiskLevel.MEDIUM,
    )
    assert plan.requires_confirmation is True


def test_high_risk_forces_confirmation():
    plan = TaskPlan(
        intent="risky",
        actions=[TaskAction(type=ActionType.LIST_FILES, source=".")],
        risk_level=RiskLevel.HIGH,
    )
    assert plan.requires_confirmation is True


def test_plan_roundtrip_json():
    plan = TaskPlan(
        intent="test",
        actions=[TaskAction(type=ActionType.CREATE_FOLDER, destination="test")],
    )
    data = json.loads(plan.model_dump_json())
    restored = TaskPlan.model_validate(data)
    assert restored.intent == plan.intent
