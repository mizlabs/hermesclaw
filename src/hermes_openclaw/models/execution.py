"""Enhanced execution result schemas for the feedback loop."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    PENDING_APPROVAL = "pending_approval"


class FailureReason(StrEnum):
    """Structured failure reasons returned by OpenClaw."""

    PERMISSION_DENIED = "permission_denied"
    PATH_BLOCKED = "path_blocked"
    SCOPE_DENIED = "scope_denied"
    POLICY_DENIED = "policy_denied"
    COMMAND_BLOCKED = "command_blocked"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class ExecutionMetadata(BaseModel):
    """Execution metadata attached to every action result."""

    scope: str = ""
    duration_ms: int = 0
    log_lines: list[str] = Field(default_factory=list)
    screenshot_path: str | None = None


class ActionResult(BaseModel):
    action_index: int
    action_type: str
    status: ExecutionStatus
    message: str = ""
    reason: FailureReason | None = None
    failed_task: str | None = None
    duration_ms: int = 0
    metadata: ExecutionMetadata = Field(default_factory=ExecutionMetadata)


class ExecutionReport(BaseModel):
    task_id: str
    status: ExecutionStatus
    reason: FailureReason | None = None
    failed_task: str | None = None
    results: list[ActionResult] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    audit_id: str | None = None
    metadata: ExecutionMetadata = Field(default_factory=ExecutionMetadata)
