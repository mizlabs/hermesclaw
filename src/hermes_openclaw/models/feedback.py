"""Feedback loop models — decisions after execution."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from hermes_openclaw.models.execution import ExecutionReport
from hermes_openclaw.models.tasks import TaskPlan


class FeedbackDecision(StrEnum):
    """What the feedback engine decides after reviewing execution results."""

    COMPLETE = "complete"
    RETRY = "retry"
    REPLAN = "replan"
    ASK_USER = "ask_user"
    ABORT = "abort"


class FeedbackReport(BaseModel):
    """Structured feedback sent back to Hermes for replanning."""

    decision: FeedbackDecision
    task_id: str
    original_intent: str
    execution_report: ExecutionReport
    failure_summary: str = ""
    retry_count: int = 0
    message: str = ""


class PipelineResult(BaseModel):
    """Final outcome of a full user-intent pipeline run."""

    success: bool
    intent: str
    final_plan: TaskPlan | None = None
    execution_report: ExecutionReport | None = None
    feedback: FeedbackReport | None = None
    attempts: int = 1
    message: str = ""
