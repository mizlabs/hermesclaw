"""Tests for signed plan hashing."""

from hermes_openclaw.models.scopes import PermissionScope
from hermes_openclaw.models.tasks import TaskAction, TaskPlan
from hermes_openclaw.models.validation import ValidatedAction, ValidatedPlan
from hermes_openclaw.security.plan_signing import PlanSigner


def _sample_plan() -> ValidatedPlan:
    action = TaskAction(type="list_files", source=".", scope="filesystem.read")
    return ValidatedPlan(
        plan=TaskPlan(intent="test", actions=[action], dry_run=True),
        actions=[ValidatedAction(action=action, scope=PermissionScope.FILESYSTEM_READ)],
    )


def test_sign_and_verify():
    signer = PlanSigner("test-secret")
    plan = _sample_plan()
    token = signer.sign(plan)
    signed = plan.model_copy(update={"execution_token": token})
    assert signer.verify(signed, token) is True


def test_tampered_plan_fails_verification():
    signer = PlanSigner("test-secret")
    plan = _sample_plan()
    token = signer.sign(plan)
    tampered = plan.model_copy(
        update={"plan": TaskPlan(intent="tampered", actions=plan.plan.actions)}
    )
    tampered = tampered.model_copy(update={"execution_token": token})
    assert signer.verify(tampered, token) is False


def test_hash_is_deterministic():
    signer = PlanSigner("test-secret")
    plan = _sample_plan()
    assert signer.hash_plan(plan) == signer.hash_plan(plan)
