"""Execution token model — signed authorization for validated plans."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field


class ExecutionToken(BaseModel):
    """Cryptographic token authorizing a specific ValidatedPlan for execution."""

    plan_hash: str
    signature: str
    validation_id: str
    task_id: str
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=5))
