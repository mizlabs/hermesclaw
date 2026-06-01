"""Validation result models — output of the Security Validator layer."""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, Field

from hermes_openclaw.models.explainability import RejectionExplanation
from hermes_openclaw.models.scopes import PermissionScope
from hermes_openclaw.models.security_levels import SecurityLevel
from hermes_openclaw.models.signing import ExecutionToken
from hermes_openclaw.models.tasks import TaskAction, TaskPlan


class ValidatedAction(BaseModel):
    """A single action that passed security validation with resolved paths and scope."""

    action: TaskAction
    scope: PermissionScope
    required_scopes: list[PermissionScope] = Field(default_factory=list)
    resolved_source: str | None = None
    resolved_destination: str | None = None


class ValidatedPlan(BaseModel):
    """
    A fully validated plan ready for the Permission Engine and OpenClaw.

    OpenClaw receives ONLY this object — never raw Hermes output.
    """

    validation_id: str = Field(default_factory=lambda: str(uuid4()))
    plan: TaskPlan
    actions: list[ValidatedAction]
    granted_scopes: list[PermissionScope] = Field(default_factory=list)
    security_level: SecurityLevel = SecurityLevel.SAFE
    execution_token: ExecutionToken | None = None


class ValidationResult(BaseModel):
    """Outcome of SecurityValidator.validate()."""

    valid: bool
    validated_plan: ValidatedPlan | None = None
    errors: list[str] = Field(default_factory=list)
    blocked_action: str | None = None
    reason: str = ""
    explanation: RejectionExplanation | None = None
