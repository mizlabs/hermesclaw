"""Permission gateway — delegates to PermissionEngine (backward compatible)."""

from __future__ import annotations

from typing import Any

from hermes_openclaw.models.tasks import TaskPlan
from hermes_openclaw.models.validation import ValidatedPlan
from hermes_openclaw.security.permission_engine import (
    PermissionEngine,
    PermissionResult,
    PermissionStatus,
)

# Re-export for existing imports
__all__ = ["PermissionGateway", "PermissionResult", "PermissionStatus"]


class PermissionGateway:
    """Thin wrapper around PermissionEngine for backward compatibility."""

    def __init__(self, engine: PermissionEngine) -> None:
        self._engine = engine

    def authorize(self, raw_plan: str | dict[str, Any]) -> PermissionResult:
        return self._engine.authorize_sync(raw_plan)

    @property
    def _approval(self):
        return self._engine._approval

    @property
    def plan(self) -> TaskPlan | None:
        return None

    def validated_plan(self, result: PermissionResult) -> ValidatedPlan | None:
        return result.validated_plan
