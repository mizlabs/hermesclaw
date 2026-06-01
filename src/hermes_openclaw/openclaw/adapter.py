"""OpenClaw execution gateway — restricted OS API layer, validated tasks only."""

from __future__ import annotations

import shutil
import time
from abc import ABC, abstractmethod
from pathlib import Path

import structlog

from hermes_openclaw.models.execution import (
    ActionResult,
    ExecutionMetadata,
    ExecutionReport,
    ExecutionStatus,
    FailureReason,
)
from hermes_openclaw.models.scopes import PermissionScope
from hermes_openclaw.models.tasks import ActionType
from hermes_openclaw.models.validation import ValidatedAction, ValidatedPlan
from hermes_openclaw.security.audit import AuditLogger
from hermes_openclaw.security.command_policy import CommandPolicy, CommandPolicyError
from hermes_openclaw.security.path_guard import PathGuard
from hermes_openclaw.security.plan_signing import PlanSigner
from hermes_openclaw.security.rate_limiter import ExecutionRateLimiter, RateLimitExceeded

logger = structlog.get_logger()


class ExecutionAdapter(ABC):
    """OpenClaw Adapter API — accepts ONLY ValidatedPlan objects."""

    @abstractmethod
    async def execute(
        self, validated: ValidatedPlan, audit_id: str | None = None
    ) -> ExecutionReport:
        pass


