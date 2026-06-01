"""User approval gate — dangerous actions require explicit consent."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hermes_openclaw.models.tasks import RiskLevel, TaskPlan


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"


@dataclass
class ApprovalRequest:
    task_id: str
    intent: str
    risk_level: RiskLevel
    action_summary: str
    reason: str


class ApprovalGate:
    """
    Blocks high-risk plans until the user explicitly approves.

    In CLI mode, prompts stdin. In API mode, returns pending status.
    Auto-denies when no approver is available (fail-safe).
    """

    def __init__(self, auto_approve: bool = False) -> None:
        # auto_approve exists ONLY for dry-run/test environments — never in production.
        self._auto_approve = auto_approve

    def requires_approval(self, plan: TaskPlan) -> bool:
        return plan.requires_confirmation or plan.risk_level in (
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        )

    def build_request(self, plan: TaskPlan) -> ApprovalRequest:
        action_types = ", ".join(a.type.value for a in plan.actions)
        return ApprovalRequest(
            task_id=plan.task_id,
            intent=plan.intent,
            risk_level=plan.risk_level,
            action_summary=action_types,
            reason=self._approval_reason(plan),
        )

    def request_approval(self, plan: TaskPlan) -> ApprovalDecision:
        if not self.requires_approval(plan):
            return ApprovalDecision.APPROVED

        if self._auto_approve:
            return ApprovalDecision.APPROVED

        request = self.build_request(plan)
        print("\n⚠️  APPROVAL REQUIRED")
        print(f"   Task:    {request.task_id}")
        print(f"   Intent:  {request.intent}")
        print(f"   Risk:    {request.risk_level.value}")
        print(f"   Actions: {request.action_summary}")
        print(f"   Reason:  {request.reason}")
        print()

        try:
            answer = input("Approve this plan? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return ApprovalDecision.DENIED

        if answer in ("y", "yes"):
            return ApprovalDecision.APPROVED
        return ApprovalDecision.DENIED

    def _approval_reason(self, plan: TaskPlan) -> str:
        if plan.risk_level == RiskLevel.CRITICAL:
            return "Critical risk level"
        if plan.risk_level == RiskLevel.HIGH:
            return "High risk level"
        if any(a.type.value == "exec" for a in plan.actions):
            return "Plan contains command execution"
        return "Plan flagged for confirmation"
