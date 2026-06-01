"""Feedback engine — analyzes execution results and drives replan/retry decisions."""

from __future__ import annotations

import structlog

from hermes_openclaw.models.execution import ExecutionReport, ExecutionStatus, FailureReason
from hermes_openclaw.models.feedback import FeedbackDecision, FeedbackReport
from hermes_openclaw.models.tasks import TaskPlan
from hermes_openclaw.security.audit import AuditLogger

logger = structlog.get_logger()


class FeedbackEngine:
    """
    Closes the loop: execution results → decision → Hermes replan or retry.

    Never auto-retries destructive failures without explicit replan from Hermes.
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        max_retries: int = 3,
    ) -> None:
        self._audit = audit_logger
        self._max_retries = max_retries

    def evaluate(
        self,
        plan: TaskPlan,
        report: ExecutionReport,
        *,
        retry_count: int = 0,
    ) -> FeedbackReport:
        """Analyze execution report and decide next step."""
        decision, message, failure_summary = self._decide(plan, report, retry_count)

        feedback = FeedbackReport(
            decision=decision,
            task_id=plan.task_id,
            original_intent=plan.intent,
            execution_report=report,
            failure_summary=failure_summary,
            retry_count=retry_count,
            message=message,
        )

        self._audit.record(
            "feedback_decision",
            task_id=plan.task_id,
            details={
                "decision": decision.value,
                "status": report.status.value,
                "retry_count": retry_count,
            },
            outcome=decision.value,
        )

        logger.info(
            "feedback_decision",
            decision=decision.value,
            task_id=plan.task_id,
            status=report.status.value,
        )

        return feedback

    def build_replan_context(self, feedback: FeedbackReport) -> str:
        """Build context string for Hermes replanning — no raw code, structured facts only."""
        failed = [
            r
            for r in feedback.execution_report.results
            if r.status in (ExecutionStatus.FAILURE, ExecutionStatus.TIMEOUT)
        ]
        lines = [
            f"Previous attempt failed (retry {feedback.retry_count}).",
            f"Intent: {feedback.original_intent}",
            f"Overall status: {feedback.execution_report.status.value}",
        ]
        for result in failed:
            reason = result.reason.value if result.reason else "unknown"
            lines.append(
                f"- Action {result.action_index} ({result.action_type}): "
                f"{result.status.value} — reason={reason} — {result.message}"
            )
        lines.append("Generate a corrected JSON plan. Do not output executable code.")
        return "\n".join(lines)

    def _decide(
        self,
        plan: TaskPlan,
        report: ExecutionReport,
        retry_count: int,
    ) -> tuple[FeedbackDecision, str, str]:
        if report.status in (ExecutionStatus.SUCCESS, ExecutionStatus.DRY_RUN):
            return FeedbackDecision.COMPLETE, "All actions completed successfully.", ""

        if report.status == ExecutionStatus.REJECTED:
            return (
                FeedbackDecision.ABORT,
                "Plan was rejected by security or permission gate.",
                report.results[0].message if report.results else "Rejected",
            )

        failure_summary = self._summarize_failures(report)

        if retry_count >= self._max_retries:
            return (
                FeedbackDecision.ASK_USER,
                f"Max retries ({self._max_retries}) exceeded. User intervention required.",
                failure_summary,
            )

        # Timeout or partial failure — ask Hermes for a new plan.
        if report.status == ExecutionStatus.TIMEOUT:
            return (
                FeedbackDecision.REPLAN,
                "Execution timed out. Requesting new plan from Hermes.",
                failure_summary,
            )

        if report.status == ExecutionStatus.FAILURE:
            # Permission/policy failures → replan with Hermes
            if report.reason in (
                FailureReason.PERMISSION_DENIED,
                FailureReason.POLICY_DENIED,
                FailureReason.SCOPE_DENIED,
            ):
                return (
                    FeedbackDecision.REPLAN,
                    f"Permission/policy failure ({report.reason.value}). Requesting replan.",
                    failure_summary,
                )

            failed_index = next(
                (r.action_index for r in report.results if r.status == ExecutionStatus.FAILURE),
                0,
            )
            remaining = len(plan.actions) - failed_index
            if remaining > 1:
                return (
                    FeedbackDecision.REPLAN,
                    "Multiple actions failed or blocked. Requesting replan from Hermes.",
                    failure_summary,
                )
            return (
                FeedbackDecision.RETRY,
                "Single action failed. Retrying same plan.",
                failure_summary,
            )

        return FeedbackDecision.ABORT, "Unexpected execution status.", failure_summary

    def _summarize_failures(self, report: ExecutionReport) -> str:
        failures = [
            f"{r.action_type}[{r.action_index}]: {r.message}"
            for r in report.results
            if r.status in (ExecutionStatus.FAILURE, ExecutionStatus.TIMEOUT)
        ]
        return "; ".join(failures) if failures else report.status.value
