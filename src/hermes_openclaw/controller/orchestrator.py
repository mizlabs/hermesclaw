"""Task controller — validate → authorize → execute via OpenClaw gateway."""

from __future__ import annotations

from typing import Any

import structlog

from hermes_openclaw.models.execution import ExecutionReport, ExecutionStatus
from hermes_openclaw.openclaw.adapter import OpenClawAdapter
from hermes_openclaw.security.audit import AuditLogger
from hermes_openclaw.security.permission_gateway import PermissionGateway, PermissionStatus

logger = structlog.get_logger()


class Orchestrator:
    """Backward-compatible entry for direct plan ingestion (API / CLI --plan)."""

    def __init__(
        self,
        permission_gateway: PermissionGateway,
        openclaw: OpenClawAdapter,
        audit_logger: AuditLogger,
    ) -> None:
        self._permission = permission_gateway
        self._openclaw = openclaw
        self._audit = audit_logger

    def process_plan(self, raw_plan: str | dict[str, Any]) -> ExecutionReport:
        audit = self._audit.record("plan_received", outcome="processing")
        permission = self._permission.authorize(raw_plan)

        if permission.status == PermissionStatus.REJECTED:
            logger.warning("plan_rejected", reason=permission.reason)
            return ExecutionReport(
                task_id=audit.audit_id,
                status=ExecutionStatus.REJECTED,
                audit_id=audit.audit_id,
            )

        if permission.status == PermissionStatus.DENIED:
            task_id = (
                permission.validated_plan.plan.task_id
                if permission.validated_plan
                else audit.audit_id
            )
            return ExecutionReport(
                task_id=task_id,
                status=ExecutionStatus.REJECTED,
                audit_id=audit.audit_id,
            )

        if permission.validated_plan is None:
            return ExecutionReport(
                task_id=audit.audit_id,
                status=ExecutionStatus.REJECTED,
                audit_id=audit.audit_id,
            )

        return self._openclaw.execute_sync(permission.validated_plan, audit_id=audit.audit_id)
