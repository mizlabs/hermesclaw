"""Plan validator — never trust raw LLM output; validate before execution."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from hermes_openclaw.models.tasks import ActionType, RiskLevel, TaskPlan
from hermes_openclaw.security.command_policy import CommandPolicy, CommandPolicyError
from hermes_openclaw.security.path_guard import PathGuard, PathGuardError


class PlanValidationError(Exception):
    """Raised when a plan fails security validation."""


class PlanValidator:
    """
    Defense-in-depth validator for Hermes output.

    Hermes produces JSON only — this module is the trust boundary.
    No plan reaches OpenClaw without passing every check here.
    """

    def __init__(
        self,
        path_guard: PathGuard,
        command_policy: CommandPolicy,
        max_actions: int = 50,
    ) -> None:
        self._path_guard = path_guard
        self._command_policy = command_policy
        self._max_actions = max_actions

    def parse_and_validate(self, raw: str | dict[str, Any]) -> TaskPlan:
        """Parse raw LLM JSON and run full security validation."""
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise PlanValidationError(f"Invalid JSON from planner: {exc}") from exc
        else:
            data = raw

        if not isinstance(data, dict):
            raise PlanValidationError("Plan must be a JSON object")

        # Reject free-form execution fields that bypass the schema.
        forbidden_keys = {"shell", "script", "raw_command", "eval", "exec_raw"}
        found = forbidden_keys & data.keys()
        if found:
            raise PlanValidationError(f"Forbidden fields in plan: {found}")

        try:
            plan = TaskPlan.model_validate(data)
        except ValidationError as exc:
            raise PlanValidationError(f"Schema validation failed: {exc}") from exc

        self._validate_action_count(plan)
        self._validate_paths(plan)
        self._validate_commands(plan)
        self._validate_risk_consistency(plan)
        return plan

    def _validate_action_count(self, plan: TaskPlan) -> None:
        if len(plan.actions) > self._max_actions:
            raise PlanValidationError(f"Plan exceeds maximum action count ({self._max_actions})")

    def _validate_paths(self, plan: TaskPlan) -> None:
        path_fields = {
            ActionType.MOVE_FILE: ("source", "destination"),
            ActionType.COPY_FILE: ("source", "destination"),
            ActionType.CREATE_FOLDER: ("destination",),
            ActionType.LIST_FILES: ("source",),
        }
        for action in plan.actions:
            fields = path_fields.get(action.type, ())
            for field_name in fields:
                raw = getattr(action, field_name)
                if raw:
                    try:
                        self._path_guard.resolve(raw)
                    except PathGuardError as exc:
                        raise PlanValidationError(
                            f"Path validation failed for {field_name}='{raw}': {exc}"
                        ) from exc

    def _validate_commands(self, plan: TaskPlan) -> None:
        for action in plan.actions:
            if action.type == ActionType.EXEC and action.command:
                try:
                    self._command_policy.validate(action.command, action.args)
                except CommandPolicyError as exc:
                    raise PlanValidationError(f"Command policy violation: {exc}") from exc

    def _validate_risk_consistency(self, plan: TaskPlan) -> None:
        has_exec = any(a.type == ActionType.EXEC for a in plan.actions)
        has_destructive = any(a.type in (ActionType.MOVE_FILE,) for a in plan.actions)
        if has_exec and plan.risk_level == RiskLevel.LOW:
            raise PlanValidationError("Plans with exec actions cannot be classified as low risk")
        if has_destructive and plan.risk_level == RiskLevel.LOW:
            raise PlanValidationError("Plans with file operations cannot be classified as low risk")
