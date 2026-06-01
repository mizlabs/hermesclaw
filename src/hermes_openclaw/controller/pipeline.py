"""Full agent pipeline — User → Hermes → Validator → Permission → OpenClaw → Feedback."""

from __future__ import annotations

import structlog

from hermes_openclaw.feedback.engine import FeedbackEngine
from hermes_openclaw.hermes.adapter import HermesAdapter, HermesAdapterError
from hermes_openclaw.models.execution import ExecutionReport, ExecutionStatus
from hermes_openclaw.models.feedback import FeedbackDecision, FeedbackReport, PipelineResult
from hermes_openclaw.models.validation import ValidatedPlan
from hermes_openclaw.openclaw.adapter import OpenClawAdapter
from hermes_openclaw.security.audit import AuditLogger
from hermes_openclaw.security.permission_gateway import PermissionGateway, PermissionStatus

logger = structlog.get_logger()


class AgentPipeline:
    """Wires planner → validator → permission → executor → feedback."""

    def __init__(
        self,
        hermes: HermesAdapter,
        permission_gateway: PermissionGateway,
        openclaw: OpenClawAdapter,
        feedback_engine: FeedbackEngine,
        audit_logger: AuditLogger,
    ) -> None:
        self._hermes = hermes
        self._permission = permission_gateway
        self._openclaw = openclaw
        self._feedback = feedback_engine
        self._audit = audit_logger

    def run(self, user_intent: str) -> PipelineResult:
        self._audit.record("pipeline_start", details={"intent": user_intent}, outcome="started")

        retry_count = 0
        replan_context = ""
        last_validated: ValidatedPlan | None = None
        last_report: ExecutionReport | None = None
        last_feedback: FeedbackReport | None = None

        while True:
            attempt = retry_count + 1
            logger.info("pipeline_attempt", attempt=attempt, intent=user_intent)

            # 1. Hermes Planner — JSON only, never raw code
            try:
                raw_plan = self._hermes.plan(user_intent, context=replan_context)
            except HermesAdapterError as exc:
                self._audit.record(
                    "hermes_plan_failed",
                    details={"error": str(exc), "attempt": attempt},
                    outcome="failed",
                )
                return PipelineResult(
                    success=False,
                    intent=user_intent,
                    attempts=attempt,
                    message=f"Hermes planning failed: {exc}",
                )

            # 2. Security Validator + 3. Permission Engine
            permission = self._permission.authorize(raw_plan)

            if permission.status == PermissionStatus.REJECTED:
                return PipelineResult(
                    success=False,
                    intent=user_intent,
                    attempts=attempt,
                    message=f"Security validation failed: {permission.reason}",
                )

            if permission.status == PermissionStatus.DENIED:
                return PipelineResult(
                    success=False,
                    intent=user_intent,
                    attempts=attempt,
                    message=f"Permission denied: {permission.reason}",
                )

            validated = permission.validated_plan
            if validated is None:
                return PipelineResult(
                    success=False,
                    intent=user_intent,
                    attempts=attempt,
                    message="Permission granted but no validated plan returned.",
                )

            last_validated = validated

            # 4. OpenClaw Executor (restricted OS API layer)
            report = self._openclaw.execute_sync(validated)
            last_report = report

            # 5. Feedback Loop → Replan / Retry
            feedback = self._feedback.evaluate(validated.plan, report, retry_count=retry_count)
            last_feedback = feedback

            if feedback.decision == FeedbackDecision.COMPLETE:
                self._audit.record(
                    "pipeline_complete",
                    task_id=validated.plan.task_id,
                    outcome="success",
                )
                return PipelineResult(
                    success=True,
                    intent=user_intent,
                    final_plan=validated.plan,
                    execution_report=report,
                    feedback=feedback,
                    attempts=attempt,
                    message=feedback.message,
                )

            if feedback.decision in (
                FeedbackDecision.ABORT,
                FeedbackDecision.ASK_USER,
            ):
                return PipelineResult(
                    success=False,
                    intent=user_intent,
                    final_plan=validated.plan,
                    execution_report=report,
                    feedback=feedback,
                    attempts=attempt,
                    message=feedback.message,
                )

            if feedback.decision in (FeedbackDecision.RETRY, FeedbackDecision.REPLAN):
                retry_count += 1
                replan_context = self._feedback.build_replan_context(feedback)
                continue

        return PipelineResult(
            success=False,
            intent=user_intent,
            final_plan=last_validated.plan if last_validated else None,
            execution_report=last_report,
            feedback=last_feedback,
            attempts=retry_count + 1,
            message="Pipeline exited unexpectedly.",
        )

    def run_plan(self, raw_plan: dict) -> PipelineResult:
        permission = self._permission.authorize(raw_plan)

        if permission.status != PermissionStatus.GRANTED or permission.validated_plan is None:
            return PipelineResult(
                success=False,
                intent=str(raw_plan.get("intent", "unknown")),
                message=permission.reason or "Permission not granted",
            )

        validated = permission.validated_plan
        report = self._openclaw.execute_sync(validated)
        feedback = self._feedback.evaluate(validated.plan, report)

        return PipelineResult(
            success=report.status in (ExecutionStatus.SUCCESS, ExecutionStatus.DRY_RUN),
            intent=validated.plan.intent,
            final_plan=validated.plan,
            execution_report=report,
            feedback=feedback,
            attempts=1,
            message=feedback.message,
        )