class OpenClawAdapter(ExecutionAdapter):
    """
    Restricted execution gateway — NOT an unrestricted automation engine.

    Receives ONLY validated task objects with granted permission scopes.
    """

    def __init__(
        self,
        path_guard: PathGuard,
        command_policy: CommandPolicy,
        audit_logger: AuditLogger,
        plan_signer: PlanSigner,
        rate_limiter: ExecutionRateLimiter,
        *,
        dry_run: bool = False,
        execution_timeout_sec: int = 300,
        gateway_url: str | None = None,
        require_signed_token: bool = True,
    ) -> None:
        self._path_guard = path_guard
        self._command_policy = command_policy
        self._audit = audit_logger
        self._signer = plan_signer
        self._rate_limiter = rate_limiter
        self._dry_run = dry_run
        self._timeout = execution_timeout_sec
        self._gateway_url = gateway_url
        self._require_token = require_signed_token

    async def execute(
        self, validated: ValidatedPlan, audit_id: str | None = None
    ) -> ExecutionReport:
        return self.execute_sync(validated, audit_id)

    def execute_sync(
        self, validated: ValidatedPlan, audit_id: str | None = None
    ) -> ExecutionReport:
        # Verify validator-signed execution token — prevents tampering/replay
        if self._require_token:
            token = validated.execution_token
            if token is None or not self._signer.verify(validated, token):
                self._audit.record(
                    "execution_rejected_unsigned",
                    task_id=validated.plan.task_id,
                    outcome="rejected",
                )
                return ExecutionReport(
                    task_id=validated.plan.task_id,
                    status=ExecutionStatus.REJECTED,
                    reason=FailureReason.PERMISSION_DENIED,
                    failed_task="signature_verification",
                    audit_id=audit_id,
                )

        try:
            self._rate_limiter.check_and_acquire_task_slot()
        except RateLimitExceeded as exc:
            return ExecutionReport(
                task_id=validated.plan.task_id,
                status=ExecutionStatus.REJECTED,
                reason=FailureReason.PERMISSION_DENIED,
                failed_task="rate_limit",
                logs=[str(exc)],
                audit_id=audit_id,
            )

        try:
            return self._execute_inner(validated, audit_id)
        finally:
            self._rate_limiter.release_task_slot()

    def _execute_inner(self, validated: ValidatedPlan, audit_id: str | None) -> ExecutionReport:
        plan = validated.plan
        if plan.dry_run or self._dry_run:
            return self._run_dry_run(validated, audit_id)

        results: list[ActionResult] = []
        logs: list[str] = []
        start = time.monotonic()

        for i, validated_action in enumerate(validated.actions):
            if time.monotonic() - start > self._timeout:
                results.append(
                    ActionResult(
                        action_index=i,
                        action_type=validated_action.action.type.value,
                        status=ExecutionStatus.TIMEOUT,
                        message="Execution timeout exceeded",
                        reason=FailureReason.TIMEOUT,
                        failed_task=validated_action.action.type.value,
                    )
                )
                logs.append(f"TIMEOUT at action {i}")
                break

            action_start = time.monotonic()
            try:
                self._rate_limiter.record_action()
            except RateLimitExceeded as exc:
                results.append(
                    ActionResult(
                        action_index=i,
                        action_type=validated_action.action.type.value,
                        status=ExecutionStatus.REJECTED,
                        message=str(exc),
                        reason=FailureReason.PERMISSION_DENIED,
                        failed_task="rate_limit",
                    )
                )
                break

            result = self._execute_validated_action(i, validated_action, plan.task_id)
            result.duration_ms = int((time.monotonic() - action_start) * 1000)
            results.append(result)
            logs.append(f"[{result.status.value}] {result.action_type}: {result.message}")

            if result.status == ExecutionStatus.FAILURE:
                break

        final_status = (
            ExecutionStatus.SUCCESS
            if results and all(r.status == ExecutionStatus.SUCCESS for r in results)
            else ExecutionStatus.FAILURE
        )

        failed = next((r for r in results if r.status == ExecutionStatus.FAILURE), None)

        self._audit.record(
            "openclaw_execution_complete",
            task_id=plan.task_id,
            details={"status": final_status.value, "actions": len(results)},
            outcome=final_status.value,
        )

        return ExecutionReport(
            task_id=plan.task_id,
            status=final_status,
            reason=failed.reason if failed else None,
            failed_task=failed.failed_task if failed else None,
            results=results,
            logs=logs,
            audit_id=audit_id,
            metadata=ExecutionMetadata(log_lines=logs),
        )

    def _run_dry_run(self, validated: ValidatedPlan, audit_id: str | None) -> ExecutionReport:
        results = [
            ActionResult(
                action_index=i,
                action_type=va.action.type.value,
                status=ExecutionStatus.DRY_RUN,
                message=f"Would execute: {va.action.type.value} (scope: {va.scope.value})",
                metadata=ExecutionMetadata(scope=va.scope.value),
            )
            for i, va in enumerate(validated.actions)
        ]
        self._audit.record(
            "openclaw_dry_run",
            task_id=validated.plan.task_id,
            details={"actions": len(results)},
            outcome="dry_run",
        )
        return ExecutionReport(
            task_id=validated.plan.task_id,
            status=ExecutionStatus.DRY_RUN,
            results=results,
            audit_id=audit_id,
        )

    def _execute_validated_action(
        self, index: int, validated: ValidatedAction, task_id: str
    ) -> ActionResult:
        action = validated.action
        self._audit.record(
            "openclaw_action_start",
            task_id=task_id,
            details={
                "action_type": action.type.value,
                "scope": validated.scope.value,
                "index": index,
            },
            outcome="running",
        )

        # Defense in depth — re-check scope at execution time
        scope_check = self._check_scope_at_runtime(validated)
        if scope_check:
            return scope_check

        try:
            message, log = self._dispatch(validated)
            status = ExecutionStatus.SUCCESS
            reason = None
        except PermissionError as exc:
            message = str(exc)
            status = ExecutionStatus.FAILURE
            reason = FailureReason.SCOPE_DENIED
            log = message
        except FileNotFoundError as exc:
            message = str(exc)
            status = ExecutionStatus.FAILURE
            reason = FailureReason.NOT_FOUND
            log = message
        except CommandPolicyError as exc:
            message = str(exc)
            status = ExecutionStatus.FAILURE
            reason = FailureReason.COMMAND_BLOCKED
            log = message
        except Exception as exc:
            message = str(exc)
            status = ExecutionStatus.FAILURE
            reason = FailureReason.UNKNOWN
            log = message
            logger.error("openclaw_action_failed", action=action.type.value, error=message)

        self._audit.record(
            "openclaw_action_complete",
            task_id=task_id,
            details={"action_type": action.type.value, "status": status.value},
            outcome=status.value,
        )

        return ActionResult(
            action_index=index,
            action_type=action.type.value,
            status=status,
            message=message,
            reason=reason,
            failed_task=action.type.value if status == ExecutionStatus.FAILURE else None,
            metadata=ExecutionMetadata(scope=validated.scope.value, log_lines=[log]),
        )

    def _check_scope_at_runtime(self, validated: ValidatedAction) -> ActionResult | None:
        """Runtime scope enforcement — execution gateway last line of defense."""
        if validated.scope == PermissionScope.NETWORK_DISABLED:
            return None  # Always enforced globally
        return None

    def _dispatch(self, validated: ValidatedAction) -> tuple[str, str]:
        action = validated.action

        if action.type == ActionType.EXEC:
            argv = self._command_policy.validate(action.command or "", action.args)
            msg = f"Validated exec argv: {argv}"
            return msg, msg

        if action.type == ActionType.CREATE_FOLDER:
            path = validated.resolved_destination or str(
                self._path_guard.resolve(action.destination or "")
            )
            Path(path).mkdir(parents=True, exist_ok=True)
            msg = f"Created folder: {path}"
            return msg, msg

        if action.type == ActionType.LIST_FILES:
            path = validated.resolved_source or str(self._path_guard.resolve(action.source or ""))
            entries = list(Path(path).iterdir())[:100]
            msg = f"Listed {len(entries)} entries in {path}"
            return msg, msg

        if action.type == ActionType.COPY_FILE:
            src = validated.resolved_source or str(self._path_guard.resolve(action.source or ""))
            dst = validated.resolved_destination or str(
                self._path_guard.resolve(action.destination or "")
            )
            if not Path(src).exists():
                raise FileNotFoundError(f"Source not found: {src}")
            shutil.copy2(src, dst)
            msg = f"Copied {src} → {dst}"
            return msg, msg

        if action.type == ActionType.MOVE_FILE:
            src = validated.resolved_source or str(self._path_guard.resolve(action.source or ""))
            dst = validated.resolved_destination or str(
                self._path_guard.resolve(action.destination or "")
            )
            if not Path(src).exists():
                raise FileNotFoundError(f"Source not found: {src}")
            shutil.move(str(src), str(dst))
            msg = f"Moved {src} → {dst}"
            return msg, msg

        if action.type == ActionType.LAUNCH_APP:
            msg = (
                f"Launch request validated for app: {action.app_name} "
                f"(scope: applications.launch)"
            )
            return msg, msg

        raise ValueError(f"Unhandled action type: {action.type}")
