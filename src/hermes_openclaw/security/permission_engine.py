"""Permission engine — authorization after security validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import structlog

from hermes_openclaw.models.validation import ValidatedPlan, ValidationResult
from hermes_openclaw.security.approval_gate import ApprovalDecision, ApprovalGate
from hermes_openclaw.security.audit import AuditLogger
from hermes_openclaw.security.plan_signing import PlanSigner
from hermes_openclaw.security.security_validator import SecurityValidator

logger = structlog.get_logger()


class PermissionStatus(StrEnum):
    GRANTED = "granted"
    DENIED = "denied"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PermissionResult:
    status: PermissionStatus
    validated_plan: ValidatedPlan | None = None
    validation: ValidationResult | None = None
    reason: str = ""


class PermissionEngine:
    """
    Permission Engine — runs AFTER SecurityValidator.

    Signs approved plans with execution tokens before OpenClaw executes them.
    """

    def __init__(
        self,
        validator: SecurityValidator,
        approval_gate: ApprovalGate,
        audit_logger: AuditLogger,
        plan_signer: PlanSigner,
    ) -> None:
        self._validator = validator
        self._approval = approval_gate
        self._audit = audit_logger
        self._signer = plan_signer

    async def authorize(self, raw: str | dict[str, Any]) -> PermissionResult:
        return self.authorize_sync(raw)

    def authorize_sync(self, raw: str | dict[str, Any]) -> PermissionResult:
        validation = self._validator.validate_sync(raw)

        if not validation.valid or validation.validated_plan is None:
            details: dict[str, Any] = {
                "errors": validation.errors,
                "reason": validation.reason,
            }
            if validation.explanation:
                details["explanation"] = validation.explanation.human_readable
            self._audit.record(
                "security_validation_failed",
                details=details,
                outcome="rejected",
            )
            logger.warning("security_validation_failed", reason=validation.reason)
            return PermissionResult(
                status=PermissionStatus.REJECTED,
                validation=validation,
                reason=(
                    validation.explanation.human_readable
                    if validation.explanation
                    else validation.reason
                ),
            )

        validated = validation.validated_plan
        plan = validated.plan

        self._audit.record(
            "security_validation_passed",
            task_id=plan.task_id,
            details={
                "intent": plan.intent,
                "actions": len(validated.actions),
                "scopes": [s.value for s in validated.granted_scopes],
                "security_level": validated.security_level.value,
            },
            outcome="validated",
        )

        if not self._approval.requires_approval(plan):
            return self._grant(validated, validation)

        decision = self._approval.request_approval(plan)
        if decision != ApprovalDecision.APPROVED:
            self._audit.record(
                "permission_denied",
                task_id=plan.task_id,
                outcome=decision.value,
            )
            return PermissionResult(
                status=PermissionStatus.DENIED,
                validated_plan=validated,
                validation=validation,
                reason=f"User {decision.value}",
            )

        return self._grant(validated, validation)

    def _grant(self, validated: ValidatedPlan, validation: ValidationResult) -> PermissionResult:
        token = self._signer.sign(validated)
        signed = validated.model_copy(update={"execution_token": token})
        self._audit.record(
            "permission_granted",
            task_id=validated.plan.task_id,
            details={
                "plan_hash": token.plan_hash,
                "security_level": validated.security_level.value,
            },
            outcome="granted",
        )
        return PermissionResult(
            status=PermissionStatus.GRANTED,
            validated_plan=signed,
            validation=validation,
        )
